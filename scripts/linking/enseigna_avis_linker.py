"""
Enseigna Avis Linker
====================

Outil simple de maillage interne pour les articles de type *avis* d'enseigna.

Pour chaque article, il pose :
  1. UN lien vers Superprof (superprof.fr), en rotation home / landing ville
     via le SuperprofRotator existant (paris, lyon, marseille, montpellier,
     bordeaux, lille, ...).
  2. UN à DEUX liens internes avis <-> avis enseigna (busuu, babbel, apprentus,
     vos cours, ...), choisis dans la même famille thématique.

Règles dures :
  - AUCUN lien vers un concurrent (on ne lie que superprof.fr et enseigna.fr).
  - JAMAIS deux fois la même URL enseigna dans une page.
  - On ne lie jamais un article vers lui-même.
  - On n'ajoute pas de phrase-robot ni de section « Articles connexes » :
    l'ancre est posée sur une expression DÉJÀ présente dans le texte. Si aucune
    expression ne convient, le lien est SKIP et reporté (jamais forcé).
  - Préservation des assets garantie par InjectionValidator (images/tableaux).

L'outil travaille sur les fichiers Gutenberg déjà générés
(_shared/outputs/enseigna/html/**/{slug}_refreshed.gutenberg.html). Il est
découplé de la génération : rejouable, reviewable, backup avant écriture.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scripts.cta.superprof_rotator import SuperprofRotator
from scripts.linking.injection_validator import InjectionValidator

logger = logging.getLogger(__name__)

DOMAIN = "enseigna.fr"
SUPERPROF_HOME = "https://www.superprof.fr/"

# Familles thématiques d'articles avis. La famille détermine (a) le pool de
# sœurs pour le maillage interne, (b) la matière passée au rotator Superprof.
FAMILIES = {
    "soutien-scolaire": {
        "rotator_subject": "soutien-scolaire",
        "url_markers": [
            "soutien-scolaire", "acadomia", "anacours", "completude",
            "kartable", "gostudent", "schoolmouv", "sherpas", "apprentus",
            "groupe-reussite", "legendre", "yoopies", "superprof-vs",
            "voscours-soutien", "cours-particuliers",
        ],
    },
    "langues": {
        "rotator_subject": "anglais",  # défaut famille langues
        "url_markers": [
            "rosetta", "mosalingua", "babbel", "duolingo", "memrise", "busuu",
            "italki", "gymglish", "berlitz", "wall-street", "langues-preply",
            "cours-langue", "avis-cours-langue",
        ],
    },
    "loisirs": {
        "rotator_subject": "musique",
        "url_markers": [
            "loisirs", "musique", "yousician", "allegro", "kelprof",
        ],
    },
    "formations": {
        "rotator_subject": "informatique",
        "url_markers": [
            "openclassrooms", "coursera", "udemy", "studi", "digischool",
            "formations", "formation",
        ],
    },
}

# Matière rotator plus fine, dérivée de marques langues (l'ancre Superprof
# colle alors à la langue du produit testé).
LANG_SUBJECT = {
    "rosetta": "allemand",   # avis enseigna = cours d'allemand
    "babbel": "allemand",
    "busuu": "italien",
    "berlitz": "anglais",
    "wall-street": "anglais",
    "italki": "anglais",
    "gymglish": "anglais",
    "mosalingua": "anglais",
    "duolingo": "anglais",
    "memrise": "anglais",
}

# Expressions-ancre candidates par famille : on cherche l'une d'elles dans le
# texte pour y poser le lien sœur (ancre naturelle, déjà présente).
FAMILY_ANCHOR_PHRASES = {
    "soutien-scolaire": [
        "soutien scolaire", "cours particuliers", "cours de soutien",
        "aide aux devoirs", "professeur particulier",
    ],
    "langues": [
        "cours de langues", "apprendre une langue", "cours de langue",
        "apprentissage des langues", "cours d'anglais",
    ],
    "loisirs": [
        "cours de musique", "cours particuliers", "activités de loisirs",
        "professeur particulier",
    ],
    "formations": [
        "formation en ligne", "formations en ligne", "cours en ligne",
    ],
}

MAX_SIBLING_LINKS = 2  # liens avis<->avis par article


@dataclass
class PlannedLink:
    url: str
    anchor_phrase: str          # expression à transformer en lien
    kind: str                   # "superprof" | "sibling"
    reason: str = ""


@dataclass
class ArticleResult:
    url: str
    file: Optional[str] = None
    links_added: list[dict] = field(default_factory=list)
    links_skipped: list[dict] = field(default_factory=list)
    internal_before: int = 0
    internal_after: int = 0
    validation_passed: bool = True
    error: Optional[str] = None


class EnseignaAvisLinker:
    def __init__(self, base_path: Optional[Path] = None, seed_salt: str = ""):
        self.base_path = base_path or Path(__file__).parent.parent.parent
        from _shared.core.tenant_paths import TenantPaths
        _out = TenantPaths(base_path=self.base_path).output_dir("enseigna")
        self.outputs_html = _out / "html"
        self.reports_dir = _out / "json"
        self.rotator = SuperprofRotator()
        self.validator = InjectionValidator(DOMAIN)
        self._sitemap = self._load_sitemap_posts()
        # Binding autoritaire URL -> fichier (source de vérité éditée à la main).
        self._url_to_file = self._load_file_bindings()

    # -- Inventaire ----------------------------------------------------------

    def _load_sitemap_posts(self) -> list[str]:
        cache = self.base_path / "_shared" / "cache" / "sitemap_cache.json"
        data = json.loads(cache.read_text(encoding="utf-8"))
        hubs = {"langues", "loisirs", "soutien-scolaire", "formations-diplomantes"}
        posts = []
        for u in data.get("urls", []):
            loc = u["loc"]
            last = loc.rstrip("/").split("/")[-1]
            if last and last not in hubs and "enseigna.fr" in loc:
                posts.append(loc.rstrip("/") + "/")
        return sorted(set(posts))

    def _load_file_bindings(self) -> dict[str, Path]:
        """Charge le binding URL -> Path depuis enseigna_file_urls.json."""
        from _shared.core.tenant_paths import TenantPaths
        cfg = (
            TenantPaths(base_path=self.base_path).linking_maps_dir("enseigna")
            / "file_urls.json"
        )
        mapping: dict[str, Path] = {}
        if not cfg.exists():
            logger.warning("[AvisLinker] Binding fichier introuvable: %s", cfg)
            return mapping
        data = json.loads(cfg.read_text(encoding="utf-8"))
        for rel_file, url in data.get("bindings", {}).items():
            path = self.outputs_html / rel_file
            if path.exists():
                mapping[_norm(url)] = path
            else:
                logger.warning("[AvisLinker] Fichier binding manquant: %s", path)
        return mapping

    def resolve_file(self, url: str) -> Optional[Path]:
        """
        Relie une URL d'article à son fichier de sortie via le binding
        autoritaire. Aucun rapprochement heuristique : un article non listé
        dans enseigna_file_urls.json est simplement ignoré (pas de faux positif).
        """
        return self._url_to_file.get(_norm(url))

    # -- Classification ------------------------------------------------------

    def family_of(self, url: str) -> str:
        slug = _slug(url)
        blob = _strip_accents(slug.lower())
        # loisirs et langues priment sur soutien (fallback le plus large).
        for fam in ("loisirs", "langues", "formations", "soutien-scolaire"):
            for marker in FAMILIES[fam]["url_markers"]:
                if marker in blob:
                    return fam
        return "soutien-scolaire"

    def rotator_subject_for(self, url: str, family: str) -> str:
        slug = _strip_accents(_slug(url).lower())
        if family == "langues":
            for marker, subj in LANG_SUBJECT.items():
                if marker in slug:
                    return subj
        return FAMILIES[family]["rotator_subject"]

    # -- Planification des liens d'un article --------------------------------

    def plan_for_article(
        self,
        url: str,
        soup: BeautifulSoup,
        used_sibling_urls: set[str],
    ) -> list[PlannedLink]:
        """
        Décide des liens à poser dans un article, sans écrire.

        used_sibling_urls : URLs sœurs déjà consommées sur le lot (rotation
        globale pour éviter de toujours lier les mêmes cibles).
        """
        family = self.family_of(url)
        existing = _existing_hrefs(soup)
        planned: list[PlannedLink] = []
        planned_targets: set[str] = set()

        # 1. Lien Superprof (rotator).
        #    - Aucun lien superprof.fr    -> on en pose un (ancre sur phrase).
        #    - Lien home nu superprof.fr/ -> on l'upgrade vers une landing ville
        #      (le rotator apporte la variété home/ville que la home nue n'a pas).
        #    - Landing déjà spécifique    -> on ne touche à rien.
        sp_hrefs = [h for h in existing if "superprof.fr" in h]
        subject = self.rotator_subject_for(url, family)
        sel = self.rotator.select_landing(
            site_id="superprof-ressources",
            article_subject=subject,
            article_url=url,
        )
        sp_url = sel["url"]
        if not sp_hrefs:
            phrase = self._find_anchor_phrase(
                soup, [sel["anchor"]] + FAMILY_ANCHOR_PHRASES.get(family, [])
            )
            if phrase:
                planned.append(PlannedLink(
                    url=sp_url, anchor_phrase=phrase, kind="superprof",
                    reason=sel.get("reason", ""),
                ))
                planned_targets.add(_norm(sp_url))
        elif any(_is_bare_superprof_home(h) for h in sp_hrefs) and not _is_bare_superprof_home(sp_url):
            # Retarget in place : on garde l'ancre existante, on change le href.
            planned.append(PlannedLink(
                url=sp_url, anchor_phrase="", kind="superprof_upgrade",
                reason="upgrade home nue -> landing " + sel.get("reason", ""),
            ))
            planned_targets.add(_norm(sp_url))

        # 2. Liens sœurs avis<->avis (même famille), en rotation globale.
        self_brands = _brand_tokens(_slug(url))
        siblings = self._sibling_candidates(url, family)
        # Écarter les cibles dont la marque d'ancre est celle de l'article source
        # (ancre auto-référentielle, ex. 'voscours' sur la page avis Voscours).
        def _sib_brand_tokens(s: str) -> set[str]:
            return {t.lower() for b in _target_brands(s) for t in b.split()}
        siblings = [
            s for s in siblings
            if not (_sib_brand_tokens(s) & self_brands)
        ]
        # Priorité aux cibles pas encore utilisées sur le lot.
        siblings.sort(key=lambda s: (_norm(s) in used_sibling_urls, s))
        used_anchor_phrases: set[str] = set()
        for sib in siblings:
            if len([p for p in planned if p.kind == "sibling"]) >= MAX_SIBLING_LINKS:
                break
            nsib = _norm(sib)
            if nsib in planned_targets:
                continue
            if any(nsib == _norm(h) for h in existing):
                continue  # déjà lié dans la page
            phrase = self._find_anchor_phrase(
                soup, self._sibling_anchor_phrases(sib)
            )
            if not phrase:
                continue
            # Jamais la même ancre (même marque) deux fois dans la page :
            # 'Acadomia' ne doit pas pointer à la fois vers l'avis et le vs.
            if phrase.lower() in used_anchor_phrases:
                continue
            planned.append(PlannedLink(
                url=sib, anchor_phrase=phrase, kind="sibling",
                reason=f"maillage avis<->avis ({family})",
            ))
            planned_targets.add(nsib)
            used_anchor_phrases.add(phrase.lower())

        return planned

    def _sibling_candidates(self, url: str, family: str) -> list[str]:
        nself = _norm(url)
        out = []
        for post in self._sitemap:
            if _norm(post) == nself:
                continue
            if self.family_of(post) != family:
                continue
            out.append(post)
        return out

    def _sibling_anchor_phrases(self, sibling_url: str) -> list[str]:
        """
        Expressions-ancre pour une sœur : le nom de la MARQUE testée par
        l'article cible (busuu, babbel, acadomia...). Pour un comparatif
        'superprof-vs-X', on ancre sur X (le concurrent comparé), jamais sur le
        mot générique 'superprof' qui serait ambigu et non descriptif.
        """
        brands = _target_brands(sibling_url)
        phrases: list[str] = []
        for b in brands:
            phrases.append(b.capitalize())
            phrases.append(b)
        return phrases

    def _find_anchor_phrase(
        self, soup: BeautifulSoup, phrases: list[str]
    ) -> Optional[str]:
        """
        Cherche la 1re expression présente dans un paragraphe éligible et pas
        déjà à l'intérieur d'un lien. Retourne l'expression trouvée (casse du
        texte réel), ou None.
        """
        for phrase in phrases:
            if not phrase:
                continue
            for p in soup.find_all("p"):
                if _p_inside_callout(p):
                    continue
                found = _find_linkable_text(p, phrase)
                if found:
                    return found
        return None

    # -- Application ---------------------------------------------------------

    def process(self, urls: Optional[list[str]] = None, dry_run: bool = True) -> list[ArticleResult]:
        targets = urls or self._sitemap
        used_sibling_urls: set[str] = set()
        results: list[ArticleResult] = []

        for url in targets:
            res = ArticleResult(url=url)
            path = self.resolve_file(url)
            if not path:
                res.error = "no local output file"
                results.append(res)
                continue
            res.file = str(path.relative_to(self.base_path))

            original = path.read_text(encoding="utf-8")
            soup = BeautifulSoup(original, "html.parser")
            res.internal_before = _count_internal(soup)

            planned = self.plan_for_article(url, soup, used_sibling_urls)

            for pl in planned:
                if pl.kind == "superprof_upgrade":
                    anchor = _retarget_bare_superprof(soup, pl.url)
                    if anchor is not None:
                        res.links_added.append({
                            "url": pl.url, "anchor": anchor,
                            "kind": pl.kind, "reason": pl.reason,
                        })
                    else:
                        res.links_skipped.append({
                            "url": pl.url, "anchor": "",
                            "kind": pl.kind, "reason": "home nue introuvable à l'écriture",
                        })
                    continue
                ok = _wrap_phrase_as_link(soup, pl.anchor_phrase, pl.url)
                if ok:
                    res.links_added.append({
                        "url": pl.url, "anchor": pl.anchor_phrase,
                        "kind": pl.kind, "reason": pl.reason,
                    })
                    if pl.kind == "sibling":
                        used_sibling_urls.add(_norm(pl.url))
                else:
                    res.links_skipped.append({
                        "url": pl.url, "anchor": pl.anchor_phrase,
                        "kind": pl.kind, "reason": "phrase introuvable à l'écriture",
                    })

            modified = str(soup)
            validation = self.validator.validate(original, modified)
            res.validation_passed = validation["valid"]
            res.internal_after = validation["internal_links_after"]

            if res.links_added and not dry_run:
                if res.validation_passed:
                    backup = path.with_suffix(".backup.html")
                    backup.write_text(original, encoding="utf-8")
                    path.write_text(modified, encoding="utf-8")
                else:
                    res.error = "validation failed: " + "; ".join(validation["errors"])
            results.append(res)

        if not dry_run:
            self._save_report(results)
        return results

    def _save_report(self, results: list[ArticleResult]):
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        out = self.reports_dir / "avis_linking_report.json"
        payload = {
            "site": "enseigna",
            "articles": [
                {
                    "url": r.url, "file": r.file,
                    "internal_before": r.internal_before,
                    "internal_after": r.internal_after,
                    "validation_passed": r.validation_passed,
                    "links_added": r.links_added,
                    "links_skipped": r.links_skipped,
                    "error": r.error,
                }
                for r in results
            ],
        }
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("[AvisLinker] Rapport écrit -> %s", out)


# ---------------------------------------------------------------------------
# Helpers HTML / texte
# ---------------------------------------------------------------------------
_ACCENT_TRANS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
_SLUG_STOP = {
    "avis", "test", "mon", "notre", "les", "des", "sur", "cours", "de", "la",
    "le", "en", "ligne", "plateforme", "soutien", "scolaire", "langue",
    "langues", "loisirs", "et", "du", "un", "une", "que", "vaut", "cette",
    "ecole", "pour", "apprendre", "ma", "mes", "experience", "personnelle",
    "objective", "temoignage", "comment", "se", "deroulent", "retours",
    "ressenti", "suite", "chez", "decouverte", "vs", "avec", "natifs",
    "formation", "particuliers", "apprentissage", "danglais", "litalien",
    "dallemand", "ditalien", "anglais", "allemand", "italien", "a",
    "article", "plateforme", "que",
}


def _strip_accents(s: str) -> str:
    return s.translate(_ACCENT_TRANS)


def _slug(url: str) -> str:
    p = urlparse(url).path.strip("/") if url.startswith("http") else url
    return p.split("/")[-1] if p else p


def _brand_tokens(text: str) -> set[str]:
    text = _strip_accents(text.lower())
    words = re.split(r"[^a-z0-9]+", text)
    return {w for w in words if len(w) >= 3 and w not in _SLUG_STOP}


# Marques multi-tokens à préserver telles quelles comme ancre.
_KNOWN_MULTITOKEN = {
    ("wall", "street"): "Wall Street English",
    ("rosetta", "stone"): "Rosetta Stone",
    ("groupe", "reussite"): "Groupe Réussite",
    ("cours", "legendre"): "Cours Legendre",
}


def _target_brands(url: str) -> list[str]:
    """
    Marques testées par un article cible, ordonnées par pertinence d'ancre.

    - 'busuu-avis-...'            -> ['busuu']
    - 'superprof-vs-acadomia'    -> ['acadomia']  (le concurrent comparé)
    - 'avis-wall-street-english' -> ['Wall Street English']
    """
    slug = _strip_accents(_slug(url).lower())
    toks = [t for t in re.split(r"[^a-z0-9]+", slug)
            if len(t) >= 3 and t not in _SLUG_STOP]

    # Comparatif superprof-vs-X : on garde X (retire 'superprof').
    if "superprof" in slug and "-vs-" in slug:
        toks = [t for t in toks if t != "superprof"]

    # Marque multi-tokens connue ?
    for combo, label in _KNOWN_MULTITOKEN.items():
        if all(c in toks for c in combo):
            return [label]

    if not toks:
        return []
    # Marque = token le plus long (heuristique robuste sur ces slugs).
    return [max(toks, key=len)]


def _norm(url: str) -> str:
    u = url.lower().strip().rstrip("/")
    u = u.replace("https://www.", "https://").replace("http://www.", "https://")
    u = u.replace("http://", "https://")
    return u


def _existing_hrefs(soup: BeautifulSoup) -> set[str]:
    return {a.get("href", "") for a in soup.find_all("a", href=True)}


def _count_internal(soup: BeautifulSoup) -> int:
    return sum(1 for a in soup.find_all("a", href=True) if DOMAIN in a.get("href", ""))


def _p_inside_callout(p) -> bool:
    parent = p.parent
    while parent and getattr(parent, "name", None):
        if parent.name == "div":
            style = parent.get("style", "")
            if "background-color" in style or "border-left" in style:
                return True
        parent = parent.parent
    return False


def _find_linkable_text(p, phrase: str) -> Optional[str]:
    """
    Vérifie qu'une occurrence de `phrase` existe dans un NavigableString du
    paragraphe hors de tout lien existant. Retourne le texte réellement présent
    (respect de la casse) ou None.
    """
    from bs4 import NavigableString
    pat = re.compile(re.escape(phrase), re.IGNORECASE)
    for node in p.descendants:
        if isinstance(node, NavigableString):
            if node.find_parent("a"):
                continue
            m = pat.search(str(node))
            if m:
                return m.group(0)
    return None


def _is_bare_superprof_home(href: str) -> bool:
    """True si l'URL est la home nue superprof.fr (sans /cours/...)."""
    n = _norm(href)
    return n in ("https://superprof.fr", "https://superprof.fr/")


