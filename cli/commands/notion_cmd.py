"""
Commandes Notion.

Usage:
    cw notion sync [--blog moments-yoga]
    cw notion check-title --blog moments-yoga --title "Les bienfaits du yoga"
    cw notion list-sujets [--blog moments-yoga]
    cw notion create-sujet --blog moments-yoga --title "Nouveau sujet" --db-id ABC123
"""

import json
import sys
from pathlib import Path

import click
from cli.options import blog_option

from scripts.notion import NotionClient


def _load_db_id(blog_id: str, db_type: str) -> str:
    """Charge le DB ID Notion depuis sites.json."""
    sites_path = Path.cwd() / "_shared" / "config" / "sites.json"
    if not sites_path.exists():
        return ""
    try:
        with open(sites_path) as f:
            data = json.load(f)
        for site in data.get("sites", []):
            if site.get("id") == blog_id:
                key = f"notion_{db_type}_db_id"
                return site.get(key, "") or ""
    except Exception:
        return ""
    return ""


@click.group()
def notion():
    """Intégration Notion — commandes et sujets."""
    pass


@notion.command(name='sync')
@blog_option()
@click.option('--db-id', help='ID de la base Notion Commandes (override sites.json)')
def sync(blog, db_id):
    """
    Affiche un résumé des commandes Notion par blog.

    Lit la base "Commandes" Notion et affiche le nombre d'articles
    par statut et par blog.
    """
    click.echo(f"\n[Notion] Synchronisation commandes")
    if blog:
        click.echo(f"Blog: {blog}")
    click.echo()

    client = NotionClient()
    if not client.is_configured:
        click.echo(
            "[ERREUR] NOTION_TOKEN manquant. Ajouter dans .env ou "
            "~/.credentials/notion/credentials.json",
            err=True
        )
        sys.exit(1)

    # Déterminer le DB ID
    database_id = db_id
    if not database_id and blog:
        database_id = _load_db_id(blog, "commandes")

    if not database_id:
        click.echo(
            "[ERREUR] DB ID manquant. Fournir --db-id ou configurer "
            "notion_commandes_db_id dans _shared/config/sites.json",
            err=True
        )
        sys.exit(1)

    commandes = client.get_commandes(database_id, blog_id=blog)

    # Résumé par statut
    by_status: dict[str, int] = {}
    by_blog: dict[str, int] = {}
    for c in commandes:
        by_status[c.status or "inconnu"] = by_status.get(c.status or "inconnu", 0) + 1
        by_blog[c.blog_id or "inconnu"] = by_blog.get(c.blog_id or "inconnu", 0) + 1

    click.echo(f"Total articles : {len(commandes)}")
    click.echo()
    click.echo("Par statut :")
    for status, count in sorted(by_status.items()):
        click.echo(f"  {status:<20} {count}")
    click.echo()
    click.echo("Par blog :")
    for b, count in sorted(by_blog.items()):
        click.echo(f"  {b:<25} {count}")


@notion.command(name='check-title')
@blog_option(required=True)
@click.option('--title', required=True, help='Titre à vérifier')
@click.option('--db-id', help='ID de la base Notion Commandes (override sites.json)')
@click.option('--threshold', default=0.85, show_default=True,
              help='Seuil de similarité Jaccard (0.0-1.0)')
def check_title(blog, title, db_id, threshold):
    """
    Vérifie si un titre existe déjà dans les commandes Notion.

    Utilise un match exact puis un match normalisé (sans accents) puis
    la similarité Jaccard sur les mots.
    """
    click.echo(f"\n[Notion] Vérification titre : '{title}'")
    click.echo(f"Blog: {blog} | Seuil: {threshold}\n")

    client = NotionClient()
    if not client.is_configured:
        click.echo("[ERREUR] NOTION_TOKEN manquant.", err=True)
        sys.exit(1)

    database_id = db_id or _load_db_id(blog, "commandes")
    if not database_id:
        click.echo("[ERREUR] DB ID manquant (notion_commandes_db_id dans sites.json).", err=True)
        sys.exit(1)

    commandes = client.get_commandes(database_id, blog_id=blog)
    match = client.find_title_match(commandes, title, threshold=threshold)

    if match:
        click.echo(f"[MATCH TROUVE]")
        click.echo(f"  Titre existant : {match.title}")
        click.echo(f"  URL            : {match.url or 'N/A'}")
        click.echo(f"  Statut         : {match.status or 'N/A'}")
        click.echo(f"  Date           : {match.date or 'N/A'}")
        click.echo(f"\n  → Attention : cannibalisation potentielle avec cet article.")
    else:
        click.echo(f"[OK] Aucun article similaire trouvé dans les {len(commandes)} commandes.")


