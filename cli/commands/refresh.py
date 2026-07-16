"""
Commandes de refresh pour une URL unique.

Usage:
    cw refresh <url> --blog enseigna [--strategy FULL_REFRESH]
"""

import os
import click
from pathlib import Path
from dataclasses import dataclass

from scripts.agent import RefreshOrchestrator
from cli.options import blog_option


@dataclass
class MinimalRow:
    """Minimal row object for standalone refresh (no spreadsheet)."""
    blog_id: str
    blogpost_url: str
    title: str = ""
    main_keyword: str = ""
    post_type: str = "STANDALONE"
    impressions_30d: int = 0
    clicks_30d: int = 0
    ctr_30d: float = 0.0
    people_also_ask: str = ""
    secondary_keywords: str = ""


@click.command()
@click.argument('url')
@blog_option(required=True)
@click.option('--spreadsheet-id', default=lambda: os.environ.get('SPREADSHEET_ID'), help='Google Sheet ID (auto depuis .env)')
@click.option('--strategy',
              type=click.Choice([
                  'TITLE_OPTIMIZATION',
                  'PARTIAL_REFRESH',
                  'FULL_REFRESH',
                  'SEMANTIC_REORIENTATION',
                  'FORMAT_ADAPTATION',
                  'EEAT_REWRITE'
              ]),
              help='Force une stratégie spécifique')
