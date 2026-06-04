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
@click.option('--blog', required=True, help='Blog ID (enseigna, moments-yoga, etc.)')
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
            main_keyword=keyword or "",
        )

        context_dir = orchestrator._prepare_context_for_claude_code(
            original_html=clean_body,
            action=result.action_taken,
            row=row,
            extraction_result=fetch_result
        )

        # Compose generation prompt via ghostwriter
        click.echo("[6/6] Composition prompt de génération...")
        output_dir = Path.cwd() / "_shared" / "outputs" / blog
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
            click.echo(f"  Assets avant: {generation_info['metadata'].get('assets_before', {})}")
            click.echo(f"  Temps total:  {result.execution_time_seconds:.1f}s")
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
