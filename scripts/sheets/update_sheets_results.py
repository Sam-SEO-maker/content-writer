#!/usr/bin/env python3
"""
Met à jour la feuille Refresh_Results avec les articles rédigés.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from scripts.sheets.sheets_client import SheetsClient, RefreshResultRow

SPREADSHEET_ID = "1F99FtN8fWQlQm0ZTJphBRz_c64iDs2DvohyHyM2Tk1M"


def main():
    print("Mise à jour de Refresh_Results...")

    client = SheetsClient(SPREADSHEET_ID)

    if client._sheets_service is None:
        print("ERREUR: Impossible de se connecter à Google Sheets")
        return

    # Article 1
    result1 = RefreshResultRow(
        url="https://enseigna.fr/apprendre-anglais-au-royaume-uni/",
        refresh_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        rewrite_type="FULL_REFRESH",
        new_title="Cours d'anglais au Royaume-Uni : le guide complet pour apprendre en 2026",
        new_meta="Vous souhaitez prendre des cours d'anglais au Royaume-Uni ? Durée, meilleures villes, types de séjours et budget : guide complet 2026 pour apprendre l'anglais en Angleterre.",
        sections_modified=5,
        word_count_before=3046,
        word_count_after=1800,
        images_before=10,
        images_after=10,
        links_before=56,
        links_after=12,
        validation_passed=True,
        validation_errors="",
        content_preview="Prendre des cours d'anglais au Royaume-Uni reste en 2026 l'une des méthodes les plus efficaces pour progresser rapidement. Selon une étude du British Council (2025)...",
        full_content_link="outputs/enseigna/2026-02-04/apprendre-anglais-au-royaume-uni/article_final.html",
        publish_queue=True,
        published_date="",
        tokens_used=0
    )

    # Article 2
    result2 = RefreshResultRow(
        url="https://enseigna.fr/combien-de-temps-pour-apprendre-langlais-en-angleterre/",
        refresh_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        rewrite_type="FULL_REFRESH",
        new_title="Combien de temps pour apprendre l'anglais en Angleterre ? Guide complet 2026",
        new_meta="Combien de temps pour apprendre l'anglais en Angleterre ? De 2 semaines à 12 mois selon vos objectifs. Découvrez notre guide 2026 avec durées, formules et conseils pratiques.",
        sections_modified=5,
        word_count_before=1950,
        word_count_after=1700,
        images_before=10,
        images_after=10,
        links_before=56,
        links_after=10,
        validation_passed=True,
        validation_errors="",
        content_preview="Comptez entre 100 et 200 heures de cours intensifs pour progresser d'un niveau sur l'échelle CECRL. Selon les données du British Council (2025)...",
        full_content_link="outputs/enseigna/2026-02-04/combien-de-temps-pour-apprendre-langlais-en-anglet/article_final.html",
        publish_queue=True,
        published_date="",
        tokens_used=0
    )

    # Logger les résultats
    success1 = client.log_refresh(result1)
    print(f"Article 1: {'OK' if success1 else 'ERREUR'}")

    success2 = client.log_refresh(result2)
    print(f"Article 2: {'OK' if success2 else 'ERREUR'}")

    # Mettre à jour le statut des URLs dans URLs_Input
    from scripts.sheets.sheets_client import TaskStatus

    client.update_status(
        "https://enseigna.fr/apprendre-anglais-au-royaume-uni/",
        TaskStatus.COMPLETED
    )
    print("Statut URL 1 mis à jour: COMPLETED")

    client.update_status(
        "https://enseigna.fr/combien-de-temps-pour-apprendre-langlais-en-angleterre/",
        TaskStatus.COMPLETED
    )
    print("Statut URL 2 mis à jour: COMPLETED")

    print("\nMise à jour terminée!")


if __name__ == "__main__":
    main()
