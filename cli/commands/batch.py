"""
Commandes de traitement batch.

Usage:
    cw batch keyword-discovery [--blog enseigna]
    cw batch audit-gsc [--blog enseigna] [--limit 10]
    cw batch audit-serp [--blog enseigna]
    cw batch decision [--blog enseigna]
    cw batch refresh --action FULL_REFRESH [--blog enseigna]
    cw batch workflow-auto [--blog enseigna] [--no-auto-refresh]
"""

import click
from pathlib import Path

from scripts.agent import RefreshOrchestrator


@click.group()
def batch():
    """Traitement batch depuis Google Sheets."""
    pass


@batch.command(name='keyword-discovery')
@click.option('--spreadsheet-id', required=True, help='Google Sheet ID')
@click.option('--blog', help='Filtrer par blog_id')
def keyword_discovery(spreadsheet_id, blog):
    """
    STEP 0: Keyword Discovery.

    Remplit main_keyword (col D) pour les URLs où il est vide.
    Cascade: ranked_keywords (vol>=50) → GSC → suggestions (vol>=100) → related_keywords → slug.
    """
    click.echo(f"\n🔍 STEP 0: KEYWORD DISCOVERY")
    if blog:
        click.echo(f"Blog: {blog}")
    click.echo()

    orchestrator = RefreshOrchestrator(
        base_path=Path.cwd(),
        spreadsheet_id=spreadsheet_id
    )

    click.echo("Découverte des mots-clés manquants...")
    try:
        results = orchestrator.batch_keyword_discovery(blog_id=blog)

        click.echo(f"\n📊 RÉSULTATS:")
        click.echo(f"  Traités:     {results['processed']}")
        click.echo(f"  DataForSEO:  {results['dataforseo']}")
        click.echo(f"  GSC:         {results['gsc']}")
        click.echo(f"  Slug:        {results['slug']}")
        click.echo(f"  Échecs:      {results['failed']}")

        if results.get('failed') > 0:
            click.echo(f"\n  ⚠ Erreurs:")
            for error in results.get('errors', [])[:5]:
                click.echo(f"    - {error}")

        click.echo(f"\n✅ Keyword Discovery terminé")

    except Exception as e:
        click.echo(f"\n❌ ERREUR: {str(e)}", err=True)
        raise click.Abort()


@batch.command(name='keyword-refresh')
@click.option('--spreadsheet-id', required=True, help='Google Sheet ID')
@click.option('--blog', help='Filtrer par blog_id')
@click.option('--min-volume', default=10, type=int, show_default=True, help='Volume minimum accepté (keywords en-dessous seront re-cherchés)')
def keyword_refresh(spreadsheet_id, blog, min_volume):
    """
    Re-vérifie et améliore les keywords existants avec volume insuffisant.

    Pour chaque ligne avec un main_keyword déjà rempli :
    - Vérifie le volume via DataForSEO keyword_overview
    - Si volume < MIN_VOLUME, relance la cascade de découverte
    - Met à jour le spreadsheet si un meilleur keyword est trouvé

    Utile pour corriger les keywords avec 0-10 volume ou non indexés Ahrefs.
    """
    click.echo(f"\n🔄 KEYWORD REFRESH (seuil volume: {min_volume})")
    if blog:
        click.echo(f"Blog: {blog}")
    click.echo()

    orchestrator = RefreshOrchestrator(
        base_path=Path.cwd(),
        spreadsheet_id=spreadsheet_id
    )

    click.echo(f"Re-vérification des mots-clés existants (volume < {min_volume})...")
    try:
        results = orchestrator.batch_keyword_re_discovery(
            min_volume=min_volume,
            blog_id=blog,
        )

        click.echo(f"\n📊 RÉSULTATS:")
        click.echo(f"  Traités:        {results['processed']}")
        click.echo(f"  Volume faible:  {results['low_volume']}")
        click.echo(f"  Mis à jour:     {results['updated']}")
        click.echo(f"  Inchangés:      {results['unchanged']}")

        if results.get('errors'):
            click.echo(f"\n  ⚠ Erreurs ({len(results['errors'])}):")
            for error in results['errors'][:5]:
                click.echo(f"    - {error}")

        click.echo(f"\n✅ Keyword Refresh terminé")

    except Exception as e:
        click.echo(f"\n❌ ERREUR: {str(e)}", err=True)
        raise click.Abort()


