"""
Commandes de workflow complet.

Usage:
    cw workflow run <url> --blog enseigna [--row 3]
"""

import os
import click
from pathlib import Path

import requests
from scripts.agent import RefreshOrchestrator
from scripts.sheets import SheetsClient


@click.group()
def workflow():
    """Workflow complet avec mise à jour spreadsheet."""
    pass


@workflow.command()
@click.argument('url')
@click.option('--blog', required=True, help='Blog ID')
@click.option('--spreadsheet-id', default=lambda: os.environ.get('SPREADSHEET_ID'), help='Google Sheet ID (auto depuis .env)')
@click.option('--row', type=int, help='Numéro de ligne dans le spreadsheet')
def run(url, blog, spreadsheet_id, row):
    """
    Lance le workflow complet pour une URL.

    Équivalent à run_workflow_parcoursup.py.
    Exécute tous les steps + mise à jour spreadsheet.
    """
    click.echo(f"\n{'='*70}")
    click.echo(f"🚀 WORKFLOW COMPLET")
    click.echo(f"{'='*70}")
    click.echo(f"URL:         {url}")
    click.echo(f"Blog:        {blog}")
    if spreadsheet_id:
        click.echo(f"Spreadsheet: {spreadsheet_id}")
    if row:
        click.echo(f"Ligne:       {row}")
    click.echo()

    # Init orchestrator
    click.echo("[1/5] Initialisation orchestrator...")
    orchestrator = RefreshOrchestrator(
        base_path=Path.cwd(),
        spreadsheet_id=spreadsheet_id
    )

    # Init sheets client
    if spreadsheet_id:
        sheets_client = SheetsClient(spreadsheet_id)
    else:
        sheets_client = None

    # Fetch content via direct HTTP scraping
    click.echo("[2/5] Récupération contenu par scraping HTTP...")
    try:
        resp = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ContentWriter/1.0)"},
            allow_redirects=True,
        )
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        click.echo(f"  ✗ Impossible de récupérer le contenu: {e}", err=True)
        raise click.Abort()
    click.echo(f"  ✓ HTML récupéré: {len(html)} chars")

    # Process URL avec workflow complet
    click.echo("[3/5] Exécution workflow complet (Ingest + Editorial Audit + Audit + Decision)...")

    try:
        result = orchestrator.process_url(
            url=url,
            blog_id=blog,
            html_content=html,
            force_action=None,
            custom_prompt=None,
            provided_keyword=None
        )

        click.echo(f"\n[4/5] Résultats workflow:")
        click.echo(f"  Success:       {result.success}")
        click.echo(f"  Action:        {result.action_taken}")
        click.echo(f"  Audit score:   {result.audit_score}")
        click.echo(f"  Assets valid:  {result.assets_valid}")
        click.echo(f"  Temps:         {result.execution_time_seconds:.1f}s")

        if result.errors:
            click.echo(f"  ⚠ Erreurs ({len(result.errors)}):")
            for error in result.errors[:3]:
                click.echo(f"    - {error[:100]}")

        # Vérifier spreadsheet
        if sheets_client:
            click.echo("\n[5/5] Vérification spreadsheet...")
            row_index = sheets_client._find_url_row(url, sheets_client.SHEET_REFRESHS_AUDIT)

            if row_index:
                click.echo(f"  ✓ URL trouvée dans spreadsheet (ligne {row_index})")
                click.echo(f"  Colonnes mises à jour:")
                click.echo(f"    - X (editorial_audit_score)")
                click.echo(f"    - Y (editorial_audit_date)")
                click.echo(f"    - Z (editorial_verdict)")
                click.echo(f"    - AA (blocking_issues_count)")
                click.echo(f"    - AB (editorial_audit_report_url)")
                if result.action_taken == "BLOCKED_QUALITY_ISSUES":
                    click.echo(f"    - G (status) = 'blocked_quality_issues'")
                    click.echo(f"    - V (error_message) = détails blocage")
            else:
                click.echo(f"  ⚠ URL non trouvée dans spreadsheet")
                click.echo(f"  L'audit éditorial a été exécuté mais colonnes non mises à jour")
        else:
            click.echo("\n[5/5] Pas de spreadsheet configuré (skip)")

        click.echo(f"\n{'='*70}")
        click.echo("WORKFLOW TERMINÉ")
        click.echo(f"{'='*70}\n")

        if result.action_taken == "BLOCKED_QUALITY_ISSUES":
            click.echo("❌ Quality Gate a bloqué le refresh")
            click.echo("Consultez le rapport éditorial pour détails:")
            click.echo(f"  tenants/{blog}/outputs/editorial_audits/")
        else:
            click.echo("✅ Workflow complété avec succès")

    except Exception as e:
        click.echo(f"\n❌ ERREUR: {str(e)[:200]}", err=True)
        import traceback
        traceback.print_exc()
        raise click.Abort()
