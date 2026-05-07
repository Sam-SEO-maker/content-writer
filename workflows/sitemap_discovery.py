#!/usr/bin/env python3
"""
Sitemap Discovery Tool

Auto-découvre les URLs à auditer depuis les sitemaps des blogs.

Fonctionnalités :
1. Détecte les nouvelles URLs publiées depuis le dernier crawl
2. Identifie les URLs obsolètes (> X mois sans mise à jour)
3. Priorise les URLs selon lastmod
4. Exporte vers Google Sheets pour traitement par le workflow

Usage:
    # Découvrir les nouvelles URLs pour un blog
    python sitemap_discovery.py --blog enseigna.fr --detect-new

    # Trouver le contenu obsolète (> 6 mois)
    python sitemap_discovery.py --blog enseigna.fr --find-stale --months 6

    # Exporter vers Google Sheets
    python sitemap_discovery.py --blog enseigna.fr --find-stale --export-to-sheets

    # Tous les blogs d'un coup
    python sitemap_discovery.py --all-blogs --find-stale --months 12
"""

import argparse
import sys
import io
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Force UTF-8 encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from scripts.sitemap.config_adapter import load_analyzer_from_blog_config, load_fetcher_from_blog_config
from scripts.sheets import SheetsClient
from _shared.core.models import StaleContent


# Blog IDs valides (CLAUDE.md multi-tenant architecture)
VALID_BLOGS = [
    "enseigna.fr",
    "superprof.fr",
]


def discover_new_urls(blog_id: str) -> Dict:
    """
    Découvre les nouvelles URLs publiées depuis le dernier crawl.

    Args:
        blog_id: Identifiant du blog

    Returns:
        {
            "new_urls": List[str],
            "removed_urls": List[str],
            "total_current": int,
            "total_previous": int
        }
    """
    print(f"\n📡 Découverte nouvelles URLs pour {blog_id}...")

    try:
        # Nettoyer le blog_id (retirer .fr/.com si présent)
        blog_id_clean = blog_id.replace(".fr", "").replace(".com", "")
        fetcher = load_fetcher_from_blog_config(blog_id_clean)
        result = fetcher.fetch_and_detect_new(force_refresh=True)

        print(f"  ✅ URLs actuelles: {result.total_current}")
        print(f"  📊 URLs précédentes: {result.total_previous}")
        print(f"  🆕 Nouvelles URLs: {len(result.new_urls)}")
        print(f"  ❌ URLs supprimées: {len(result.removed_urls)}")

        if result.new_urls:
            print(f"\n  Exemples de nouvelles URLs:")
            for url_obj in result.new_urls[:5]:
                lastmod = url_obj.lastmod or "Non spécifié"
                print(f"    • {url_obj.loc}")
                print(f"      Lastmod: {lastmod}")

        return {
            "new_urls": [url.loc for url in result.new_urls],
            "removed_urls": result.removed_urls,
            "total_current": result.total_current,
            "total_previous": result.total_previous
        }

    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return {
            "new_urls": [],
            "removed_urls": [],
            "total_current": 0,
            "total_previous": 0
        }


def find_stale_content(blog_id: str, months: int = 6, min_priority: int = 3) -> List[StaleContent]:
    """
    Identifie les URLs obsolètes nécessitant un refresh.

    Args:
        blog_id: Identifiant du blog
        months: Nombre de mois pour considérer le contenu obsolète
        min_priority: Priorité minimale (1-5)

    Returns:
        Liste de StaleContent triée par priorité
    """
    print(f"\n🔍 Recherche contenu obsolète pour {blog_id} (> {months} mois)...")

    try:
        # Nettoyer le blog_id (retirer .fr/.com si présent)
        blog_id_clean = blog_id.replace(".fr", "").replace(".com", "")
        analyzer = load_analyzer_from_blog_config(blog_id_clean)
        stale = analyzer.find_stale_content(
            months=months,
            min_priority=min_priority,
            force_refresh=True
        )

        print(f"  ✅ URLs obsolètes trouvées: {len(stale)}")

        if stale:
            # Statistiques par priorité
            priority_counts = {}
            for item in stale:
                priority_counts[item.refresh_priority] = priority_counts.get(item.refresh_priority, 0) + 1

            print(f"\n  📊 Répartition par priorité:")
            for priority in sorted(priority_counts.keys(), reverse=True):
                count = priority_counts[priority]
                stars = "⭐" * priority
                print(f"    {stars} Priorité {priority}: {count} URLs")

            print(f"\n  Top 10 URLs à refresh en priorité:")
            for i, item in enumerate(stale[:10], 1):
                days = item.days_since_update
                days_str = f"{days} jours" if days >= 0 else "Date inconnue"
                priority_stars = "⭐" * item.refresh_priority
                print(f"    {i}. {priority_stars} {item.url}")
                print(f"       Âge: {days_str}")

        return stale

    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return []


