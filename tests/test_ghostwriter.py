"""
Tests pour le module ghostwriter.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ghostwriter.ghostwriter import Ghostwriter, RewriteResult
from scripts.ghostwriter.diff_engine import DiffEngine, ContentDiff


class TestGhostwriter:
    """Tests pour Ghostwriter."""

    def setup_method(self):
        """Setup avant chaque test."""
        self.ghostwriter = Ghostwriter()

    def test_prepare_rewrite_context(self, sample_html, sample_audit_data):
        """Test préparation contexte de réécriture."""
        strategy_config = {
            "strategy": "PARTIAL_REFRESH",
            "rewrite_scope": "diff_based",
            "guidelines": ["Mettre à jour statistiques", "Renforcer E-E-A-T"],
            "blog_overrides": {},
        }

        assets = {
            "images": [{"src": "/img.jpg", "alt": "Test"}],
            "internal_links": [{"href": "/link", "anchor": "Link"}],
            "superprof_link": {"href": "https://superprof.fr", "anchor": "SP"},
            "counts": {"images": 1, "internal_links": 1},
        }

        context = self.ghostwriter.prepare_rewrite_context(
            original_html=sample_html,
            strategy_config=strategy_config,
            audit_data=sample_audit_data,
            assets=assets,
            seo_guidelines="Guidelines SEO...",
        )

        assert "instruction" in context
        assert "original_content" in context
        assert "audit_insights" in context
        assert "assets_to_preserve" in context
        assert "output_format" in context

    def test_context_includes_audit_insights(self, sample_html, sample_audit_data):
        """Test inclusion insights audit."""
        strategy_config = {
            "strategy": "TITLE_OPTIMIZATION",
            "rewrite_scope": "title_meta",
            "guidelines": [],
            "blog_overrides": {},
        }

        context = self.ghostwriter.prepare_rewrite_context(
            original_html=sample_html,
            strategy_config=strategy_config,
            audit_data=sample_audit_data,
            assets={"images": [], "internal_links": [], "counts": {}},
            seo_guidelines="",
        )

        insights = context["audit_insights"]
        assert insights["main_keyword"] == "apprendre maths"
        assert "alerts" in insights
        assert "recommendations" in insights

    def test_context_preserves_assets(self, sample_html, sample_audit_data):
        """Test préservation assets dans contexte."""
        strategy_config = {
            "strategy": "FULL_REFRESH",
            "rewrite_scope": "full_content",
            "guidelines": [],
            "blog_overrides": {},
        }

        assets = {
            "images": [
                {"src": "/img1.jpg", "alt": "Image 1"},
                {"src": "/img2.jpg", "alt": "Image 2"},
            ],
            "internal_links": [{"href": "/lien", "anchor": "Lien"}],
            "superprof_link": {"href": "https://superprof.fr", "anchor": "Superprof"},
            "counts": {"images": 2, "internal_links": 1},
        }

        context = self.ghostwriter.prepare_rewrite_context(
            original_html=sample_html,
            strategy_config=strategy_config,
            audit_data=sample_audit_data,
            assets=assets,
            seo_guidelines="",
        )

        assets_section = context["assets_to_preserve"]
        assert len(assets_section["images"]) == 2
        assert len(assets_section["internal_links"]) == 1
        assert "NE JAMAIS supprimer" in assets_section["rule"]

    def test_generate_instruction_title_optimization(self, sample_html, sample_audit_data):
        """Test instruction pour optimisation titre."""
        strategy_config = {
            "strategy": "TITLE_OPTIMIZATION",
            "rewrite_scope": "title_meta",
            "guidelines": [],
            "blog_overrides": {},
        }

        context = self.ghostwriter.prepare_rewrite_context(
            original_html=sample_html,
            strategy_config=strategy_config,
            audit_data=sample_audit_data,
            assets={"images": [], "internal_links": [], "counts": {}},
            seo_guidelines="",
        )

        instruction = context["instruction"]
        assert "titre" in instruction.lower() or "title" in instruction.lower()
        assert "meta" in instruction.lower()

    def test_generate_instruction_full_refresh(self, sample_html, sample_audit_data):
        """Test instruction pour refresh complet."""
        strategy_config = {
            "strategy": "FULL_REFRESH",
            "rewrite_scope": "full_content",
            "guidelines": [],
            "blog_overrides": {},
        }

        context = self.ghostwriter.prepare_rewrite_context(
            original_html=sample_html,
            strategy_config=strategy_config,
            audit_data=sample_audit_data,
            assets={"images": [], "internal_links": [], "counts": {}},
            seo_guidelines="",
        )

        instruction = context["instruction"]
        assert "complèt" in instruction.lower() or "réécri" in instruction.lower()

    def test_output_format_diff(self, sample_html, sample_audit_data):
        """Test format sortie diff."""
        strategy_config = {
            "strategy": "PARTIAL_REFRESH",
            "rewrite_scope": "diff_based",
            "guidelines": [],
            "blog_overrides": {},
        }

        context = self.ghostwriter.prepare_rewrite_context(
            original_html=sample_html,
            strategy_config=strategy_config,
            audit_data=sample_audit_data,
            assets={"images": [], "internal_links": [], "counts": {}},
            seo_guidelines="",
        )

        output_format = context["output_format"]
        assert output_format["type"] == "diff"
        assert "AVANT" in output_format["format"]
        assert "APRÈS" in output_format["format"]

    def test_output_format_full(self, sample_html, sample_audit_data):
        """Test format sortie complet."""
        strategy_config = {
            "strategy": "FULL_REFRESH",
            "rewrite_scope": "full_content",
            "guidelines": [],
            "blog_overrides": {},
        }

        context = self.ghostwriter.prepare_rewrite_context(
            original_html=sample_html,
            strategy_config=strategy_config,
            audit_data=sample_audit_data,
            assets={"images": [], "internal_links": [], "counts": {}},
            seo_guidelines="",
        )

        output_format = context["output_format"]
        assert output_format["type"] == "full"


class TestRewriteProcessing:
    """Tests pour le traitement des réponses LLM."""

    def setup_method(self):
        self.ghostwriter = Ghostwriter()

    def test_extract_new_title(self):
        """Test extraction nouveau titre."""
        llm_response = """
        <h1>Nouveau titre optimisé pour le CTR</h1>
        <p>Contenu de l'article...</p>
        """

        result = self.ghostwriter.process_rewrite_response(
            llm_response=llm_response,
            original_html="<h1>Ancien titre</h1>",
            rewrite_type="full",
            url="https://example.com",
        )

        assert result.new_title == "Nouveau titre optimisé pour le CTR"

    def test_extract_meta_description(self):
        """Test extraction meta description."""
        llm_response = """
        <h1>Titre</h1>
        <meta name="description" content="Nouvelle meta description optimisée">
        <p>Contenu...</p>
        """

        result = self.ghostwriter.process_rewrite_response(
            llm_response=llm_response,
            original_html="<h1>Titre</h1>",
            rewrite_type="full",
            url="https://example.com",
        )

        assert "optimisée" in result.new_meta_description

    def test_rewrite_result_structure(self):
        """Test structure RewriteResult."""
        result = self.ghostwriter.process_rewrite_response(
            llm_response="<h1>Titre</h1><p>Contenu</p>",
            original_html="<h1>Ancien</h1>",
            rewrite_type="full",
            url="https://example.com/article",
        )

        assert isinstance(result, RewriteResult)
        assert result.url == "https://example.com/article"
        assert result.rewrite_type == "full"
        assert result.original_html == "<h1>Ancien</h1>"
        assert result.new_content == "<h1>Titre</h1><p>Contenu</p>"


class TestDiffEngine:
    """Tests pour DiffEngine."""

    def setup_method(self):
        self.diff_engine = DiffEngine()

    def test_extract_sections(self, sample_html):
        """Test extraction des sections."""
        sections = self.diff_engine.extract_sections(sample_html)

        assert "h1" in sections
        assert sections["h1"] == "Comment apprendre les maths efficacement"

    def test_identify_sections_to_modify(self, sample_html):
        """Test identification sections à modifier."""
        sections = self.diff_engine.extract_sections(sample_html)

        recommendations = [
            "Mettre à jour statistiques 2023 → 2025",
            "Améliorer section FAQ",
        ]

        to_modify = self.diff_engine.identify_sections_to_modify(
            sections,
            recommendations
        )

        # Devrait identifier des sections basées sur les recommandations
        assert isinstance(to_modify, list)

    def test_compare_content(self):
        """Test comparaison de contenu."""
        original = """
        <h1>Titre original</h1>
        <h2>Section 1</h2>
        <p>Contenu section 1 original.</p>
        <h2>Section 2</h2>
        <p>Contenu section 2 original.</p>
        """

        # Section 1 réécrite en profondeur (au-delà du seuil de similarité 0.8 :
        # les changements triviaux d'un mot sont volontairement ignorés comme du
        # bruit ; on teste donc une vraie réécriture de section).
        modified = """
        <h1>Titre original</h1>
        <h2>Section 1</h2>
        <p>Voici une explication entièrement nouvelle et beaucoup plus détaillée
        de cette notion, avec des exemples concrets et une méthodologie pas à pas.</p>
        <h2>Section 2</h2>
        <p>Contenu section 2 original.</p>
        """

        diff = self.diff_engine.compare_content(original, modified)

        assert isinstance(diff, ContentDiff)
        assert diff.modified_sections >= 1

    def test_similarity_calculation(self):
        """Test calcul de similarité."""
        text1 = "Le chat mange la souris."
        text2 = "Le chat attrape la souris."

        similarity = self.diff_engine._calculate_similarity(text1, text2)

        # Textes similaires mais pas identiques
        assert 0 < similarity < 1
        assert similarity > 0.5  # Plus de 50% similaire

    def test_similarity_identical(self):
        """Test similarité textes identiques."""
        text = "Texte identique."

        similarity = self.diff_engine._calculate_similarity(text, text)
        assert similarity == 1.0

    def test_similarity_different(self):
        """Test similarité textes très différents."""
        text1 = "ABC XYZ 123"
        text2 = "Complètement différent autre chose"

        similarity = self.diff_engine._calculate_similarity(text1, text2)
        assert similarity < 0.3  # Très différents


class TestGhostwriterDiffPrompt:
    """Tests pour la génération de prompts diff."""

    def setup_method(self):
        self.ghostwriter = Ghostwriter()

    def test_generate_diff_prompt(self):
        """Test génération prompt diff."""
        sections_to_modify = [
            {"title": "Introduction", "content": "Ancien contenu intro..."},
            {"title": "Statistiques", "content": "Données 2023..."},
        ]

        recommendations = [
            "Mettre à jour les statistiques",
            "Ajouter sources récentes",
        ]

        assets = {
            "counts": {
                "images": 3,
                "internal_links": 5,
            },
        }

        prompt = self.ghostwriter.generate_diff_prompt(
            sections_to_modify,
            recommendations,
            assets
        )

        assert "Réécriture Partielle" in prompt
        assert "AVANT" in prompt
        assert "APRÈS" in prompt
        assert "Introduction" in prompt
        assert "Statistiques" in prompt
        assert "3 images" in prompt
        assert "5 liens internes" in prompt

    def test_diff_prompt_preserves_assets_warning(self):
        """Test avertissement préservation assets."""
        prompt = self.ghostwriter.generate_diff_prompt(
            sections_to_modify=[{"title": "Test", "content": "..."}],
            audit_recommendations=["Recommandation"],
            assets={"counts": {"images": 2, "internal_links": 3}},
        )

        assert "NE PAS SUPPRIMER" in prompt or "préserver" in prompt.lower()
        assert "Superprof" in prompt


class TestLanguageDirective:
    """Instruction de langue multi-marché (Phase 6d)."""

    def test_known_language_emits_directive(self):
        from scripts.ghostwriter.ghostwriter import language_directive
        block = language_directive("et")
        text = " ".join(block)
        assert "LANGUE DE RÉDACTION" in text
        assert "estonien" in text

    def test_french_and_portuguese(self):
        from scripts.ghostwriter.ghostwriter import language_directive
        assert "français" in " ".join(language_directive("fr"))
        assert "portugais" in " ".join(language_directive("pt"))

    def test_empty_or_unknown_language_no_directive(self):
        from scripts.ghostwriter.ghostwriter import language_directive
        assert language_directive("") == []
        assert language_directive("xx") == []

    def test_all_catalog_languages_have_names(self):
        """Toute langue du catalogue Superprof doit produire une directive."""
        import json
        from pathlib import Path
        from scripts.ghostwriter.ghostwriter import language_directive
        cat_path = Path(__file__).parent.parent / "_shared" / "config" / "superprof_blogs_catalog.json"
        if not cat_path.exists():
            pytest.skip("catalogue absent")
        cat = json.loads(cat_path.read_text(encoding="utf-8"))
        langs = {e["language"] for e in cat["blogs"] + cat["ressources_sites"] if e["language"]}
        for lang in langs:
            assert language_directive(lang), f"langue '{lang}' sans directive"