def _retarget_bare_superprof(soup: BeautifulSoup, new_url: str) -> Optional[str]:
    """
    Repointe le 1er lien home nue superprof.fr vers new_url, en conservant
    l'ancre existante. Retourne l'ancre conservée, ou None si rien à faire.
    """
    for a in soup.find_all("a", href=True):
        if _is_bare_superprof_home(a.get("href", "")):
            a["href"] = new_url
            return a.get_text(strip=True)
    return None


def _wrap_phrase_as_link(soup: BeautifulSoup, phrase: str, url: str) -> bool:
    """
    Transforme la 1re occurrence de `phrase` (hors lien, hors callout, hors
    titre) en <a href=url>phrase</a>. Ne crée jamais de <strong> autour.
    Retourne True si un lien a été posé.
    """
    from bs4 import NavigableString
    pat = re.compile(re.escape(phrase), re.IGNORECASE)
    for p in soup.find_all("p"):
        if _p_inside_callout(p):
            continue
        for node in list(p.descendants):
            if not isinstance(node, NavigableString):
                continue
            if node.find_parent("a"):
                continue
            text = str(node)
            m = pat.search(text)
            if not m:
                continue
            before, match, after = text[:m.start()], m.group(0), text[m.end():]
            a = soup.new_tag("a", href=url)
            a.string = match
            node.replace_with(a)
            if before:
                a.insert_before(NavigableString(before))
            if after:
                a.insert_after(NavigableString(after))
            return True
    return False
