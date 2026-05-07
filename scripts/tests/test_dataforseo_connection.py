#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de connexion API DataforSEO

Valide que :
1. Les credentials sont correctement configures
2. L'API repond avec un code 200
3. Les donnees SERP sont retournees correctement
"""

import json
import os
from pathlib import Path
import sys

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.audit.serp_analyzer import SERPAnalyzer


def test_dataforseo_connection():
    """Test la connexion a l'API DataforSEO."""

    print("=" * 70)
    print("TEST : Connexion API DataforSEO")
    print("=" * 70)

    # Verifier que les credentials existent
    credentials_path = Path(os.environ.get("DATAFORSEO_CREDENTIALS_PATH", os.path.expanduser("~/.credentials/dataforseo/credentials.json")))

    print("\n1. Verification des credentials...")
    if not credentials_path.exists():
        print(f"   [FAIL] ERREUR : Fichier credentials non trouve a {credentials_path}")
        return False

    try:
        with open(credentials_path) as f:
            creds = json.load(f)
            if "dataforseo" in creds:
                creds = creds["dataforseo"]
            login = creds.get("login", "")
            password = creds.get("password", "")

            if login and login != "VOTRE_LOGIN_DATAFORSEO":
                print(f"   [OK] Credentials trouves : login={login[:10]}...")
            else:
                print(f"   [FAIL] ERREUR : Login invalide ou placeholder")
                return False
    except Exception as e:
        print(f"   [FAIL] ERREUR : Impossible de lire les credentials : {e}")
        return False

    # Initialiser l'analyseur SERP
    print("\n2. Initialisation de SERPAnalyzer...")
    try:
        analyzer = SERPAnalyzer(location="France", language="fr")
        print("   [OK] SERPAnalyzer initialise")
    except Exception as e:
        print(f"   [FAIL] ERREUR : {e}")
        return False

    # Verifier que les credentials API sont charges
    if not analyzer._api_credentials:
        print("   [FAIL] ERREUR : Credentials API non charges")
        return False
    print("   [OK] Credentials API charges avec succes")

    # Tester une requete SERP
    print("\n3. Test d'une requete SERP (keyword: 'cours particuliers')...")
    try:
        keyword = "cours particuliers"
        result = analyzer.analyze(
            keyword=keyword,
            our_domain="enseigna.fr"
        )

        if result and hasattr(result, 'organic_results'):
            print("   [OK] Reponse SERP recue avec succes")

            # Afficher les resultats
            if result.organic_results:
                print(f"\n   Top 3 resultats organiques pour '{keyword}' :")
                for i, serp in enumerate(result.organic_results[:3], 1):
                    try:
                        domain = str(serp.domain) if serp.domain else "N/A"
                        url = str(serp.url) if serp.url else "N/A"
                        position = str(serp.position) if serp.position else "N/A"
                        # Nettoyer les caracteres problematiques
                        domain = ''.join(c for c in domain if ord(c) < 128 or ord(c) >= 160)
                        url = ''.join(c for c in url if ord(c) < 128 or ord(c) >= 160)

                        print(f"   {i}. {domain}")
                        print(f"      URL: {url}")
                        print(f"      Position: {position}")
                        if hasattr(serp, 'word_count') and serp.word_count:
                            print(f"      Word Count: {serp.word_count}")
                        print()
                    except Exception as serp_err:
                        print(f"   {i}. [Erreur affichage : {serp_err}]")
                        continue

            if hasattr(result, 'our_position') and result.our_position:
                print(f"   [INFO] Notre position pour ce keyword : {result.our_position}")

            return True
        else:
            print("   [FAIL] ERREUR : Reponse SERP vide ou invalide")
            # Ne pas afficher la reponse complete si elle contient des caracteres problematiques
            print("   [INFO] Reponse recue mais pas de donnees SERP exploitables")
            return False

    except Exception as e:
        print(f"   [FAIL] ERREUR lors de l'appel API : {str(e)[:100]}")
        return False


def main():
    """Fonction principale."""
    success = test_dataforseo_connection()

    print("\n" + "=" * 70)
    if success:
        print("[SUCCESS] TEST REUSSI : DataforSEO API fonctionne correctement")
        print("   -> On peut lancer le workflow batch")
    else:
        print("[FAILURE] TEST ECHOUE : DataforSEO API ne repond pas correctement")
        print("   -> Il faudra ajouter le support MCP DataforSEO")
    print("=" * 70)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