@batch.command(name='audit-gsc')
@click.option('--spreadsheet-id', required=True, help='Google Sheet ID')
@click.option('--blog', help='Filtrer par blog_id')
@click.option('--limit', type=int, help='Limite du nombre d\'URLs')
def audit_gsc(spreadsheet_id, blog, limit):
    """
    Batch Audit GSC.

    Récupère données GSC pour toutes les URLs en attente.
    """
    click.echo(f"\n📊 BATCH AUDIT GSC")
    if blog:
        click.echo(f"Blog: {blog}")
    if limit:
        click.echo(f"Limit: {limit}")
    click.echo()

    # Init orchestrator
    orchestrator = RefreshOrchestrator(
        base_path=Path.cwd(),
        spreadsheet_id=spreadsheet_id
    )

    # Run batch audit GSC
    click.echo("Exécution batch audit GSC...")
    try:
        results = orchestrator.batch_audit_gsc(blog_id=blog)

        click.echo(f"\n📊 RÉSULTATS:")
        click.echo(f"  Traités:  {results['processed']}")
        click.echo(f"  Succès:   {results['success']}")
        click.echo(f"  Échecs:   {results['failed']}")

        if results.get('failed') > 0:
            click.echo(f"\n  ⚠ Erreurs:")
            for error in results.get('errors', [])[:5]:
                click.echo(f"    - {error}")

        click.echo(f"\n✅ Batch GSC terminé")

    except Exception as e:
        click.echo(f"\n❌ ERREUR: {str(e)}", err=True)
        raise click.Abort()


@batch.command(name='audit-serp')
@click.option('--spreadsheet-id', required=True, help='Google Sheet ID')
@click.option('--blog', help='Filtrer par blog_id')
def audit_serp(spreadsheet_id, blog):
    """
    Batch Audit SERP.

    Récupère PAA et secondary keywords pour toutes les URLs.
    """
    click.echo(f"\n📊 BATCH AUDIT SERP")
    if blog:
        click.echo(f"Blog: {blog}")
    click.echo()

    # Init orchestrator
    orchestrator = RefreshOrchestrator(
        base_path=Path.cwd(),
        spreadsheet_id=spreadsheet_id
    )

    # Run batch audit SERP
    click.echo("Exécution batch audit SERP...")
    try:
        results = orchestrator.batch_audit_serp(blog_id=blog)

        click.echo(f"\n📊 RÉSULTATS:")
        click.echo(f"  Traités:  {results['processed']}")
        click.echo(f"  Succès:   {results['success']}")
        click.echo(f"  Échecs:   {results['failed']}")

        if results.get('failed') > 0:
            click.echo(f"\n  ⚠ Erreurs:")
            for error in results.get('errors', [])[:5]:
                click.echo(f"    - {error}")

        click.echo(f"\n✅ Batch SERP terminé")

    except Exception as e:
        click.echo(f"\n❌ ERREUR: {str(e)}", err=True)
        raise click.Abort()


@batch.command()
@click.option('--spreadsheet-id', required=True, help='Google Sheet ID')
@click.option('--blog', help='Filtrer par blog_id')
def decision(spreadsheet_id, blog):
    """
    Batch Decision.

    Prend des décisions de stratégie pour toutes les URLs auditées.
    """
    click.echo(f"\n🎯 BATCH DECISION")
    if blog:
        click.echo(f"Blog: {blog}")
    click.echo()

    # Init orchestrator
    orchestrator = RefreshOrchestrator(
        base_path=Path.cwd(),
        spreadsheet_id=spreadsheet_id
    )

    # Run batch decision
    click.echo("Exécution batch decision...")
    try:
        results = orchestrator.batch_decision(blog_id=blog)

        click.echo(f"\n📊 RÉSULTATS:")
        click.echo(f"  NO ACTION:        {results['no_action']}")
        click.echo(f"  PARTIAL REFRESH:  {results['partial_refresh']}")
        click.echo(f"  REFRESH TITLES:   {results['refresh_titles']}")
        click.echo(f"  FULL REFRESH:     {results['full_refresh']}")

        click.echo(f"\n✅ Batch decision terminé")

    except Exception as e:
        click.echo(f"\n❌ ERREUR: {str(e)}", err=True)
        raise click.Abort()


@batch.command()
@click.option('--spreadsheet-id', required=True, help='Google Sheet ID')
@click.option('--action', required=True,
              type=click.Choice(['PARTIAL_REFRESH', 'REFRESH_TITLES', 'FULL_REFRESH']),
              help='Type de refresh')