@click.option('--keyword', help='Mot-clé principal (force analyse SERP)')
@click.option('--debug', is_flag=True, help='Mode debug avec traceback complet')
def refresh(url, blog, spreadsheet_id, strategy, keyword, debug):
    """
    Refresh une URL unique.

    Exécute le workflow complet :
    - Scraping HTML
    - Audit éditorial
    - Analyse GSC/SERP
    - Décision stratégie
    - Préparation contexte + prompt de génération
    """
    import traceback

    click.echo(f"\n{'='*70}")
    click.echo(f"🔄 REFRESH URL")
    click.echo(f"{'='*70}")
    click.echo(f"URL:      {url}")
    click.echo(f"Blog:     {blog}")
    if strategy:
        click.echo(f"Stratégie: {strategy} (forcée)")
    if keyword:
        click.echo(f"Mot-clé:  {keyword}")
    click.echo()

    # Init orchestrator
    click.echo("[1/6] Initialisation orchestrator...")
    orchestrator = RefreshOrchestrator(
        base_path=Path.cwd(),
        spreadsheet_id=spreadsheet_id
    )

    # Fetch content via WP API (ou HTTP scraping fallback)
    click.echo("[2/6] Récupération contenu...")
    fetch_result = orchestrator._fetch_html(url, blog_id=blog)
    if not fetch_result.get("clean_body"):
        click.echo("  ✗ Impossible de récupérer le contenu", err=True)
        raise click.Abort()
    method = fetch_result["extraction_metadata"].get("method_used", "unknown")
    click.echo(f"  ✓ Contenu récupéré via {method} ({len(fetch_result['clean_body'])} chars)")

    # Process URL (audit + decision)
    click.echo("[3/6] Audit + décision stratégie...")
    try:
        result = orchestrator.process_url(
            url=url,
            blog_id=blog,
            html_content=fetch_result["clean_body"],
            force_action=strategy,
            custom_prompt=None,
            provided_keyword=keyword
        )

        click.echo(f"  Action:      {result.action_taken}")
        click.echo(f"  Audit score: {result.audit_score}")

        if result.errors:
            click.echo(f"  ⚠ Erreurs ({len(result.errors)}):")
            for error in result.errors[:3]:
                click.echo(f"    - {error[:100]}")

        if result.action_taken == "BLOCKED_QUALITY_ISSUES":
            click.echo("\n❌ Quality Gate a bloqué le refresh")
            click.echo("Consultez le rapport éditorial pour détails")
            return

        if result.action_taken in ("NO_ACTION", "ERROR", "REDIRECT_301_SUGGESTED"):
            click.echo(f"\n⚠ Action '{result.action_taken}' - pas de génération nécessaire")
            return

        # Assets déjà extraits par _fetch_html()
        click.echo("[4/6] Extraction contenu + assets...")
        clean_body = fetch_result["clean_body"]
        asset_counts = fetch_result["assets_baseline"].get("counts", {})
        click.echo(f"  ✓ Body: {len(clean_body)} chars")
        click.echo(f"  ✓ Images: {asset_counts.get('images', 0)}, "
                    f"Tables: {asset_counts.get('tables', 0)}, "
                    f"Links: {asset_counts.get('internal_links', 0)}")

        # Extract title from article HTML
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(fetch_result["full_html"], 'html.parser')
        h1_tag = soup.find('h1')
        title = h1_tag.get_text(strip=True) if h1_tag else ""

        # Prepare context directory
        click.echo("[5/6] Préparation contexte pour génération...")
        row = MinimalRow(
            blog_id=blog,
            blogpost_url=url,
            title=title,
            main_keyword=keyword or result.main_keyword or "",
            # PAA / secondary keywords issus de l'audit SERP live (DataForSEO),
            # sans quoi le contexte de génération part sans questions SERP.
            people_also_ask=result.people_also_ask or "",
            secondary_keywords=result.secondary_keywords or "",
        )

        # Propager le guide YTG calculé au STEP 2.5 de process_url : sans ça, les
        # termes sémantiques n'atteignent jamais generation_prompt.txt (le guide
        # serait créé puis jeté). Clés attendues par _prepare_context_for_claude_code.
        ytg_data = None
        if result.ytg_guide_id or result.ytg_semantic_field:
            ytg_data = {
                "ytg_guide_id": result.ytg_guide_id,
                "semantic_field_override": result.ytg_semantic_field,
                "ytg_competitor_targets": result.ytg_competitor_targets,
                "ytg_term_colors": result.ytg_term_colors,
            }
            click.echo(f"  YTG: guide {result.ytg_guide_id}, "
                       f"{len(result.ytg_semantic_field)} termes → prompt")

        context_dir = orchestrator._prepare_context_for_claude_code(
            original_html=clean_body,
            action=result.action_taken,
            row=row,
            extraction_result=fetch_result,
            ytg_data=ytg_data,
        )

        # Compose generation prompt via ghostwriter
        click.echo("[6/6] Composition prompt de génération...")
        from _shared.core.tenant_paths import TenantPaths
        output_dir = TenantPaths(base_path=Path.cwd()).output_dir(blog)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "html").mkdir(parents=True, exist_ok=True)
        (output_dir / "json").mkdir(parents=True, exist_ok=True)

        generation_info = orchestrator.ghostwriter.generate_from_context(
            context_dir=context_dir,
            output_dir=output_dir,
            blog_id=blog
        )

        if generation_info["status"] == "ready_for_generation":
            # Save composed prompt
            prompt_file = context_dir / "generation_prompt.txt"
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(generation_info["generation_prompt"])

            click.echo(f"\n{'='*70}")
            click.echo(f"✅ CONTEXTE PRÊT POUR GÉNÉRATION")
            click.echo(f"{'='*70}")
            click.echo(f"  Context dir:  {context_dir}")
            click.echo(f"  Prompt:       {prompt_file}")
            click.echo(f"  Output HTML:  {generation_info['output_files']['html']}")
            click.echo(f"  Output JSON:  {generation_info['output_files']['metadata']}")
            click.echo(f"  Strategy:     {generation_info['metadata']['strategy']}")
            _art = generation_info['metadata'].get('article_type')
            if _art:
                click.echo(f"  Type:         {_art}  (finalize --type {_art} → html/{_art}/)")
            click.echo(f"  Assets avant: {generation_info['metadata'].get('assets_before', {})}")
            # Mot-clé + guide YTG : à reporter dans `finalize --keyword/--guide-id`
            # pour que le QC post-génération score sur le bon guide (pas le slug).
            _kw = keyword or result.main_keyword or ""
            if _kw:
                click.echo(f"  Mot-clé:      {_kw}")
            if result.ytg_guide_id:
                click.echo(f"  YTG guide:    {result.ytg_guide_id}")
            click.echo(f"  Temps total:  {result.execution_time_seconds:.1f}s")

            # QC sémantique YTG : le HTML n'est pas encore généré à ce stade
            # (génération LLM déléguée hors process). On lance le QC seulement si
            # un HTML généré existe déjà (cas d'un re-run après génération),
            # sinon on rappelle la commande à lancer après génération.
            _maybe_run_ytg_qc(
                blog, url,
                main_keyword=keyword or result.main_keyword or "",
                guide_id=result.ytg_guide_id,
            )
        else:
            click.echo(f"\n⚠ Erreur composition prompt: {generation_info.get('error', 'unknown')}")

    except Exception as e:
        if debug:
            click.echo(f"\n❌ ERREUR:", err=True)
            click.echo(traceback.format_exc(), err=True)
        else:
            click.echo(f"\n❌ ERREUR: {str(e)[:200]}", err=True)
            click.echo("(Utilisez --debug pour le traceback complet)")
        raise click.Abort()