@notion.command(name='list-sujets')
@blog_option()
@click.option('--db-id', required=True, help='ID de la base Notion Sujets')
def list_sujets(blog, db_id):
    """
    Liste les sujets à traiter depuis la base Notion.

    Affiche les topics non encore traités avec leur priorité.
    """
    click.echo(f"\n[Notion] Sujets à traiter")
    if blog:
        click.echo(f"Blog: {blog}")
    click.echo()

    client = NotionClient()
    if not client.is_configured:
        click.echo("[ERREUR] NOTION_TOKEN manquant.", err=True)
        sys.exit(1)

    sujets = client.get_sujets(db_id, blog_id=blog)

    if not sujets:
        click.echo("Aucun sujet trouvé.")
        return

    click.echo(f"{len(sujets)} sujets trouvés :\n")
    for s in sujets:
        priority_icon = {"high": "!!!", "medium": " ! ", "low": "   "}.get(
            (s.priority or "").lower(), "   "
        )
        click.echo(
            f"  [{priority_icon}] {s.title:<50} "
            f"| {s.blog_id or '?':<20} | {s.status or '?'}"
        )


@notion.command(name='create-sujet')
@blog_option(required=True)
@click.option('--title', required=True, help='Titre du sujet')
@click.option('--db-id', required=True, help='ID de la base Notion Sujets')
@click.option('--category', default='', help='Catégorie thématique')
@click.option('--priority', default='medium',
              type=click.Choice(['high', 'medium', 'low']),
              show_default=True, help='Priorité')
def create_sujet(blog, title, db_id, category, priority):
    """
    Crée un nouveau sujet dans la base Notion.

    Utile pour enregistrer manuellement un topic découvert
    lors d'une analyse de contenu ou de recherche de mots-clés.
    """
    click.echo(f"\n[Notion] Création sujet : '{title}'")
    click.echo(f"Blog: {blog} | Priorité: {priority}\n")

    client = NotionClient()
    if not client.is_configured:
        click.echo("[ERREUR] NOTION_TOKEN manquant.", err=True)
        sys.exit(1)

    page = client.create_sujet(
        database_id=db_id,
        title=title,
        blog_id=blog,
        category=category,
        priority=priority,
    )

    if page:
        page_id = page.get("id", "?")
        click.echo(f"[OK] Sujet créé — page_id: {page_id}")
    else:
        click.echo("[ERREUR] Création échouée.", err=True)
        sys.exit(1)


@notion.command(name='sync-sites')
@click.option('--apply', 'do_apply', is_flag=True, default=False,
              help='Écrit sites.json (sinon dry-run diff).')
@click.option('--dump-schema', 'dump_schema', is_flag=True, default=False,
              help='Affiche les propriétés réelles de la base Notion « config pays ».')
def sync_sites(do_apply, dump_schema):
    """Sync unidirectionnel : page Notion « config pays » → sites.json.

    Notion (édité par les humains) est la source ; sites.json en est la projection
    machine. Le moteur ne lit jamais Notion au runtime. Merge additif, dry-run par
    défaut. Nécessite un NOTION_TOKEN valide dans .env.
    """
    from scripts.notion.sync_sites_from_notion import main as sync_main
    argv = []
    if do_apply:
        argv.append('--apply')
    if dump_schema:
        argv.append('--dump-schema')
    # Le module lit sys.argv via argparse ; on le pilote directement.
    import sys as _sys
    old = _sys.argv
    _sys.argv = ['sync_sites_from_notion'] + argv
    try:
        code = sync_main()
    finally:
        _sys.argv = old
    if code:
        sys.exit(code)
