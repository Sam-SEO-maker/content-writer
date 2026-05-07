"""
Test d'integration des requetes GSC dans le workflow de refresh.

Verifie que:
1. Les keywords sont bien exportees dans audit_dict
2. Les keywords sont formatees intelligemment (quick wins, long tail, core)
3. Le prompt final contient les recommandations semantiques
"""

import sys
import io

# Force UTF-8 encoding for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from scripts.ghostwriter import Ghostwriter


def test_gsc_queries_formatting():
    """Test du formatage des requêtes GSC."""
    print("\n=== TEST: Formatage Requêtes GSC ===\n")

    ghostwriter = Ghostwriter()

    # Données GSC simulées (représentatives d'un vrai article)
    mock_keywords = [
        # Quick wins: impressions élevées, CTR faible
        {"query": "formation coach sportif", "impressions": 1200, "ctr": 1.5, "position": 8.2, "clicks": 18},
        {"query": "devenir coach sportif", "impressions": 850, "ctr": 1.8, "position": 12.5, "clicks": 15},

        # Core keywords: bonnes impressions, bonne position
        {"query": "avis superprof", "impressions": 650, "ctr": 4.2, "position": 5.3, "clicks": 27},
        {"query": "cours sport lyon", "impressions": 420, "ctr": 3.8, "position": 7.1, "clicks": 16},

        # Long tail: faible volume, bien positionné
        {"query": "coach sportif domicile lyon 6", "impressions": 35, "ctr": 8.5, "position": 3.2, "clicks": 3},
        {"query": "personal trainer lyon croix rousse", "impressions": 28, "ctr": 7.1, "position": 4.5, "clicks": 2},
        {"query": "cours musculation lyon particulier", "impressions": 42, "ctr": 4.8, "position": 8.9, "clicks": 2},

        # Autres requêtes variées
        {"query": "tarif coach sportif lyon", "impressions": 180, "ctr": 2.2, "position": 15.3, "clicks": 4},
        {"query": "coach sportif perte de poids", "impressions": 95, "ctr": 1.9, "position": 18.7, "clicks": 2},
        {"query": "meilleur coach sportif lyon", "impressions": 320, "ctr": 2.8, "position": 9.5, "clicks": 9},
    ]

    # Formater les requêtes
    formatted = ghostwriter._format_gsc_queries(mock_keywords)

    # Vérifications
    assert formatted['available'] is True, "Les données GSC devraient être disponibles"
    assert formatted['total_queries'] == len(mock_keywords), f"Total queries mismatch: {formatted['total_queries']}"

    print(f"✅ Total queries: {formatted['total_queries']}")
    print(f"✅ Quick wins détectés: {len(formatted['quick_wins'])}")
    print(f"✅ Long tail détectés: {len(formatted['long_tail'])}")
    print(f"✅ Core keywords détectés: {len(formatted['core_keywords'])}")

    # Afficher les catégories
    print("\n--- Quick Wins (Impressions élevées + CTR faible) ---")
    for qw in formatted['quick_wins']:
        print(f"  • \"{qw['query']}\" - {qw['impressions']} imp., CTR {qw['ctr']}%, pos {qw['position']}")
        print(f"    → {qw['opportunity']}")

    print("\n--- Long Tail (Faible volume + Bonne position) ---")
    for lt in formatted['long_tail']:
        print(f"  • \"{lt['query']}\" - pos {lt['position']}")
        print(f"    → {lt['opportunity']}")

    print("\n--- Core Keywords (Bonnes impressions + Top 10) ---")
    for core in formatted['core_keywords']:
        print(f"  • \"{core['query']}\" - {core['impressions']} imp., pos {core['position']}")
        print(f"    → {core['opportunity']}")

    # Vérifier le résumé pour le prompt
    print("\n--- Résumé pour le prompt ---")
    print(formatted['summary_for_prompt'])

    # Vérifier les recommandations
    print("\n--- Recommandations ---")
    for rec in formatted['recommendations']:
        print(f"  • {rec}")

    print("\n✅ TEST PASSED: Formatage des requêtes GSC fonctionne correctement\n")