@click.option('--blog', help='Filtrer par blog_id')
@click.option('--limit', type=int, help='Limite du nombre d\'URLs à traiter')
def refresh(spreadsheet_id, action, blog, limit):
    """
    Batch Refresh.

    Génère le contenu pour toutes les URLs avec l'action spécifiée.
    """
    click.echo(f"\n✍️  BATCH REFRESH")
    click.echo(f"Action: {action}")
    if blog:
        click.echo(f"Blog:   {blog}")
    if limit:
        click.echo(f"Limit:  {limit}")
    click.echo()

    # Init orchestrator
    orchestrator = RefreshOrchestrator(
        base_path=Path.cwd(),
        spreadsheet_id=spreadsheet_id
    )

    # Run batch refresh
    click.echo("Exécution batch refresh...")
    try:
        results = orchestrator.batch_refresh(action=action, blog_id=blog, limit=limit)

        click.echo(f"\n📊 RÉSULTATS:")
        click.echo(f"  Traités:         {results['processed']}")
        click.echo(f"  Succès:          {results['success']}")
        click.echo(f"  Assets restaurés: {results.get('assets_restored', 0)}")

        if results.get('failed') > 0:
            click.echo(f"  Échecs:          {results['failed']}")
            click.echo(f"\n  ⚠ Erreurs:")
            for error in results.get('errors', [])[:5]:
                click.echo(f"    - {error}")

        click.echo(f"\n✅ Batch refresh terminé")

    except Exception as e:
        click.echo(f"\n❌ ERREUR: {str(e)}", err=True)
        raise click.Abort()


@batch.command(name='workflow-auto')
@click.option('--spreadsheet-id', required=True, help='Google Sheet ID')
@click.option('--blog', help='Filtrer par blog_id')
@click.option('--auto-refresh/--no-auto-refresh', default=True,
              help='Auto-exécuter les refreshs (défaut: oui)')
def workflow_auto(spreadsheet_id, blog, auto_refresh):
    """
    Workflow automatisé complet.

    Exécute GSC → SERP → Decision → Refresh automatiquement.
    """
    click.echo(f"\n🚀 WORKFLOW AUTOMATISÉ COMPLET")
    if blog:
        click.echo(f"Blog: {blog}")
    click.echo(f"Auto-refresh: {'OUI' if auto_refresh else 'NON'}")
    click.echo()

    # Init orchestrator
    orchestrator = RefreshOrchestrator(
        base_path=Path.cwd(),
        spreadsheet_id=spreadsheet_id
    )

    # Run workflow auto
    click.echo("Exécution workflow automatisé...")
    try:
        results = orchestrator.batch_workflow_auto(
            blog_id=blog,
            auto_refresh=auto_refresh
        )

        # Display summary
        click.echo(f"\n{'='*70}")
        click.echo(f"📊 RÉSUMÉ DU WORKFLOW")
        click.echo(f"{'='*70}")

        if results["step1_audit_gsc"]:
            gsc = results['step1_audit_gsc']
            click.echo(f"Step 1 (GSC):   {gsc['success']} succès / {gsc['failed']} échecs")

        if results["step2_audit_serp"]:
            serp = results['step2_audit_serp']
            click.echo(f"Step 2 (SERP):  {serp['success']} succès / {serp['failed']} échecs")

        if results["step3_decision"]:
            dec = results["step3_decision"]
            click.echo(f"Step 3 (Decision):")
            click.echo(f"  - NO ACTION:      {dec['no_action']}")
            click.echo(f"  - PARTIAL REFRESH: {dec['partial_refresh']}")
            click.echo(f"  - REFRESH TITLES:  {dec['refresh_titles']}")
            click.echo(f"  - FULL REFRESH:    {dec['full_refresh']}")

        if results["step4_refresh"]:
            click.echo(f"Step 4 (Refresh): {len(results['step4_refresh'])} actions exécutées")

        click.echo(f"⏱️  Durée totale: {results['total_duration_seconds']:.1f}s")
        click.echo(f"{'='*70}\n")

        click.echo(f"✅ Workflow automatisé terminé")

    except Exception as e:
        click.echo(f"\n❌ ERREUR: {str(e)}", err=True)
        raise click.Abort()


@batch.command(name='benchmark')
@click.option('--blog', required=True, help='Blog ID (ex: superprof-ressources)')
@click.option('--source-sheet', default='GSC_Perfs',
              help="Nom de l'onglet contenant les URLs (défaut: GSC_Perfs)")
@click.option('--rows', default='2:16',
              help='Plage de lignes 1-indexées, format a:b (défaut: 2:16 = 15 URLs)')
@click.option('--spreadsheet-id', default=None,
              help="Spreadsheet ID (override sinon lu depuis la config du blog)")
