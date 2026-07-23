"""
YourTextGuru (YTG) commands.

Usage:
    cw ytg create-guide --main-keyword "bienfaits yoga"
    cw ytg check-guide --guide-id ABC123
    cw ytg batch-prefetch --spreadsheet-id ID [--site moments-yoga]
    cw ytg analyze --guide-id ABC123 --html-file path/to/article.html
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from cli.options import blog_option

from scripts.audit.ytg_analyzer import YTGAnalyzer, YTGAPIError, YTGGuideTimeoutError


@click.group()
def ytg():
    """YourTextGuru semantic guide management."""
    pass


@ytg.command(name='create-guide')
@click.option('--main-keyword', '--keyword', 'keyword', required=True,
              help='Main keyword for the guide. --keyword = legacy alias.')
@click.option('--lang', default='fr', show_default=True, help='Language (fr, en, ...)')
@click.option('--country', default='fr', show_default=True, help='Country (fr, us, ...)')
def create_guide(keyword, lang, country):
    """
    Creates a YTG guide for a keyword and waits for the result.

    Shows the guide_id, the competitors' SOSEO/DSEO scores and the list
    of terms to optimize.
    """
    click.echo(f"\n[YTG] Creating guide for: '{keyword}'")
    click.echo(f"      Language: {lang} | Country: {country}\n")

    analyzer = YTGAnalyzer()
    if not analyzer.is_configured:
        click.echo(
            "[ERROR] YTG_API_KEY missing. Add it to .env or "
            "~/.credentials/ytg/credentials.json",
            err=True
        )
        sys.exit(1)

    try:
        result = analyzer.create_and_wait(keyword, language=lang, country=country)
        if not result:
            click.echo("[ERROR] Guide creation failed.", err=True)
            sys.exit(1)

        click.echo(f"Guide ID   : {result.guide_id}")
        click.echo(f"Status     : {result.status}")
        click.echo()
        click.echo("Competitor scores:")
        click.echo(f"  TOP 3  - SOSEO: {result.top3_soseo:.1f}%  DSEO: {result.top3_dseo:.1f}%")
        click.echo(f"  TOP 10 - SOSEO: {result.top10_soseo:.1f}%  DSEO: {result.top10_dseo:.1f}%")
        click.echo()
        click.echo(f"Terms to optimize ({len(result.semantic_terms)}):")

        # Grouper par couleur
        by_color = {"blue": [], "green": [], "orange": [], "red": []}
        for term in result.terms:
            by_color.get(term.color, by_color["green"]).append(term.term)

        if by_color["blue"]:
            click.echo(f"  Under-optimized (blue) : {', '.join(by_color['blue'][:15])}")
        if by_color["orange"]:
            click.echo(f"  Heavily optim. (orange): {', '.join(by_color['orange'][:15])}")
        if by_color["red"]:
            click.echo(f"  Overdosed (red)        : {', '.join(by_color['red'][:15])}")
        if by_color["green"]:
            click.echo(f"  Normal (green)         : {', '.join(by_color['green'][:15])}")

        click.echo()
        click.echo(
            f"[OK] Guide ready. Add to audit_data.json: "
            f'"ytg_guide_id": "{result.guide_id}"'
        )

    except YTGAPIError as e:
        click.echo(f"[API ERROR] {e}", err=True)
        sys.exit(1)
    except YTGGuideTimeoutError as e:
        click.echo(f"[TIMEOUT] Guide not ready after {e.attempts} attempts.", err=True)
        click.echo(f"Retry later: cw ytg check-guide --guide-id {e.guide_id}")
        sys.exit(1)


@ytg.command(name='check-guide')
@click.option('--guide-id', required=True, help='ID of the YTG guide to check')
def check_guide(guide_id):
    """Checks the status of an existing YTG guide."""
    click.echo(f"\n[YTG] Checking guide: {guide_id}\n")

    analyzer = YTGAnalyzer()
    if not analyzer.is_configured:
        click.echo("[ERROR] YTG_API_KEY missing.", err=True)
        sys.exit(1)

    try:
        raw = analyzer.get_guide_status(guide_id)
        if not raw:
            click.echo("[ERROR] Could not fetch the guide.", err=True)
            sys.exit(1)

        status = raw.get("status") or raw.get("data", {}).get("status", "?")
        click.echo(f"Status: {status}")

        if status == "ready":
            result = analyzer.get_guide(guide_id)
            if result:
                click.echo(f"TOP 3  SOSEO: {result.top3_soseo:.1f}%  DSEO: {result.top3_dseo:.1f}%")
                click.echo(f"TOP 10 SOSEO: {result.top10_soseo:.1f}%  DSEO: {result.top10_dseo:.1f}%")
                click.echo(f"Terms       : {len(result.semantic_terms)}")
                if result.semantic_terms:
                    click.echo(f"Preview     : {', '.join(result.semantic_terms[:10])}...")
        else:
            click.echo("Guide not ready yet. Retry in a few minutes.")
    except YTGAPIError as e:
        click.echo(f"[API ERROR] {e}", err=True)
        sys.exit(1)


@ytg.command(name='list-guides')
@click.option('--lang', default=None, help='Filter by language (e.g. fr)')
@click.option('--status', default=None, help='Filter by status (ready, in_progress, ...)')
def list_guides(lang, status):
    """
    Lists the YTG guides in the thematic-websites group.

    Lets you check the existing guides before creating new ones.
    """
    click.echo(f"\n[YTG] Guide list (groupId={YTGAnalyzer.DEFAULT_GROUP_ID})\n")

    analyzer = YTGAnalyzer()
    if not analyzer.is_configured:
        click.echo("[ERROR] YTG_API_KEY missing.", err=True)
        sys.exit(1)

    try:
        guides = analyzer.list_guides(
            group_id=YTGAnalyzer.DEFAULT_GROUP_ID,
            status=status,
        )
        if not guides:
            click.echo("No guide found.")
            return

        click.echo(f"{'ID':<12} {'Status':<14} {'Lang':<8} {'Query'}")
        click.echo("-" * 70)
        for g in guides:
            gid = str(g.get("id", "?"))
            if g.get("ready"):
                gstatus = "ready"
            elif g.get("inProgress"):
                gstatus = "in_progress"
            elif g.get("error"):
                gstatus = "error"
            else:
                gstatus = "waiting"
            glang = str(g.get("lang", "?"))
            query = str(g.get("query", g.get("keyword", "?")))
            click.echo(f"{gid:<12} {gstatus:<14} {glang:<8} {query}")

        click.echo(f"\nTotal: {len(guides)} guide(s)")
    except YTGAPIError as e:
        click.echo(f"[API ERROR] {e}", err=True)
        sys.exit(1)


@ytg.command(name='batch-prefetch')
@click.option('--spreadsheet-id', required=True, help='Google Sheet ID')
@blog_option()
@click.option('--lang', default='fr', show_default=True, help='Language of the guides')
@click.option('--country', default='fr', show_default=True, help='Country of the guides')
@click.option('--create-missing', is_flag=True, default=False,
              help='Create the missing guides (otherwise: match only)')
def batch_prefetch(spreadsheet_id, blog, lang, country, create_missing):
    """
    Matches column D of the spreadsheet (main_keyword) with the existing YTG guides.

    1. Downloads ALL the group's YTG guides in a single pass
    2. Reads the spreadsheet (col D = main_keyword) for each URL
    3. Maps locally: main_keyword == YTG query
    4. For each match → writes ytg_guide_id into audit_data.json
    5. With --create-missing: creates the missing guides

    Run it BEFORE cw batch audit-serp so that STEP 2.5 is a cache hit
    (< 1s) and does not impact the main workflow's runtime.
    """
    import glob
    from scripts.sheets.sheets_client import SheetsClient

    click.echo(f"\n[YTG] Batch prefetch - matching col D vs YTG guides")
    if blog:
        click.echo(f"Blog: {blog}")
    click.echo()

    analyzer = YTGAnalyzer()
    if not analyzer.is_configured:
        click.echo("[ERROR] YTG_API_KEY missing.", err=True)
        sys.exit(1)

    # ÉTAPE 1 : Télécharger TOUS les guides YTG en une seule passe
    click.echo("[1/3] Downloading YTG guides...")
    all_guides = analyzer.list_guides_all()
    query_index = analyzer.build_query_index(all_guides)
    click.echo(f"      {len(all_guides)} guides downloaded, index ready")
    click.echo()

    # ÉTAPE 2 : Lire les onglets RÉELS du blog pour récupérer les main_keywords.
    # ⚠️ L'ancien onglet "Refreshs_Audit" n'existe plus. On utilise le layout réel
    # par blog (défini dans keyword_resolver._SHEET_LAYOUT) : Enseigna → Avis/Versus/
    # "A ajouter" ; Superprof → "New Growing List".
    from scripts.audit.keyword_resolver import _SHEET_LAYOUT, _norm_url

    click.echo("[2/3] Reading the site's real tabs...")
    if not blog:
        click.echo("[ERROR] --site is required (real tabs differ per site).", err=True)
        sys.exit(1)
    layout = _SHEET_LAYOUT.get(blog)
    if not layout:
        click.echo(f"[ERROR] No known tab layout for site '{blog}'.", err=True)
        sys.exit(1)

    sheets = SheetsClient(spreadsheet_id=spreadsheet_id)
    sheet_rows = []
    seen_urls = set()
    for tab, url_idx, kw_idx in layout["tabs"]:
        try:
            data = sheets._read_sheet(tab)
        except Exception as e:
            click.echo(f"  [WARN] tab '{tab}' unreadable: {e}")
            continue
        if not data:
            continue
        for i, row in enumerate(data[1:], start=2):  # skip header
            if len(row) <= url_idx:
                continue
            row_url = row[url_idx].strip() if row[url_idx] else ""
            row_kw = row[kw_idx].strip() if len(row) > kw_idx and row[kw_idx] else ""
            if not row_kw or not row_url:
                continue
            u = _norm_url(row_url)
            if u in seen_urls:
                continue
            seen_urls.add(u)
            sheet_rows.append({
                "site_slug": blog,
                "url": row_url,
                "main_keyword": row_kw,
                "row_idx": i,
            })

    click.echo(f"      {len(sheet_rows)} URLs with a main_keyword")
    click.echo()

    # ÉTAPE 3 : Matching local + mise à jour audit_data.json
    click.echo("[3/3] Matching and updating audit_data.json...")
    context_dir = Path.cwd() / "_shared" / "context"

    matched = 0
    already_cached = 0
    created = 0
    missing = 0
    failed = 0

    for row in sheet_rows:
        kw = row["main_keyword"]
        kw_norm = kw.lower().strip()
        url = row["url"]

        # Trouver l'audit_data.json correspondant à cette URL
        audit_file = _find_audit_file(context_dir, url)

        # Vérifier si déjà en cache dans audit_data.json
        audit_data = {}
        if audit_file and audit_file.exists():
            try:
                with open(audit_file) as f:
                    audit_data = json.load(f)
            except Exception:
                pass

        if audit_data.get("ytg_guide_id"):
            already_cached += 1
            continue

        # Matching local dans l'index
        guide = query_index.get(kw_norm)

        if guide:
            guide_id = str(guide.get("id", ""))
            if not guide_id:
                continue

            # Guide trouvé et ready → fetch le détail pour les termes
            if guide.get("ready"):
                try:
                    raw = analyzer.get_guide_status(guide_id)
                    if raw and analyzer._is_ready(raw):
                        result = analyzer._parse_guide_result(guide_id, kw, raw)
                        _save_ytg_to_audit(audit_file, audit_data, result, url, row["site_slug"])
                        click.echo(
                            f"  [MATCH] {kw[:45]:<45} → guide {guide_id} "
                            f"({len(result.semantic_terms)} terms)"
                        )
                        matched += 1
                    else:
                        click.echo(f"  [WAIT]  {kw[:45]} guide {guide_id} not ready yet")
                        missing += 1
                except Exception as e:
                    click.echo(f"  [ERR]   {kw[:45]}: {e}", err=True)
                    failed += 1
            else:
                click.echo(f"  [WAIT]  {kw[:45]} guide {guide_id} still generating")
                missing += 1
        else:
            # Pas de guide existant
            if create_missing:
                click.echo(f"  [CREATE] {kw[:45]}...")
                try:
                    result = analyzer.create_and_wait(kw, language=lang, country=country)
                    if result:
                        _save_ytg_to_audit(audit_file, audit_data, result, url, row["site_slug"])
                        click.echo(
                            f"           OK - guide {result.guide_id} "
                            f"({len(result.semantic_terms)} terms, "
                            f"target SOSEO={result.top3_soseo:.0f}%)"
                        )
                        created += 1
                    else:
                        failed += 1
                except (YTGAPIError, YTGGuideTimeoutError) as e:
                    click.echo(f"           ERROR: {e}", err=True)
                    failed += 1
            else:
                click.echo(f"  [MISS]  {kw[:45]} - no guide (use --create-missing)")
                missing += 1

    click.echo()
    click.echo("[YTG] Summary:")
    click.echo(f"  Matched (audit_data updated): {matched}")
    click.echo(f"  Already cached              : {already_cached}")
    if create_missing:
        click.echo(f"  Created                     : {created}")
    click.echo(f"  Without guide               : {missing}")
    click.echo(f"  Errors                      : {failed}")


def _find_audit_file(context_dir: Path, url: str) -> Optional[Path]:
    """
    Cherche le fichier audit_data.json pour une URL donnée.

    Stratégie : slug de l'URL → répertoire dans _shared/context/.
    Ex: https://moments-yoga.fr/les-bienfaits-du-yoga
    → _shared/context/https_www_moments_yoga_fr_les_bienfaits_du_yoga/audit_data.json
    """
    import re
    # Slugifier l'URL comme le fait le projet
    slug = re.sub(r'[^a-z0-9]', '_', url.lower())
    slug = re.sub(r'_+', '_', slug).strip('_')
    candidate = context_dir / slug / "audit_data.json"
    if candidate.exists():
        return candidate
    # Recherche partielle si le slug exact ne correspond pas
    try:
        for d in context_dir.iterdir():
            if not d.is_dir():
                continue
            audit_file = d / "audit_data.json"
            if not audit_file.exists():
                continue
            # Vérifier l'URL dans le fichier
            try:
                with open(audit_file) as f:
                    data = json.load(f)
                if data.get("url", "") == url or data.get("blogpost_url", "") == url:
                    return audit_file
            except Exception:
                continue
    except Exception:
        pass
    return candidate  # Retourne le chemin calculé même s'il n'existe pas encore


def _save_ytg_to_audit(
    audit_file: Optional[Path],
    audit_data: dict,
    result,
    url: str,
    site_slug: str,
) -> None:
    """Écrit les données YTG dans audit_data.json (création si nécessaire)."""
    if not audit_file:
        return

    if not audit_data:
        audit_data = {"url": url, "site_slug": site_slug}

    audit_data["ytg_guide_id"] = result.guide_id
    audit_data["semantic_field_override"] = result.semantic_terms
    audit_data["ytg_competitor_targets"] = {
        "top3_soseo": result.top3_soseo,
        "top3_dseo": result.top3_dseo,
        "top10_soseo": result.top10_soseo,
        "top10_dseo": result.top10_dseo,
    }
    audit_data["ytg_term_colors"] = result.term_colors

    audit_file.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, ensure_ascii=False, indent=2)


@ytg.command(name='analyze')
@click.option('--guide-id', required=True, help='YTG guide ID')
@click.option('--html-file', required=True, type=click.Path(exists=True),
              help='HTML file to analyze')
def analyze(guide_id, html_file):
    """
    Analyzes an HTML file against an existing YTG guide.

    Shows the SOSEO and DSEO obtained for our content,
    compared to the TOP 3/TOP 10 averages.
    """
    click.echo(f"\n[YTG] Analyzing content against guide {guide_id}")
    click.echo(f"      File: {html_file}\n")

    analyzer = YTGAnalyzer()
    if not analyzer.is_configured:
        click.echo("[ERROR] YTG_API_KEY missing.", err=True)
        sys.exit(1)

    # Lire le contenu HTML et en extraire le texte
    try:
        from bs4 import BeautifulSoup
        with open(html_file, encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
    except Exception as e:
        click.echo(f"[ERROR] File read: {e}", err=True)
        sys.exit(1)

    try:
        result = analyzer.analyze_content(guide_id, text)
        if not result:
            click.echo("[ERROR] Analysis failed.", err=True)
            sys.exit(1)

        click.echo(f"Our content    - SOSEO: {result.get('our_soseo', 0):.1f}%  "
                   f"DSEO: {result.get('our_dseo', 0):.1f}%")

        colors = result.get("term_colors", {})
        if colors:
            blue = [t for t, c in colors.items() if c == "blue"]
            red = [t for t, c in colors.items() if c == "red"]
            orange = [t for t, c in colors.items() if c == "orange"]
            click.echo()
            if blue:
                click.echo(f"Under-optimized (blue) : {', '.join(blue[:10])}")
            if orange:
                click.echo(f"Heavily optim. (orange): {', '.join(orange[:10])}")
            if red:
                click.echo(f"Overdosed (red)        : {', '.join(red[:10])}")

    except YTGAPIError as e:
        click.echo(f"[API ERROR] {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# QC sémantique multi-blog (systématique avant intégration WP)
# ---------------------------------------------------------------------------

def _load_blog_ytg_config(site_slug: str) -> dict:
    """Lit le bloc `ytg` de _shared/config/blogs/{site_slug}.json (défaut si absent)."""
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent.parent
    from _shared.core.site_paths import SitePaths
    cfg_path = SitePaths(base_path=base).site_config(site_slug)
    if not cfg_path.exists():
        click.echo(f"[ERROR] Site config not found: {cfg_path}", err=True)
        sys.exit(1)
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f).get("ytg", {}) or {}


def _infer_url_from_html_path(site_slug: str, path) -> str:
    """Reconstitue une URL plausible depuis le nom de fichier (pour résoudre le KW)."""
    from pathlib import Path

    # Nom de fichier : `{slug}_refreshed.gutenberg.html` ou `{slug}_refreshed.html`.
    # .stem n'enlève qu'une extension → il faut retirer .gutenberg puis _refreshed.
    name = Path(path).name
    for suffix in (".gutenberg.html", ".html"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    slug = name.replace("_refreshed", "").replace("_", "-")
    domain_map = {
        "enseigna.fr": "https://enseigna.fr/{slug}/",
        "superprof.fr-ressources": "https://www.superprof.fr/ressources/{slug}/",
    }
    tpl = domain_map.get(site_slug, "https://example.com/{slug}/")
    return tpl.format(slug=slug)


@ytg.command(name='qc')
@blog_option(required=True, dest='site_slug')
@click.option('--slug', default='', help='Filter on a specific article slug')
@click.option('--main-keyword', '--keyword', 'keyword', default='',
              help='Forced main keyword (overrides the resolver). Requires --slug '
                   '(a single article): the YTG guide is created/resolved on this keyword. '
                   '--keyword = alias legacy.')
@click.option('--fix', is_flag=True, default=False,
              help='Flag NEEDS_FIX articles for targeted correction (corrector)')
@click.option('--json-out', 'json_out', is_flag=True, default=False,
              help='Write the summary report to sites/{site-slug}/outputs/ytg_qc_report.json')
def qc(site_slug, slug, keyword, fix, json_out):
    """
    YTG semantic QC on a site's generated HTML, BEFORE WP integration.

    For each article:
      1. Resolves the main keyword (Notion / Sheet / GSC / slug).
      2. Resolves or creates the YTG guide.
      3. Analyzes the HTML → SOSEO/DSEO vs TOP3 targets.
      4. Returns a verdict: OPTIMAL / NEEDS_FIX / BLOCKED / SKIP.
    """
    from scripts.audit.ytg_qc import (
        YTGQualityCheck,
        discover_generated_html,
        VERDICT_OPTIMAL,
        VERDICT_NEEDS_FIX,
        VERDICT_BLOCKED,
        VERDICT_SKIP,
    )
    from scripts.audit.ytg_corrector import RateLimiter

    ytg_cfg = _load_blog_ytg_config(site_slug)
    if ytg_cfg.get("enabled") is False:
        click.echo(f"[YTG QC] Disabled for '{site_slug}' (ytg.enabled=false). Nothing to do.")
        return

    analyzer = YTGAnalyzer()
    if not analyzer.is_configured:
        click.echo("[ERROR] YTG_API_KEY missing.", err=True)
        sys.exit(1)

    files = discover_generated_html(site_slug, slug_filter=slug)
    if not files:
        click.echo(f"[YTG QC] No generated HTML found for '{site_slug}'"
                   + (f" (slug '{slug}')" if slug else "") + ".")
        return

    # Un mot-clé forcé ne s'applique qu'à UN article (sinon le même KW serait
    # appliqué à tous → guide faux). On exige que le batch soit réduit à 1 fichier.
    keyword = (keyword or "").strip()
    if keyword and len(files) != 1:
        click.echo(
            f"[ERROR] --main-keyword requires targeting a single article "
            f"(use --slug). {len(files)} files currently match.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"\n[YTG QC] {site_slug} - {len(files)} article(s) to analyze\n")

    qc_engine = YTGQualityCheck(analyzer=analyzer, rate_limiter=RateLimiter())
    counts = {VERDICT_OPTIMAL: 0, VERDICT_NEEDS_FIX: 0, VERDICT_BLOCKED: 0, VERDICT_SKIP: 0}
    report = []
    to_fix = []

    for path in files:
        html = path.read_text(encoding="utf-8")
        url = _infer_url_from_html_path(site_slug, path)
        res = qc_engine.check_html(
            site_slug, url=url, html=html, ytg_config=ytg_cfg,
            main_keyword=keyword or None,
        )
        res.html_path = str(path)
        qc_engine.persist(res)

        counts[res.verdict] = counts.get(res.verdict, 0) + 1
        report.append(res.to_dict())

        icon = {
            VERDICT_OPTIMAL: "[OK]   ",
            VERDICT_NEEDS_FIX: "[FIX]  ",
            VERDICT_BLOCKED: "[BLOCK]",
            VERDICT_SKIP: "[SKIP] ",
        }.get(res.verdict, "[?]    ")
        click.echo(f"{icon} {path.stem[:50]:<50} {res.verdict}  {res.message}")
        if res.verdict == VERDICT_NEEDS_FIX and res.under_optimized_terms:
            click.echo(f"         to enrich: {', '.join(res.under_optimized_terms[:8])}")
        if res.verdict == VERDICT_NEEDS_FIX and res.over_optimized_terms:
            click.echo(f"         to reduce: {', '.join(res.over_optimized_terms[:8])}")
        if res.verdict == VERDICT_NEEDS_FIX:
            to_fix.append(res)

    click.echo()
    click.echo("[YTG QC] Summary:")
    click.echo(f"  OPTIMAL    : {counts[VERDICT_OPTIMAL]}")
    click.echo(f"  NEEDS_FIX : {counts[VERDICT_NEEDS_FIX]}")
    click.echo(f"  BLOCKED     : {counts[VERDICT_BLOCKED]}")
    click.echo(f"  SKIP       : {counts[VERDICT_SKIP]}")
    if ytg_cfg.get("gate"):
        click.echo(f"  [GATE active] {counts[VERDICT_NEEDS_FIX] + counts[VERDICT_BLOCKED]} article(s) "
                   "to review before WP push.")

    if json_out:
        from _shared.core.site_paths import SitePaths
        _root = Path(__file__).resolve().parent.parent.parent
        out = SitePaths(base_path=_root).output_dir(site_slug) / "ytg_qc_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        click.echo(f"\n[YTG QC] Report written: {out}")

    if fix and to_fix:
        from scripts.audit.ytg_autocorrect import YTGAutoCorrector

        click.echo(f"\n[YTG QC] --fix: preparing {len(to_fix)} correction(s)...")
        autocorrector = YTGAutoCorrector(
            site_slug, analyzer=analyzer, rate_limiter=RateLimiter()
        )
        items = [
            {
                "url": r.url,
                "html_path": r.html_path,
                "guide_id": r.guide_id,
                "targets": {"top3_soseo": r.target_soseo or 0, "top3_dseo": r.target_dseo or 0},
                "current_scores": {"soseo": r.our_soseo or 0, "dseo": r.our_dseo or 0},
            }
            for r in to_fix if r.guide_id and r.html_path
        ]
        tasks = autocorrector.prepare(items)
        if not tasks:
            click.echo("[YTG QC] No correction task prepared (per-term analysis failed).")
            return

        from _shared.core.site_paths import SitePaths
        manifest = (SitePaths(base_path=Path(__file__).resolve().parent.parent.parent)
                    .output_dir(site_slug) / "ytg_fix_manifest.json")
        click.echo(f"[YTG QC] {len(tasks)} correction task(s) ready.")
        click.echo(f"[YTG QC] Manifest: {manifest}")
        click.echo(
            "[YTG QC] The correction is applied by the Claude Code sub-agents "
            "(Max plan): each sub-agent reads its prompt, rewrites the HTML and writes "
            "the `_corrected.html` to disk. Re-validation (assets + SOSEO/DSEO) "
            "is then automatic via YTGAutoCorrector.revalidate()."
        )
