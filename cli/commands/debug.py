"""
Commandes de debug.

Usage:
    cw debug workflow <url> --blog enseigna
    cw debug config [--blog enseigna]
    cw debug extract-structures --spreadsheet-id <ID>
"""

import os
import click
import traceback
from pathlib import Path

import requests
from scripts.agent import RefreshOrchestrator
from _shared.config.sites import SITE_CONFIGS


@click.group()
def debug():
    """Utilitaires de debug."""
    pass


@debug.command()
@click.argument('url')
@click.option('--blog', required=True, help='Blog ID')
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
              default='FULL_REFRESH',
              help='Stratégie forcée (défaut: FULL_REFRESH)')
def workflow(url, blog, spreadsheet_id, strategy):
    """
    Debug workflow complet avec traceback.

    Migre debug_workflow.py
    Exécute le workflow avec affichage complet des erreurs.
    """
    click.echo(f"\n{'='*70}")
    click.echo(f"🐛 DEBUG WORKFLOW")
    click.echo(f"{'='*70}")
    click.echo(f"URL:       {url}")
    click.echo(f"Blog:      {blog}")
    click.echo(f"Stratégie: {strategy}")
    click.echo()

    # Init orchestrator
    click.echo("[1/3] Initialisation orchestrator...")
    orchestrator = RefreshOrchestrator(
        base_path=Path.cwd(),
        spreadsheet_id=spreadsheet_id
    )

    # Fetch content via direct HTTP scraping
    click.echo("[2/3] Récupération contenu par scraping HTTP...")
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
    click.echo(f"  ✓ HTML récupéré ({len(html)} chars)")

    # Process URL
    click.echo("[3/3] Exécution workflow avec debug complet...")
    try:
        result = orchestrator.process_url(
            url=url,
            blog_id=blog,
            html_content=html,
            force_action=strategy,
            custom_prompt=None,
            provided_keyword=None
        )

        click.echo(f"\n✅ SUCCESS:")
        click.echo(f"  URL:           {result.url}")
        click.echo(f"  Success:       {result.success}")
        click.echo(f"  Action:        {result.action_taken}")
        click.echo(f"  Audit score:   {result.audit_score}")
        click.echo(f"  Assets valid:  {result.assets_valid}")
        click.echo(f"  Temps:         {result.execution_time_seconds:.1f}s")

        if result.errors:
            click.echo(f"\n  ⚠ Erreurs ({len(result.errors)}):")
            for error in result.errors:
                click.echo(f"    - {error}")

    except Exception as e:
        click.echo(f"\n❌ ERROR CAUGHT:")
        click.echo(f"Type:    {type(e).__name__}")
        click.echo(f"Message: {str(e)}")
        click.echo(f"\nFULL TRACEBACK:")
        traceback.print_exc()
        raise click.Abort()


@debug.command()
@click.option('--blog', help='Blog ID (optionnel, affiche config spécifique)')
@click.option('--show-all', is_flag=True, help='Afficher tous les blogs')
def config(blog, show_all):
    """
    Affiche la configuration.

    Vérifie les configs chargées depuis _shared/config/sites.py
    """
    click.echo(f"\n🔧 CONFIGURATION")

    if blog:
        # Afficher config d'un blog spécifique
        blog_config = SITE_CONFIGS.get(blog)
        if not blog_config:
            click.echo(f"❌ Blog ID inconnu: {blog}", err=True)
            raise click.Abort()

        click.echo(f"\nBlog: {blog}")
        click.echo(f"{'='*70}")
        click.echo(f"Domain:        {blog_config.get('domain')}")
        click.echo(f"GSC Property:  {blog_config.get('gsc_property')}")
        click.echo(f"Spreadsheet:   {blog_config.get('sheet_id') or blog_config.get('sheets_config', {}).get('spreadsheet_id')}")
        click.echo(f"YMYL:          {blog_config.get('ymyl_level')}")
        click.echo(f"E-E-A-T:       {blog_config.get('eeat_level')}")

    elif show_all:
        # Afficher tous les blogs
        click.echo(f"\nTous les blogs:")
        click.echo(f"{'='*70}")
        for blog_id, config in SITE_CONFIGS.items():
            click.echo(f"\n{blog_id}:")
            click.echo(f"  Domain:  {config.get('domain')}")
            click.echo(f"  YMYL:    {config.get('ymyl_level')}")
            click.echo(f"  E-E-A-T: {config.get('eeat_level')}")

    else:
        # Afficher résumé
        click.echo(f"\nBlogs configurés: {len(SITE_CONFIGS)}")
        for blog_id in SITE_CONFIGS.keys():
            click.echo(f"  - {blog_id}")

        click.echo(f"\nUtilisez --blog <ID> pour voir la config détaillée")
        click.echo(f"Utilisez --show-all pour voir toutes les configs")


@debug.command(name='extract-structures')
@click.option('--spreadsheet-id', required=True, help='Google Sheet ID')
def extract_structures(spreadsheet_id):
    """
    Extrait les structures H1/H2 de toutes les URLs.

    Génère articles_structure_*.json pour analyse.
    """
    import json
    from datetime import datetime
    from scripts.sheets import SheetsClient
    from scripts.audit import HTMLAnalyzer

    click.echo(f"\n📚 EXTRACTION STRUCTURES H1/H2")
    click.echo(f"Spreadsheet: {spreadsheet_id}\n")

    # Read spreadsheet
    click.echo("[1/3] Lecture spreadsheet...")
    sheets_client = SheetsClient(spreadsheet_id)
    sheet_data = sheets_client._read_sheet('Refreshs_Audit')

    articles = []
    for i, row in enumerate(sheet_data[1:], start=2):
        if len(row) > 4:
            url = row[2] if len(row) > 2 else None
            blog_id = row[0] if len(row) > 0 else None
            title = row[4] if len(row) > 4 else ""

            if url and blog_id:
                articles.append({
                    'row': i,
                    'url': url,
                    'blog_id': blog_id,
                    'title': title
                })

    click.echo(f"  ✓ {len(articles)} URLs trouvées")

    # Fetch and extract structures
    click.echo("[2/3] Extraction structures H1/H2...")
    analyzer = HTMLAnalyzer()

    for idx, article in enumerate(articles, 1):
        url = article['url']
        click.echo(f"  [{idx}/{len(articles)}] {url[:60]}...")

        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
            html = resp.text if resp.ok else None
            if html:
                audit = analyzer.analyze_html(html, url)
                article['h1'] = audit.h1_title
                article['h2s'] = audit.h2_sections
            else:
                article['h1'] = ""
                article['h2s'] = []
        except Exception as e:
            click.echo(f"    ⚠ Erreur: {str(e)[:60]}")
            article['h1'] = ""
            article['h2s'] = []

    # Save to JSON
    click.echo("[3/3] Sauvegarde JSON...")
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_file = outputs_dir / f"articles_structure_{timestamp}.json"

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    click.echo(f"  ✓ Fichier créé: {json_file}")
    click.echo(f"\n✅ Extraction terminée")
    click.echo(f"Fichier de structures généré: {json_file}")
