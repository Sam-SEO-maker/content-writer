"""Génère le catalogue des blogs Superprof depuis les propriétés GSC.

Le **catalogue** (`_shared/config/superprof_blogs_catalog.json`) liste TOUS les
blogs Superprof actifs (éditoriaux `/blog/` + sites Ressources), qu'ils soient
onboardés ou non comme tenants Content Writer. C'est le « menu » qu'un responsable
pays consulte pour découvrir ce qu'il peut onboarder (`cw tenant init <id>`).

À NE PAS confondre avec le **registre** `sites.json` (tenants réellement onboardés,
chargés par le moteur au runtime). Catalogue = carte ; registre = commande.

Source = propriétés GSC (`mcp gsc-remote list_properties`), la liste vivante des
sites. Comme les tools MCP sont appelés côté Claude Code (pas depuis ce process),
la liste est passée en entrée :

    # Claude appelle mcp__gsc-remote__list_properties, colle la sortie dans un
    # fichier, puis :
    python -m scripts.utils.build_superprof_catalog --from-file props.txt

Filtrage : on ne garde que les propriétés `/blog/` (type=blog) et les 6 sites
Ressources connus (type=ressources). On écarte le bruit (homepages nues,
diccionario, laromedel, resources hors des 6 marchés…).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG_PATH = _PROJECT_ROOT / "_shared" / "config" / "superprof_blogs_catalog.json"

# Les 6 sites Ressources confirmés (cf. RECENSEMENT_BLOGS_SUPERPROF.md).
# gsc_property → (tenant_id conventionnel, country, language, url_base)
RESSOURCES_SITES = {
    "https://www.superprof.fr/ressources/":   ("superprof-ressources", "FR", "fr", "/ressources/"),
    "https://www.superprof.es/apuntes/":      ("es-es-ressources", "ES", "es", "/apuntes/"),
    "https://www.superprof.de/lernplattform/": ("de-de-ressources", "DE", "de", "/lernplattform/"),
    "https://www.superprof.co.uk/resources/": ("en-uk-ressources", "UK", "en", "/resources/"),
    "https://www.superprof.com/resources/":   ("en-us-ressources", "US", "en", "/resources/"),
    "https://www.superprof.com.br/recursos/": ("pt-br-ressources", "BR", "pt", "/recursos/"),
}

# Mapping exhaustif TLD Superprof → (country ISO-2, langue de contenu du marché).
# Couvre les 89 domaines réels (cf. list_properties). La langue = langue
# PRINCIPALE de rédaction du marché Superprof (pas la seule langue officielle).
# Les marchés multilingues gérés par sous-domaine (nl.superprof.be, de.superprof.ch)
# sont traités par _SUBDOMAIN_META ci-dessous.
_TLD_META = {
    # Europe
    "fr": ("FR", "fr"), "es": ("ES", "es"), "de": ("DE", "de"), "it": ("IT", "it"),
    "co.uk": ("GB", "en"), "ie": ("IE", "en"), "pt": ("PT", "pt"), "nl": ("NL", "nl"),
    "be": ("BE", "fr"), "ch": ("CH", "de"), "at": ("AT", "de"), "lu": ("LU", "fr"),
    "pl": ("PL", "pl"), "se": ("SE", "sv"), "no": ("NO", "no"), "dk": ("DK", "da"),
    "fi": ("FI", "fi"), "is": ("IS", "is"), "cz": ("CZ", "cs"), "sk": ("SK", "sk"),
    "hu": ("HU", "hu"), "gr": ("GR", "el"), "ee": ("EE", "et"), "lv": ("LV", "lv"),
    "lt": ("LT", "lt"), "si": ("SI", "sl"), "hr": ("HR", "hr"), "bg": ("BG", "bg"),
    "rs": ("RS", "sr"), "ba": ("BA", "bs"), "al": ("AL", "sq"), "md": ("MD", "ro"),
    "com.cy": ("CY", "el"), "com.mt": ("MT", "en"), "com.ro": ("RO", "ro"),
    "com.ua": ("UA", "uk"),
    # Amériques (LATAM hispanophone = es ; BR = pt ; US/CA-en)
    "com": ("US", "en"), "ca": ("CA", "en"), "mx": ("MX", "es"), "com.br": ("BR", "pt"),
    "com.ar": ("AR", "es"), "cl": ("CL", "es"), "co": ("CO", "es"), "pe": ("PE", "es"),
    "uy": ("UY", "es"), "com.bo": ("BO", "es"), "com.py": ("PY", "es"), "cr": ("CR", "es"),
    "com.do": ("DO", "es"), "com.ec": ("EC", "es"), "com.gt": ("GT", "es"),
    "com.ni": ("NI", "es"), "com.pa": ("PA", "es"), "com.pr": ("PR", "es"),
    "com.sv": ("SV", "es"), "hn": ("HN", "es"), "bz": ("BZ", "en"),
    # Afrique
    "ma": ("MA", "fr"), "cm": ("CM", "fr"), "com.sn": ("SN", "fr"), "com.tn": ("TN", "fr"),
    "co.za": ("ZA", "en"), "ng": ("NG", "en"), "co.ke": ("KE", "en"), "co.tz": ("TZ", "en"),
    "co.mz": ("MZ", "pt"), "co.bw": ("BW", "en"), "rw": ("RW", "en"), "ls": ("LS", "en"),
    "mu": ("MU", "fr"), "com.gh": ("GH", "en"), "com.na": ("NA", "en"),
    # Moyen-Orient / Asie / Océanie
    "ae": ("AE", "en"), "qa": ("QA", "en"), "com.om": ("OM", "en"), "co.il": ("IL", "he"),
    "com.tr": ("TR", "tr"), "in": ("IN", "en"), "co.in": ("IN", "en"), "pk": ("PK", "en"),
    "co.id": ("ID", "id"), "com.my": ("MY", "en"), "sg": ("SG", "en"), "com.ph": ("PH", "en"),
    "vn": ("VN", "vi"), "co.kr": ("KR", "ko"), "jp": ("JP", "ja"), "hk": ("HK", "zh"),
    "com.tw": ("TW", "zh"), "com.au": ("AU", "en"), "co.nz": ("NZ", "en"),
}

# Marchés servis par SOUS-DOMAINE ou domaine spécial (langue portée par le
# préfixe / le domaine, pas le TLD superprof.{tld} standard).
_SUBDOMAIN_META = {
    "nl.superprof.be": ("BE", "nl"),   # Belgique néerlandophone
    "de.superprof.ch": ("CH", "de"),   # Suisse germanophone
    "super-prof.me": ("ME", "sr"),     # Monténégro (domaine à trait d'union)
    "super-prof.nl": ("NL", "nl"),     # Pays-Bas (domaine à trait d'union)
}

# Overrides de langue VÉRIFIÉS sur le contenu réel du blog (WebFetch), quand la
# langue de rédaction Superprof diffère de l'heuristique pays→langue. Clé = TLD.
# Balayage systématique des 90 blogs le 2026-07-15 (5 sous-agents WebFetch) :
# 88/90 conformes à l'heuristique ; seules exceptions ci-dessous. EAU .ae reste
# en ANGLAIS (vérifié). Corée .co.kr reste 'ko' (indéterminé au fetch, défaut sûr).
_LANG_OVERRIDES = {
    "qa": "ar",      # Qatar — blog en arabe (pas en)
    "com.om": "ar",  # Oman — blog en arabe (pas en)
    "com.tn": "ar",  # Tunisie — blog en arabe (pas fr)
    "is": "en",      # Islande — blog en anglais (pas is) — confirmé
    "mu": "en",      # Maurice — chrome/contenu observé en anglais (à confirmer ; défaut en)
}

_DOMAIN_RE = re.compile(r"https?://(?:www\.)?superprof\.([a-z.]+?)/")
_SUBDOMAIN_RE = re.compile(r"https?://([a-z]+\.superprof\.[a-z.]+?)/")


def _host_of(url: str) -> str:
    """Host « <sub>.superprof.<tld> » sans www (pour la détection sous-domaine)."""
    m = re.search(r"https?://([a-z.-]+)/", url.lower())
    host = m.group(1) if m else ""
    return host[4:] if host.startswith("www.") else host


def _tld_of(url: str) -> str:
    m = _DOMAIN_RE.search(url.lower())
    return m.group(1) if m else ""


def resolve_meta(url: str) -> tuple[str, str]:
    """(country ISO-2, langue) pour une URL de blog. Gère les sous-domaines.

    Inconnu → (tld.upper(), "") pour rester visible et corrigeable (aucun crash).
    """
    host = _host_of(url)
    if host in _SUBDOMAIN_META:
        return _SUBDOMAIN_META[host]
    tld = _tld_of(url)
    country, lang = _TLD_META.get(tld, (tld.upper().replace(".", "-"), ""))
    # Override langue vérifié sur contenu réel (prime sur l'heuristique pays).
    if tld in _LANG_OVERRIDES:
        lang = _LANG_OVERRIDES[tld]
    return country, lang


def parse_properties(text: str) -> list[str]:
    """Extrait les URLs de la sortie de list_properties (lignes `- <url> (...)`)."""
    urls = []
    for line in text.splitlines():
        m = re.search(r"(https?://\S+/)", line)
        if m:
            urls.append(m.group(1).strip())
    return urls


def build_catalog(urls: list[str]) -> dict:
    """Construit le catalogue {ressources[], blogs[]} filtré depuis les URLs GSC."""
    ressources = []
    blogs = []
    seen = set()

    for url in urls:
        u = url.rstrip("/") + "/"
        if u in seen:
            continue
        seen.add(u)

        # Sites Ressources connus (liste blanche stricte).
        if u in RESSOURCES_SITES:
            tid, country, lang, url_base = RESSOURCES_SITES[u]
            ressources.append({
                "tenant_id": tid, "type": "ressources", "country": country,
                "language": lang, "gsc_property": u, "url_base": url_base,
                "onboardable": True,
            })
            continue

        # Blogs éditoriaux : /blog/ uniquement.
        if u.endswith("/blog/"):
            if not _host_of(u):
                continue
            country, lang = resolve_meta(u)
            # id conventionnel : {lang}-{country}-blog (country ISO-2 en minuscules).
            country_slug = country.lower() if len(country) <= 3 else country.lower().replace("-", "")
            blogs.append({
                "tenant_id": f"{lang or 'xx'}-{country_slug}-blog",
                "type": "blog", "country": country, "language": lang,
                "gsc_property": u, "url_base": "/blog/", "onboardable": True,
            })

    # Dédup par tenant_id : plusieurs propriétés GSC peuvent viser le même marché
    # (ex. www.superprof.ch/blog/ et de.superprof.ch/blog/ → de-ch-blog). On garde
    # la 1re rencontrée (ordre stable) et on liste les doublons dans le rapport.
    dedup, dup_ids = {}, []
    for b in blogs:
        if b["tenant_id"] in dedup:
            dup_ids.append(f"{b['tenant_id']} ({b['gsc_property']})")
            continue
        dedup[b["tenant_id"]] = b
    blogs = list(dedup.values())

    ressources.sort(key=lambda x: x["tenant_id"])
    blogs.sort(key=lambda x: x["tenant_id"])
    return {
        "_comment": (
            "Catalogue des blogs Superprof (généré depuis GSC list_properties). "
            "NE PAS confondre avec sites.json (tenants onboardés, lu au runtime). "
            "Régénérer : python -m scripts.utils.build_superprof_catalog --from-file <props>."
        ),
        "ressources_sites": ressources,
        "blogs": blogs,
        "counts": {"ressources": len(ressources), "blogs": len(blogs),
                   "blog_duplicates_dropped": len(dup_ids)},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Génère superprof_blogs_catalog.json depuis GSC")
    ap.add_argument("--from-file", required=True,
                    help="Fichier contenant la sortie de mcp gsc-remote list_properties.")
    ap.add_argument("--apply", action="store_true", help="Écrit le catalogue (sinon stdout).")
    args = ap.parse_args()

    text = Path(args.from_file).read_text(encoding="utf-8")
    urls = parse_properties(text)
    catalog = build_catalog(urls)

    if not args.apply:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
        print(f"\n[CATALOG] {catalog['counts']} — dry-run (--apply pour écrire).", file=sys.stderr)
        return 0

    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[CATALOG] ✓ {CATALOG_PATH} — {catalog['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