def export_to_sheets(
    blog_id: str,
    stale_content: List[StaleContent],
    spreadsheet_id: str,
    dry_run: bool = False
) -> int:
    """
    Exporte les URLs obsolètes vers Google Sheets pour audit.

    Args:
        blog_id: Identifiant du blog
        stale_content: Liste des URLs obsolètes
        spreadsheet_id: ID du Google Sheet
        dry_run: Si True, simule l'export sans écrire

    Returns:
        Nombre d'URLs exportées
    """
    print(f"\n📤 Export vers Google Sheets (Spreadsheet: {spreadsheet_id})...")

    if not stale_content:
        print("  ⚠️  Aucune URL à exporter")
        return 0

    if dry_run:
        print(f"  🔍 MODE DRY-RUN: Simulation d'export de {len(stale_content)} URLs")
        print(f"  Les URLs seraient ajoutées dans la feuille 'Refreshs_Audit'")
        print(f"  Colonnes remplies: blog_id, blogpost_url, status, main_keyword")
        return len(stale_content)

    try:
        sheets = SheetsClient(spreadsheet_id)

        # TODO: Implémenter l'ajout batch dans SheetsClient
        # Pour l'instant, affiche les données qui seraient ajoutées

        print(f"  ℹ️  Fonctionnalité d'export direct en cours d'implémentation")
        print(f"  En attendant, voici les données à ajouter manuellement:")
        print(f"\n  Format CSV pour import:")
        print(f"  blog_id,blogpost_url,status,main_keyword")

        for item in stale_content[:50]:  # Limite à 50 pour affichage
            # Extraire un mot-clé approximatif du slug
            keyword = item.slug.replace("-", " ") if item.slug else ""
            print(f"  {blog_id},{item.url},à_faire,{keyword}")

        if len(stale_content) > 50:
            print(f"  ... et {len(stale_content) - 50} URLs supplémentaires")

        return len(stale_content)

    except Exception as e:
        print(f"  ❌ Erreur lors de l'export: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Sitemap Discovery Tool - Auto-découverte d'URLs à auditer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Découvrir nouvelles URLs
  python sitemap_discovery.py --blog enseigna.fr --detect-new

  # Trouver contenu obsolète (> 6 mois)
  python sitemap_discovery.py --blog enseigna.fr --find-stale --months 6

  # Avec priorité haute uniquement
  python sitemap_discovery.py --blog enseigna.fr --find-stale --min-priority 4

  # Exporter vers Google Sheets (dry-run)
  python sitemap_discovery.py --blog superprof.fr --find-stale --export-to-sheets --dry-run

  # Tous les blogs d'un coup
  python sitemap_discovery.py --all-blogs --find-stale --months 12
        """
    )

    # Blog selection
    blog_group = parser.add_mutually_exclusive_group(required=True)
    blog_group.add_argument(
        "--blog",
        choices=VALID_BLOGS,
        help="Identifiant du blog"
    )
    blog_group.add_argument(
        "--all-blogs",
        action="store_true",
        help="Traiter tous les blogs"
    )

    # Actions
    parser.add_argument(
        "--detect-new",
        action="store_true",
        help="Détecter les nouvelles URLs depuis le dernier crawl"
    )
    parser.add_argument(
        "--find-stale",
        action="store_true",
        help="Trouver le contenu obsolète nécessitant un refresh"
    )

    # Options stale content
    parser.add_argument(
        "--months",
        type=int,
        default=6,
        help="Nombre de mois pour considérer le contenu obsolète (défaut: 6)"
    )
    parser.add_argument(
        "--min-priority",
        type=int,
        choices=[1, 2, 3, 4, 5],
        default=3,
        help="Priorité minimale à inclure (1-5, défaut: 3)"
    )

    # Export
    parser.add_argument(
        "--export-to-sheets",
        action="store_true",
        help="Exporter les résultats vers Google Sheets"
    )
    parser.add_argument(
        "--spreadsheet-id",
        default="1F99FtN8fWQlQm0ZTJphBRz_c64iDs2DvohyHyM2Tk1M",
        help="ID du Google Spreadsheet (défaut: spreadsheet principal)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode dry-run: simule les actions sans modifier les données"
    )

    args = parser.parse_args()

    # Validation
    if not args.detect_new and not args.find_stale:
        parser.error("Au moins une action requise: --detect-new ou --find-stale")

    # Déterminer la liste des blogs
    blogs = [args.blog] if args.blog else VALID_BLOGS

    print("="*70)
    print("SITEMAP DISCOVERY TOOL")
    print("="*70)
    print(f"Blogs: {', '.join(blogs)}")
    print(f"Actions: {', '.join([a for a in ['detect-new' if args.detect_new else None, 'find-stale' if args.find_stale else None] if a])}")
    print("="*70)

    all_stale = []

    for blog_id in blogs:
        print(f"\n{'='*70}")
        print(f"📍 BLOG: {blog_id}")
        print(f"{'='*70}")

        # Action 1: Détecter nouvelles URLs
        if args.detect_new:
            discover_new_urls(blog_id)

        # Action 2: Trouver contenu obsolète
        if args.find_stale:
            stale = find_stale_content(blog_id, args.months, args.min_priority)
            all_stale.extend([(blog_id, item) for item in stale])

    # Export global
    if args.export_to_sheets and all_stale:
        print(f"\n{'='*70}")
        print("📤 EXPORT GLOBAL")
        print(f"{'='*70}")

        # Grouper par blog
        by_blog = {}
        for blog_id, item in all_stale:
            if blog_id not in by_blog:
                by_blog[blog_id] = []
            by_blog[blog_id].append(item)

        total_exported = 0
        for blog_id, items in by_blog.items():
            print(f"\n  📍 {blog_id}: {len(items)} URLs")
            exported = export_to_sheets(blog_id, items, args.spreadsheet_id, args.dry_run)
            total_exported += exported

        print(f"\n  ✅ Total exporté: {total_exported} URLs")

    print(f"\n{'='*70}")
    print("✅ TERMINÉ")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