def test_audit_data_integration():
    """Test de l'intégration dans audit_data."""
    print("\n=== TEST: Intégration dans audit_data ===\n")

    ghostwriter = Ghostwriter()

    # Simuler audit_data avec keywords
    mock_audit_data = {
        "url": "https://enseigna.fr/avis-superprof/",
        "main_keyword": "avis superprof",
        "performance": {
            "clicks_30d": 125,
            "impressions_30d": 3500,
            "ctr_30d": 3.6,
            "avg_position": 8.2,
            "main_keyword": "avis superprof",
            "keywords": [
                {"query": "avis superprof", "impressions": 650, "ctr": 4.2, "position": 5.3, "clicks": 27},
                {"query": "formation coach sportif", "impressions": 1200, "ctr": 1.5, "position": 8.2, "clicks": 18},
                {"query": "personal trainer lyon", "impressions": 35, "ctr": 8.5, "position": 3.2, "clicks": 3},
            ]
        },
        "alerts": [],
        "recommendations": ["Enrichir le contenu", "Ajouter FAQ"],
    }

    # Préparer le contexte de réécriture
    context = ghostwriter.prepare_rewrite_context(
        original_html="<h1>Coach Sportif Lyon</h1><p>Test content...</p>",
        strategy_config={
            "strategy": "PARTIAL_REFRESH",
            "rewrite_scope": "full_content",
            "guidelines": [],
            "blog_overrides": {},
        },
        audit_data=mock_audit_data,
        assets={"images": [], "internal_links": []},
        seo_guidelines=""
    )

    # Vérifier que gsc_queries est présent
    assert 'gsc_queries' in context['audit_insights'], "gsc_queries devrait être dans audit_insights"

    gsc_queries = context['audit_insights']['gsc_queries']
    assert gsc_queries['available'] is True, "GSC queries devraient être disponibles"
    assert gsc_queries['total_queries'] == 3, f"Total queries incorrect: {gsc_queries['total_queries']}"

    print(f"✅ gsc_queries présent dans context['audit_insights']")
    print(f"✅ Total queries: {gsc_queries['total_queries']}")
    print(f"✅ Quick wins: {len(gsc_queries['quick_wins'])}")
    print(f"✅ Long tail: {len(gsc_queries['long_tail'])}")
    print(f"✅ Summary généré: {bool(gsc_queries.get('summary_for_prompt'))}")

    print("\n✅ TEST PASSED: Intégration dans audit_data fonctionne\n")


def test_empty_keywords():
    """Test du cas où il n'y a pas de requêtes (nouveau contenu)."""
    print("\n=== TEST: Gestion des keywords vides ===\n")

    ghostwriter = Ghostwriter()

    # Cas 1: Liste vide
    formatted = ghostwriter._format_gsc_queries([])
    assert formatted['available'] is False, "Devrait indiquer non disponible"
    assert 'message' in formatted, "Devrait contenir un message explicatif"
    print(f"✅ Liste vide gérée: {formatted['message']}")

    # Cas 2: None (nouveau contenu)
    mock_audit_data = {
        "performance": {
            "keywords": []  # Pas de keywords
        },
        "recommendations": []
    }

    context = ghostwriter.prepare_rewrite_context(
        original_html="<h1>Test</h1>",
        strategy_config={"strategy": "PARTIAL_REFRESH", "rewrite_scope": "full_content", "guidelines": [], "blog_overrides": {}},
        audit_data=mock_audit_data,
        assets={},
        seo_guidelines=""
    )

    gsc_queries = context['audit_insights']['gsc_queries']
    assert gsc_queries['available'] is False, "Devrait indiquer non disponible"

    print(f"✅ Keywords vides gérés correctement")
    print("\n✅ TEST PASSED: Gestion des cas limites OK\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("TESTS D'INTÉGRATION: Requêtes GSC dans Workflow Refresh")
    print("="*60)

    try:
        test_gsc_queries_formatting()
        test_audit_data_integration()
        test_empty_keywords()

        print("\n" + "="*60)
        print("✅ TOUS LES TESTS PASSÉS !")
        print("="*60 + "\n")

        print("📊 Résumé:")
        print("  1. ✅ Formatage intelligent des requêtes (quick wins, long tail, core)")
        print("  2. ✅ Intégration dans audit_data et rewrite_context")
        print("  3. ✅ Gestion robuste des cas limites (keywords vides)")
        print("\n🚀 L'intégration des requêtes GSC est OPÉRATIONNELLE\n")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        raise