def benchmark(blog, source_sheet, rows, spreadsheet_id):
    """
    Benchmark pipeline mécanique (fetch + audit GSC + décision + sheets + contexte).

    Lit des URLs depuis un onglet/plage, exécute le pipeline automatisé pour chaque
    URL, et produit un rapport de timing (console + JSON).

    NB: La génération LLM effective est out-of-process (Claude Code opérateur).
    Ce benchmark couvre uniquement la partie automatisée.

    Exemple:
      cw batch benchmark --blog superprof-ressources --source-sheet GSC_Perfs --rows 2:16
    """
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from scripts.agent.benchmark_runner import run_benchmark

    click.echo(f"\n🧪 BENCHMARK PIPELINE MÉCANIQUE")
    click.echo(f"Blog:          {blog}")
    click.echo(f"Source sheet:  {source_sheet}")
    click.echo(f"Row range:     {rows}")
    click.echo()

    try:
        report = run_benchmark(
            blog_id=blog,
            source_sheet=source_sheet,
            row_range=rows,
            spreadsheet_id=spreadsheet_id,
        )
    except Exception as e:
        click.echo(f"\n❌ ERREUR: {str(e)}", err=True)
        raise click.Abort()

    if any(not t.success for t in report.timers):
        raise click.exceptions.Exit(1)


@batch.command(name='extract-tables')
@click.option('--site-id', default='superprof-ressources', show_default=True,
              help='Identifiant du blog (ex: superprof-ressources, enseigna.fr)')
@click.option('--input-dir', type=click.Path(exists=True, file_okay=False, path_type=Path),
              default=None, help='Dossier HTML source (défaut: _shared/outputs/{site_id}/html/)')
@click.option('--output-dir', type=click.Path(file_okay=False, path_type=Path),
              default=None, help='Dossier CSV destination (défaut: _shared/outputs/{site_id}/csv/)')
@click.option('--file', 'single_file', type=click.Path(exists=True, dir_okay=False, path_type=Path),
              default=None,
              help="Ne traiter qu'un seul fichier *_refreshed.html (chemin exact), au lieu de scanner --input-dir")
def extract_tables(site_id, input_dir, output_dir, single_file):
    """Extrait les tableaux HTML des articles en fichiers CSV pour TablePress.

    Sans --file : scanne récursivement tous les *_refreshed.html du dossier
    source (y compris sous-dossiers) et génère un CSV par tableau trouvé.
    Avec --file : ne traite que ce fichier précis (utilisé en fin de Phase 2,
    juste après la génération d'un article, pour garantir l'extraction sans
    dépendre d'un scan global).

    Exemple:
      cw batch extract-tables --site-id superprof-ressources
      cw batch extract-tables --site-id superprof-ressources --file _shared/outputs/superprof-ressources/html/mon-article_refreshed.html
    """
    import logging
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    from scripts.utils.table_csv_extractor import extract_tables_to_csv

    from _shared.core.tenant_paths import TenantPaths
    base_dir = TenantPaths(base_path=Path(__file__).parents[2]).output_dir(site_id)
    html_dir = input_dir or base_dir / "html"
    csv_dir = output_dir or base_dir / "csv"

    if single_file:
        html_files = [single_file]
    else:
        if not html_dir.exists():
            click.echo(f"Dossier introuvable : {html_dir}", err=True)
            raise click.Abort()
        html_files = sorted(html_dir.rglob("*_refreshed.html"))
        if not html_files:
            click.echo(f"Aucun fichier *_refreshed.html trouvé dans {html_dir}")
            return

    click.echo(f"\nExtraction CSV — {site_id}")
    click.echo(f"Destination : {csv_dir}")
    click.echo(f"Fichiers à traiter : {len(html_files)}\n")

    total_tables = 0
    files_with_tables = 0
    files_without_tables = 0

    for html_file in html_files:
        html_content = html_file.read_text(encoding="utf-8")
        file_slug = html_file.stem.removesuffix("_refreshed")
        csv_files = extract_tables_to_csv(html_content, csv_dir, file_slug)

        if csv_files:
            files_with_tables += 1
            total_tables += len(csv_files)
            click.echo(f"  ✓ {file_slug} → {len(csv_files)} tableau(x)")
        else:
            files_without_tables += 1
            click.echo(f"  - {file_slug} → 0 tableau (aucune balise <table>)")

    click.echo(f"\nRésultat : {total_tables} tableaux extraits "
               f"({files_with_tables} articles avec tableaux, "
               f"{files_without_tables} sans tableau)")