def _maybe_run_ytg_qc(blog_id: str, url: str,
                      main_keyword: str = "", guide_id: str = "") -> None:
    """
    Lance le QC sémantique YTG sur l'article si un HTML généré existe déjà.

    Dans le flux `cw refresh`, la génération LLM est déléguée hors process : à la
    fin de la commande, le HTML n'existe généralement pas encore. On ne peut donc
    analyser que si un `_refreshed.html` correspondant est déjà présent (re-run).
    Sinon on rappelle la commande à lancer après la génération.
    """
    from scripts.audit.ytg_qc import (
        YTGQualityCheck,
        discover_generated_html,
        url_to_context_slug,
        VERDICT_OPTIMAL,
        VERDICT_A_CORRIGER,
        VERDICT_BLOQUE,
    )

    slug = url.strip("/").split("/")[-1]
    files = discover_generated_html(blog_id, slug_filter=slug)
    if not files:
        click.echo("\n[YTG QC] HTML pas encore généré — lancer APRÈS génération :")
        click.echo(f"         cw ytg qc --blog {blog_id} --slug {slug}")
        return

    # Charger le bloc ytg de la config blog
    import json
    from _shared.core.tenant_paths import TenantPaths
    cfg_path = TenantPaths(base_path=Path.cwd()).blog_config(blog_id)
    ytg_cfg = {}
    if cfg_path.exists():
        try:
            ytg_cfg = json.loads(cfg_path.read_text(encoding="utf-8")).get("ytg", {}) or {}
        except Exception:
            ytg_cfg = {}
    if ytg_cfg.get("enabled") is False:
        return

    click.echo("\n[YTG QC] HTML généré détecté — analyse sémantique…")
    try:
        engine = YTGQualityCheck()
        html = files[0].read_text(encoding="utf-8")
        res = engine.check_html(
            blog_id, url=url, html=html, ytg_config=ytg_cfg,
            main_keyword=main_keyword or "", guide_id=guide_id or "",
        )
        res.html_path = str(files[0])
        engine.persist(res)
        click.echo(f"[YTG QC] Verdict: {res.verdict} — {res.message}")
        if res.verdict == VERDICT_A_CORRIGER and res.under_optimized_terms:
            click.echo(f"[YTG QC] À enrichir : {', '.join(res.under_optimized_terms[:8])}")
        if ytg_cfg.get("gate") and res.verdict in (VERDICT_A_CORRIGER, VERDICT_BLOQUE):
            click.echo("[YTG QC] ⚠ GATE actif : article à revoir avant push WP.")
    except Exception as e:
        click.echo(f"[YTG QC] Non-bloquant, erreur ignorée: {str(e)[:120]}")
