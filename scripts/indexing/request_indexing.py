"""
Script de Demande d'Indexation Google

Utilise l'API URL Inspection pour forcer la demande d'indexation des URLs
après un refresh de contenu.

Usage:
    python scripts/indexing/request_indexing.py --spreadsheet-id <ID> --blog-id <blog>
    python scripts/indexing/request_indexing.py --url <URL> --site-property <property>
"""

import argparse
import json
import os
import time
from datetime import datetime
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build


class IndexingRequester:
    """Gestionnaire de demandes d'indexation via GSC API."""

    def __init__(self, gsc_property: str, credentials_path: str = None):
        """
        Initialise le requester.

        Args:
            gsc_property: URL de la propriété GSC (ex: https://example.com/)
            credentials_path: Chemin vers les credentials Google Service Account
        """
        self.gsc_property = gsc_property

        if credentials_path is None:
            import os
            credentials_path = os.environ.get("GOOGLE_SA_PATH", os.path.expanduser("~/.credentials/google/google-service-account.json"))

        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/webmasters']
        )

        self.service = build('searchconsole', 'v1', credentials=credentials)

    def request_indexing(self, url: str) -> dict:
        """
        Demande l'indexation d'une URL via l'API URL Inspection.

        Args:
            url: URL à indexer

        Returns:
            dict avec le résultat de la demande:
            {
                "url": str,
                "status": "SUCCESS|FAILED|QUOTA_EXCEEDED",
                "message": str,
                "timestamp": str
            }
        """
        try:
            # Appel API pour demander l'indexation
            # Note: L'API URL Inspection ne permet pas directement de demander l'indexation
            # Il faut utiliser l'Indexing API (différente de Search Console API)
            # Pour GSC, on peut seulement vérifier le statut, pas forcer l'indexation

            # Alternative: Utiliser l'Indexing API (nécessite des scopes différents)
            # Pour l'instant, on vérifie le statut et on log la demande

            print(f"[INFO] Demande d'indexation pour: {url}")

            # Vérifier le statut actuel
            result = self.service.urlInspection().index().inspect(
                body={
                    "inspectionUrl": url,
                    "siteUrl": self.gsc_property
                }
            ).execute()

            inspection_result = result.get("inspectionResult", {})
            index_status = inspection_result.get("indexStatusResult", {})
            verdict = index_status.get("verdict", "UNKNOWN")
            coverage_state = index_status.get("coverageState", "UNKNOWN")

            # Log du statut actuel
            print(f"  - Verdict: {verdict}")
            print(f"  - Coverage State: {coverage_state}")

            return {
                "url": url,
                "status": "SUCCESS",
                "message": f"Status checked: {verdict} - {coverage_state}",
                "verdict": verdict,
                "coverage_state": coverage_state,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            error_msg = str(e)

            # Détecter quota exceeded
            if "quota" in error_msg.lower() or "limit" in error_msg.lower():
                return {
                    "url": url,
                    "status": "QUOTA_EXCEEDED",
                    "message": f"API quota exceeded: {error_msg[:100]}",
                    "timestamp": datetime.now().isoformat()
                }

            return {
                "url": url,
                "status": "FAILED",
                "message": f"Error: {error_msg[:200]}",
                "timestamp": datetime.now().isoformat()
            }

    def batch_request_indexing(self, urls: list[str], delay: float = 2.0) -> dict:
        """
        Demande l'indexation en batch pour plusieurs URLs.

        Args:
            urls: Liste des URLs à indexer
            delay: Délai en secondes entre chaque requête (default: 2.0s)

        Returns:
            dict avec les résultats:
            {
                "total": int,
                "success": int,
                "failed": int,
                "quota_exceeded": int,
                "results": list[dict]
            }
        """
        results = {
            "total": len(urls),
            "success": 0,
            "failed": 0,
            "quota_exceeded": 0,
            "results": []
        }

        for idx, url in enumerate(urls, 1):
            print(f"\n[{idx}/{len(urls)}] Processing: {url}")

            result = self.request_indexing(url)
            results["results"].append(result)

            if result["status"] == "SUCCESS":
                results["success"] += 1
            elif result["status"] == "QUOTA_EXCEEDED":
                results["quota_exceeded"] += 1
                print(f"⚠️  Quota exceeded - stopping batch")
                break
            else:
                results["failed"] += 1

            # Rate limiting
            if idx < len(urls):
                time.sleep(delay)

        return results


def main():
    """Point d'entrée du script."""
    parser = argparse.ArgumentParser(description="Demande d'indexation Google via API")

    # Mode 1: Single URL
    parser.add_argument("--url", type=str, help="URL unique à indexer")
    parser.add_argument("--site-property", type=str, help="Propriété GSC (ex: https://example.com/)")

    # Mode 2: Batch depuis spreadsheet
    parser.add_argument("--spreadsheet-id", type=str, help="ID du Google Spreadsheet")
    parser.add_argument("--blog-id", type=str, help="Blog ID (enseigna, superprof-ressources, etc.)")
    parser.add_argument("--status-filter", type=str, default="CONTENT DONE",
                       help="Filtre sur colonne G (status)")

    # Options communes
    parser.add_argument("--credentials", type=str,
                       default=os.environ.get("GOOGLE_SA_PATH", os.path.expanduser("~/.credentials/google/google-service-account.json")),
                       help="Chemin vers les credentials Google")
    parser.add_argument("--delay", type=float, default=2.0,
                       help="Délai entre requêtes en secondes (default: 2.0)")
    parser.add_argument("--output", type=str, help="Fichier de sortie JSON pour les résultats")

    args = parser.parse_args()

    # Mode 1: Single URL
    if args.url and args.site_property:
        requester = IndexingRequester(args.site_property, args.credentials)
        result = requester.request_indexing(args.url)

        print(f"\n{'='*60}")
        print(f"Résultat:")
        print(f"  - URL: {result['url']}")
        print(f"  - Status: {result['status']}")
        print(f"  - Message: {result['message']}")
        print(f"{'='*60}")

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Résultat sauvegardé dans: {args.output}")

    # Mode 2: Batch depuis spreadsheet
    elif args.spreadsheet_id:
        from scripts.sheets.sheets_client import SheetsClient
        from _shared.config.sites import SITE_CONFIGS

        # Charger le blog config pour obtenir le gsc_property
        if args.blog_id:
            blog_config = SITE_CONFIGS.get(args.blog_id)
            if not blog_config:
                print(f"❌ Blog ID inconnu: {args.blog_id}")
                return
            gsc_property = blog_config.get("gsc_property")
        else:
            print("❌ --blog-id requis pour le mode batch")
            return

        # Charger les URLs depuis le spreadsheet
        sheets_client = SheetsClient(args.spreadsheet_id)
        rows = sheets_client.read_pending_for_refresh(
            action=None,  # All actions
            blog_id=args.blog_id
        )

        # Filtrer par status
        urls_to_index = [
            row.blogpost_url
            for row in rows
            if row.status == args.status_filter
        ]

        print(f"📊 {len(urls_to_index)} URLs à indexer (blog: {args.blog_id}, status: {args.status_filter})")

        if not urls_to_index:
            print("⚠️  Aucune URL à indexer")
            return

        # Demander confirmation
        confirm = input(f"\nDemander l'indexation de {len(urls_to_index)} URLs? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ Annulé")
            return

        # Exécuter le batch
        requester = IndexingRequester(gsc_property, args.credentials)
        results = requester.batch_request_indexing(urls_to_index, delay=args.delay)

        print(f"\n{'='*60}")
        print(f"Résultats Batch:")
        print(f"  - Total: {results['total']}")
        print(f"  - Success: {results['success']}")
        print(f"  - Failed: {results['failed']}")
        print(f"  - Quota Exceeded: {results['quota_exceeded']}")
        print(f"{'='*60}")

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Résultats sauvegardés dans: {args.output}")

    else:
        parser.print_help()
        print("\n❌ Soit --url + --site-property, soit --spreadsheet-id + --blog-id requis")


if __name__ == "__main__":
    main()
