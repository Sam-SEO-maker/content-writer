"""Routing locale (serp_location / language) du SERPAnalyzer par tenant.

Garde-fou de non-régression : les tenants historiques (enseigna,
superprof-ressources) ne déclarent pas `serp_location`/`language` et doivent
continuer à cibler France/fr. Les nouveaux marchés (US, AU...) déclarent les
deux champs et doivent les voir appliqués.

Isolé du réseau : `_get_serp_analyzer` est appelée sur un orchestrateur non
initialisé, avec un SERPAnalyzer factice (le vrai ouvre des credentials API).
"""

from unittest.mock import patch

import pytest

from scripts.agent.orchestrator import RefreshOrchestrator


class _FakeSERPAnalyzer:
    """Capture les kwargs de locale sans toucher au réseau."""

    def __init__(self, location="France", language="fr"):
        self.location = location
        self.language = language


def _orchestrator_with_configs(configs: dict):
    """Orchestrateur nu : ni __init__, ni réseau, ni credentials.

    Seuls les attributs lus par _get_serp_analyzer sont posés.
    """
    orch = RefreshOrchestrator.__new__(RefreshOrchestrator)
    orch._serp_analyzers = {}
    orch._sites_config = {}

    class _DocCache:
        def get_blog_config(self, blog_id):
            return configs.get(blog_id, {})

    orch.doc_cache = _DocCache()
    return orch


def _resolve(configs, blog_id):
    orch = _orchestrator_with_configs(configs)
    with patch("scripts.agent.orchestrator.SERPAnalyzer", _FakeSERPAnalyzer):
        return orch._get_serp_analyzer(blog_id)


# --- Non-régression France --------------------------------------------------

@pytest.mark.parametrize("blog_id", ["enseigna", "superprof-ressources"])
def test_tenant_sans_locale_reste_france_fr(blog_id):
    """Config sans serp_location/language → France/fr (comportement historique)."""
    analyzer = _resolve({blog_id: {"gsc_property": "https://example.test/"}}, blog_id)

    assert analyzer.location == "France"
    assert analyzer.language == "fr"


def test_blog_id_inconnu_reste_france_fr():
    """Config absente → défauts, sans lever."""
    analyzer = _resolve({}, "tenant-inexistant")

    assert analyzer.location == "France"
    assert analyzer.language == "fr"


# --- Nouveaux marchés -------------------------------------------------------

def test_tenant_us_route_sur_united_states_en():
    configs = {"en-us-blog": {"serp_location": "United States", "language": "en"}}

    analyzer = _resolve(configs, "en-us-blog")

    assert analyzer.location == "United States"
    assert analyzer.language == "en"


def test_language_et_serp_location_sont_independants():
    """Même langue, locations distinctes : en-au ne doit pas hériter des US."""
    configs = {
        "en-au-blog": {"serp_location": "Australia", "language": "en"},
        "en-ng-blog": {"serp_location": "Nigeria", "language": "en"},
    }
    orch = _orchestrator_with_configs(configs)

    with patch("scripts.agent.orchestrator.SERPAnalyzer", _FakeSERPAnalyzer):
        au = orch._get_serp_analyzer("en-au-blog")
        ng = orch._get_serp_analyzer("en-ng-blog")

    assert (au.location, au.language) == ("Australia", "en")
    assert (ng.location, ng.language) == ("Nigeria", "en")


def test_locale_partielle_complete_par_les_defauts():
    """language seul déclaré → location retombe sur France."""
    analyzer = _resolve({"fr-be-blog": {"language": "fr"}}, "fr-be-blog")

    assert analyzer.location == "France"
    assert analyzer.language == "fr"


def test_locale_vide_retombe_sur_les_defauts():
    """Le scaffold écrit "" si le pays n'est pas résolu : ne pas propager du vide."""
    configs = {"xx-zz-blog": {"serp_location": "", "language": ""}}

    analyzer = _resolve(configs, "xx-zz-blog")

    assert analyzer.location == "France"
    assert analyzer.language == "fr"


# --- Cache ------------------------------------------------------------------

def test_analyzer_mis_en_cache_par_blog():
    configs = {"en-us-blog": {"serp_location": "United States", "language": "en"}}
    orch = _orchestrator_with_configs(configs)

    with patch("scripts.agent.orchestrator.SERPAnalyzer", _FakeSERPAnalyzer):
        first = orch._get_serp_analyzer("en-us-blog")
        second = orch._get_serp_analyzer("en-us-blog")

    assert first is second
