"""Répare les blocs AdvGB/quote mal formatés dans les articles SP Ressources.

Bugs corrigés (causés par gutenberg_formatter.py qui ne gère pas les blocs AdvGB
et émet wp:quote natif au lieu de superprof/quote-block) :
  1. quote      : <!-- wp:quote --> + markup custom  ->  <!-- wp:superprof/quote-block {...} -->
  2. infobox    : <div> brut sans commentaire        ->  <!-- wp:advgb/infobox {...} --> single-line
  3. count-up   : <div> brut sans commentaire        ->  <!-- wp:advgb/count-up {...} --> single-line
  4. sources    : <div> brut sans commentaire        ->  groupe wp:group + wp:list complet
  5. timeline   : <div> brut sans commentaire        ->  wp:superprof/timeline-block + wp:timeline/timeline-container

Reconstruction lossless :
  - infobox couleur via suffixe -001 (jaune) / -002 (bleue)
  - count-up couleur via style inline du compteur
  - tout le texte est préservé depuis le markup existant
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

from _shared.core.tenant_paths import TenantPaths
HTML_DIR = TenantPaths().output_dir("superprof-ressources") / "html"

FILES = [
    "monnaie_franc_puissance", "ouvrage_brisou_pellen", "regles_bonne_conduite",
    "societe_athenes_politique", "telechargement_google_earth", "vie_biologie_metabolisme",
    "vie_ecrivain_moderne_lumiere", "agir_collectivement", "bien_parler_en_classe",
    "interface_du_web", "question_espagnol_lycee", "verbes_present_britanniques",
    "decouvrir_singularite_terrestre", "energie_mecanique_premiere",
    "rangement_organisation_efficacite", "termes_anglais_jardinage",
    "correspondance_cas_fonction", "valeur_probante", "peinture_artiste_david",
    "exemple_dessin_chapeau", "maupassant_saison_beaute", "constitutions_lois_fonctionnement",
    "religion_chretiente_pouvoir", "traites_paix_conflit_mondial", "verbe_langue_hispanique",
    "lire_texte_internet", "lecture_passage_classique",
]

# Couleurs par type d'infobox (convention du generation_prompt)
YELLOW = {"bg": "#fffbf0", "border": "#ffcf3b"}  # Info Box Jaune
BLUE = {"bg": "#e8f2ff", "border": "#157dfe"}    # Info Box Bleue


def _infobox_color(suffix: str) -> dict:
    """Couleur deduite du suffixe de classe (001/jaune -> jaune, 002/bleu -> bleue)."""
    s = suffix.lower()
    if "jaune" in s or s.endswith("001"):
        return YELLOW
    if "bleu" in s or s.endswith("002"):
        return BLUE
    return BLUE  # defaut


def _attrs(d: dict) -> str:
    """json.dumps avec accents litteraux + tags HTML echappes en \\u003c (format AdvGB)."""
    s = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c").replace(">", "\\u003e")


def fix_quote(text: str) -> tuple[str, int]:
    pat = re.compile(
        r'<!-- wp:quote -->\s*'
        r'<blockquote class="wp-block-superprof-quote-block wp-block-quote">\s*'
        r'<p>(?P<q>.*?)</p>\s*'
        r'<cite>(?P<c>.*?)</cite>\s*'
        r'</blockquote>\s*'
        r'<!-- /wp:quote -->',
        re.DOTALL,
    )

    def repl(m: re.Match) -> str:
        q, c = m.group("q").strip(), m.group("c").strip()
        attrs = _attrs({"quote": q, "citation": c})
        return (
            f"<!-- wp:superprof/quote-block {attrs} -->\n"
            f'<blockquote class="wp-block-superprof-quote-block"><p>{q}</p><cite>{c}</cite></blockquote>\n'
            f"<!-- /wp:superprof/quote-block -->"
        )

    return pat.subn(repl, text)


def fix_infobox(text: str) -> tuple[str, int]:
    pat = re.compile(
        # le \n exige la forme BRUTE multi-lignes -> idempotent (ne re-matche pas le single-line corrige)
        r'<div class="wp-block-advgb-infobox advgb-infobox-wrapper has-text-align-center advgb-infobox-(?P<suf>[a-zA-Z0-9-]+)">[ \t]*\n[ \t]*'
        r'<div class="advgb-infobox-wrap">.*?'
        r'<div class="advgb-infobox-title">(?P<title>.*?)</div>\s*'
        r'<p class="advgb-infobox-text">(?P<txt>.*?)</p>\s*'
        r'</div>\s*</div>\s*</div>',
        re.DOTALL,
    )

    def repl(m: re.Match) -> str:
        col = _infobox_color(m.group("suf"))
        title = m.group("title").strip()
        txt = m.group("txt").strip()
        new_id = f"advgb-infobox-{uuid.uuid4()}"
        attrs = _attrs({
            "blockIDX": new_id,
            "containerBorderWidth": 2,
            "containerBackground": col["bg"],
            "containerBorderBackground": col["border"],
            "iconBackground": col["bg"],
            "iconColor": col["border"],
            "title": title,
            "titleHtmlTag": "div",
            "text": txt,
            "changed": True,
        })
        markup = (
            f'<div class="wp-block-advgb-infobox advgb-infobox-wrapper has-text-align-center {new_id}">'
            f'<div class="advgb-infobox-wrap"><div class="advgb-infobox-icon-container">'
            f'<div class="advgb-infobox-icon-inner-container"><i class="material-icons-outlined">beenhere</i></div></div>'
            f'<div class="advgb-infobox-textcontent"><div class="advgb-infobox-title">{title}</div>'
            f'<p class="advgb-infobox-text">{txt}</p></div></div></div>'
        )
        return f"<!-- wp:advgb/infobox {attrs} -->\n{markup}\n<!-- /wp:advgb/infobox -->"

    return pat.subn(repl, text)


def fix_countup(text: str) -> tuple[str, int]:
    pat = re.compile(
        # le \n exige la forme BRUTE multi-lignes -> idempotent (ne re-matche pas le single-line corrige)
        r'<div class="wp-block-advgb-count-up advgb-count-up count-up-[a-zA-Z0-9-]+"[^>]*>[ \t]*\n[ \t]*'
        r'<div class="advgb-count-up-columns-one"[^>]*>\s*'
        r'<h4 class="advgb-count-up-header">(?P<h>.*?)</h4>\s*'
        r'<div class="advgb-counter" style="color:(?P<color>#[0-9a-fA-F]+);[^"]*">\s*'
        r'<span class="advgb-counter-number">(?P<num>.*?)</span>\s*'
        r'</div>\s*'
        r'<p class="advgb-count-up-desc">(?P<d>.*?)</p>\s*'
        r'</div>\s*</div>',
        re.DOTALL,
    )

    def repl(m: re.Match) -> str:
        h = m.group("h").strip()
        color = m.group("color")
        num = m.group("num").strip()
        d = m.group("d").strip()
        new_id = f"count-up-{uuid.uuid4()}"
        attrs = _attrs({
            "id": new_id,
            "headerText": h,
            "countUpNumber": num,
            "countUpNumberColor": color,
            "descText": d,
            "changed": True,
        })
        markup = (
            f'<div class="wp-block-advgb-count-up advgb-count-up {new_id}" style="display:flex">'
            f'<div class="advgb-count-up-columns-one"><h4 class="advgb-count-up-header">{h}</h4>'
            f'<div class="advgb-counter" style="color:{color};font-size:55px">'
            f'<span class="advgb-counter-number">{num}</span></div>'
            f'<p class="advgb-count-up-desc">{d}</p></div></div>'
        )
        return f"<!-- wp:advgb/count-up {attrs} -->\n{markup}\n<!-- /wp:advgb/count-up -->"

    return pat.subn(repl, text)


def fix_sources(text: str) -> tuple[str, int]:
    pat = re.compile(
        r'<div class="wp-block-group">\s*'
        r'<div class="wp-block-group wp-block-wp-sp-gutenberg-blocks-block-sources">\s*'
        r'<h2 class="wp-block-heading">(?P<h2>.*?)</h2>\s*'
        r'<ol class="wp-block-list references">(?P<items>.*?)</ol>\s*'
        r'</div>\s*</div>',
        re.DOTALL,
    )

    def repl(m: re.Match) -> str:
        h2 = m.group("h2").strip()
        lis = re.findall(r"<li>(.*?)</li>", m.group("items"), re.DOTALL)
        # 1er <!-- wp:list-item --> colle au <ol>, dernier <!-- /wp:list-item --> colle au </ol>
        items = "\n\n".join(
            f"<!-- wp:list-item -->\n<li>{li.strip()}</li>\n<!-- /wp:list-item -->" for li in lis
        )
        list_block = (
            '<!-- wp:list {"ordered":true,"className":"references"} -->\n'
            f'<ol class="wp-block-list references">{items}</ol>\n'
            "<!-- /wp:list -->"
        )
        return (
            "<!-- wp:group -->\n"
            '<div class="wp-block-group"><!-- wp:group {"className":"wp-block-wp-sp-gutenberg-blocks-block-sources"} -->\n'
            '<div class="wp-block-group wp-block-wp-sp-gutenberg-blocks-block-sources"><!-- wp:heading -->\n'
            f'<h2 class="wp-block-heading">{h2}</h2>\n'
            "<!-- /wp:heading -->\n\n"
            f"{list_block}</div>\n"
            "<!-- /wp:group --></div>\n"
            "<!-- /wp:group -->"
        )

    return pat.subn(repl, text)


def fix_timeline(text: str) -> tuple[str, int]:
    """Enveloppe un timeline-block brut avec les commentaires Gutenberg.

    <div class="wp-block-superprof-timeline-block ..."> (sans commentaire)
      -> <!-- wp:superprof/timeline-block --> + <!-- wp:timeline/timeline-container {...} --> par ligne.
    """
    open_pat = re.compile(r'<div class="wp-block-superprof-timeline-block timeline[^"]*">[ \t]*\n')
    m = open_pat.search(text)
    if not m:
        return text, 0
    # idempotent : si deja precede du commentaire, ne rien faire
    if text[: m.start()].rstrip().endswith("<!-- wp:superprof/timeline-block -->"):
        return text, 0

    row_pat = re.compile(
        r'<div class="wp-block-timeline-timeline-container timeline-row">\s*'
        r'<div class="timeline-dot"[^>]*></div>\s*'
        r'<div class="timeline-date">\s*'
        r'<p class="timeline-date-item"[^>]*>(?P<date>.*?)</p>\s*</div>\s*'
        r'<div class="timeline-details">\s*'
        r'<p class="timeline-title"[^>]*>(?P<title>.*?)</p>\s*'
        r'<p class="timeline-description"[^>]*>(?P<desc>.*?)</p>\s*</div>\s*</div>',
        re.DOTALL,
    )
    rows = list(row_pat.finditer(text, m.end()))
    if not rows:
        return text, 0
    close_m = re.compile(r'\s*</div>').match(text, rows[-1].end())
    if not close_m:
        return text, 0
    end = close_m.end()

    n = len(rows)
    containers = []
    for i, r in enumerate(rows):
        date, title, desc = r.group("date").strip(), r.group("title").strip(), r.group("desc").strip()
        attrs = _attrs({
            "itemDate": date, "itemTitle": title,
            "itemDescription": desc, "isLast": i == n - 1,
        })
        containers.append(
            f"<!-- wp:timeline/timeline-container {attrs} -->\n"
            '<div class="wp-block-timeline-timeline-container timeline-row">\n'
            '<div class="timeline-dot" style="background-color:#ff6363"></div>\n'
            '<div class="timeline-date">\n'
            f'<p class="timeline-date-item" style="color:#ff6363;font-size:18px;text-align:left">{date}</p>\n'
            "</div>\n"
            '<div class="timeline-details">\n'
            f'<p class="timeline-title" style="color:#888888;font-size:18px">{title}</p>\n'
            f'<p class="timeline-description" style="color:#888888;font-size:16px">{desc}</p>\n'
            "</div>\n"
            "</div>\n"
            "<!-- /wp:timeline/timeline-container -->"
        )
    block = (
        "<!-- wp:superprof/timeline-block -->\n"
        '<div class="wp-block-superprof-timeline-block timeline medium">\n'
        + "\n".join(containers)
        + "\n</div>\n"
        "<!-- /wp:superprof/timeline-block -->"
    )
    return text[: m.start()] + block + text[end:], n


def process(text: str) -> tuple[str, dict]:
    text, q = fix_quote(text)
    text, ib = fix_infobox(text)
    text, cu = fix_countup(text)
    text, sr = fix_sources(text)
    text, tl = fix_timeline(text)
    return text, {"quote": q, "infobox": ib, "count_up": cu, "sources": sr, "timeline": tl}


def main() -> None:
    dry = "--apply" not in sys.argv
    print("=== DRY-RUN ===" if dry else "=== APPLY ===")
    total = {"quote": 0, "infobox": 0, "count_up": 0, "sources": 0, "timeline": 0}
    errors = []
    for slug in FILES:
        p = HTML_DIR / f"{slug}.html"
        if not p.exists():
            errors.append(f"{slug}: MISSING")
            continue
        orig = p.read_text(encoding="utf-8")
        new, counts = process(orig)
        # Validation : on attend 1 quote, 2 infobox, 1 count-up, 1 sources par fichier
        ok = counts["quote"] <= 1 and counts["infobox"] <= 2 and counts["count_up"] <= 1 and counts["sources"] == 1
        flag = "" if ok else "  <-- ATTENTION"
        print(f"  {slug:42s} quote={counts['quote']} infobox={counts['infobox']} count_up={counts['count_up']} sources={counts['sources']} timeline={counts['timeline']}{flag}")
        for k in total:
            total[k] += counts[k]
        if not dry and new != orig:
            p.write_text(new, encoding="utf-8")
    print(f"\nTOTAL: {total}")
    if errors:
        print("ERREURS:", errors)


if __name__ == "__main__":
    main()
