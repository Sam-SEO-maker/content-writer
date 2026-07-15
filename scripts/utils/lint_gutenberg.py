"""
Gutenberg HTML Linter & Fixer — SP Ressources

Vérifie les fichiers .gutenberg.html générés avant upload WP.
Bloque l'upload si des problèmes connus sont détectés.
Avec --fix, corrige automatiquement le bloc Sources.

Usage:
  python scripts/utils/lint_gutenberg.py                            # scan _shared/outputs/
  python scripts/utils/lint_gutenberg.py path/to/file.html          # fichier unique
  python scripts/utils/lint_gutenberg.py path/ --fix                # scan + fix Sources
  python scripts/utils/lint_gutenberg.py path/to/file.html --fix    # fix fichier unique
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ─── Constantes ──────────────────────────────────────────────────────────────

OUTPUTS_DIR = Path(__file__).parent.parent.parent / "_shared" / "outputs"

# ─── Patterns pour le fix Sources ────────────────────────────────────────────

# Capture le bloc Sources complet dans sa forme INCORRECTE (sans wrapper)
# Accepte les variantes avec ou sans sauts de ligne supplémentaires
_SOURCES_BARE_RE = re.compile(
    r'<!-- wp:heading -->\s*\n'
    r'<h2 class="wp-block-heading">Sources 📚</h2>\s*\n'
    r'<!-- /wp:heading -->\s*\n'
    r'\s*\n?'
    r'<!-- wp:list \{"ordered":true[^}]*\} -->\s*\n'
    r'<ol class="wp-block-list references">\s*\n'
    r'([\s\S]*?)'
    r'</ol>\s*\n'
    r'<!-- /wp:list -->',
    re.DOTALL,
)

_LI_RE = re.compile(r'(<li>[\s\S]*?</li>)')

SCIENCE_SLUGS = {
    "chimie", "physique", "maths", "mathematiques", "physique-chimie",
    "redox", "electron", "mole", "atome", "nucleaire", "optique",
    "thermodynamique", "mecanique", "algebre", "geometrie", "trigonometrie",
    "probabilite", "statistique", "derivee", "integrale",
}

SCIENCE_CONTENT_MARKERS = [
    "mol⁻¹", "g·mol", "h₂o", "co₂", "équation chimique",
    "demi-équation", "oxydant", "réducteur", "quantité de matière",
    "masse molaire", "nombre d'avogadro", "potentiel standard",
    "oxydoréduction", "électrochimie",
]

FORBIDDEN_PHRASES: dict[str, str] = {
    "dans ce cours": "cadrage pédagogique interdit",
    "dans ce guide": "cadrage pédagogique interdit",
    "ce cours s'adresse": "cadrage pédagogique interdit",
    "ce guide s'adresse": "cadrage pédagogique interdit",
    "à la fin de ce cours": "cadrage pédagogique interdit",
    "ce cours te permettra": "cadrage pédagogique interdit",
    "on va voir ensemble": "cadrage pédagogique interdit (même sans 'dans ce cours')",
    "pas de panique": "formulation négative interdite",
    "pas d'inquiétude": "formulation négative interdite",
    "tu n'arrives pas à": "formulation négative interdite",
    "tu n'y arrives pas": "formulation négative interdite",
    "tu as de la difficulté": "formulation négative interdite",
    "tu éprouves des difficultés": "formulation négative interdite",
    "c'est difficile pour beaucoup": "formulation négative interdite",
    "tu bloques": "formulation négative interdite",
    "tu n'es pas seul": "formulation négative interdite",
}

FORBIDDEN_COLORS = ["#4caf50", "#fff9e6", "#e8f4f8"]

# Pattern du wrapper sources correct (doit être inline, pas de saut de ligne)
SOURCES_CORRECT_RE = re.compile(
    r'<div class="wp-block-group"><!-- wp:group \{"className":"wp-block-wp-sp-gutenberg-blocks-block-sources"\} -->'
)


# ─── Sources fixer ───────────────────────────────────────────────────────────

def build_correct_sources_block(li_items: list[str]) -> str:
    """
    Reconstruit le bloc Sources au format Gutenberg validé WP.

    Format exact (inline entre <div> et <!-- wp:group -->, blank line entre items,
    </ol> inline après le dernier <!-- /wp:list-item -->).
    """
    if not li_items:
        return ""

    list_section = '<ol class="wp-block-list references">'
    for i, li in enumerate(li_items):
        is_last = i == len(li_items) - 1
        if i == 0:
            list_section += f'<!-- wp:list-item -->\n{li}\n<!-- /wp:list-item -->'
        else:
            list_section += f'\n\n<!-- wp:list-item -->\n{li}\n<!-- /wp:list-item -->'
        if is_last:
            list_section += '</ol>'

    return (
        '<!-- wp:group -->\n'
        '<div class="wp-block-group"><!-- wp:group {"className":"wp-block-wp-sp-gutenberg-blocks-block-sources"} -->\n'
        '<div class="wp-block-group wp-block-wp-sp-gutenberg-blocks-block-sources"><!-- wp:heading -->\n'
        '<h2 class="wp-block-heading">Sources 📚</h2>\n'
        '<!-- /wp:heading -->\n'
        '\n'
        '<!-- wp:list {"ordered":true,"className":"references"} -->\n'
        f'{list_section}\n'
        '<!-- /wp:list --></div>\n'
        '<!-- /wp:group --></div>\n'
        '<!-- /wp:group -->'
    )


def fix_sources(content: str) -> tuple[str, bool]:
    """
    Corrige le bloc Sources dans le contenu HTML.

    Returns:
        (contenu_corrigé, a_été_modifié)
    """
    def _replace(match: re.Match) -> str:
        raw_items = match.group(1)
        li_items = _LI_RE.findall(raw_items)
        if not li_items:
            return match.group(0)
        return build_correct_sources_block(li_items)

    new_content, n = _SOURCES_BARE_RE.subn(_replace, content)
    return new_content, n > 0


# ─── Modèle d'issue ───────────────────────────────────────────────────────────

@dataclass
class Issue:
    severity: str  # "error" | "warning"
    code: str
    message: str

    def __str__(self) -> str:
        icon = "❌" if self.severity == "error" else "⚠️"
        return f"  {icon} [{self.code}] {self.message}"


@dataclass
class FileReport:
    path: Path
    issues: list[Issue] = field(default_factory=list)
    fixed: bool = False

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0


# ─── Checks ──────────────────────────────────────────────────────────────────

def check_sources_block(content: str) -> list[Issue]:
    """Le bloc Sources doit utiliser le wrapper Superprof avec format inline."""
    issues: list[Issue] = []

    has_sources_emoji = "Sources 📚" in content
    has_sources_block_class = "wp-block-wp-sp-gutenberg-blocks-block-sources" in content
    has_correct_inline = bool(SOURCES_CORRECT_RE.search(content))

    if not has_sources_emoji:
        issues.append(Issue("error", "SOURCES-MISSING",
            "Bloc Sources 📚 absent — obligatoire dans chaque article SP Ressources"))
    elif not has_sources_block_class:
        issues.append(Issue("error", "SOURCES-NO-WRAPPER",
            "Bloc Sources sans wrapper 'wp-block-wp-sp-gutenberg-blocks-block-sources' — "
            "le Block References Superprof ne sera pas reconnu"))
    elif not has_correct_inline:
        issues.append(Issue("error", "SOURCES-NEWLINE",
            "Bloc Sources : saut de ligne détecté entre <div class=\"wp-block-group\"> et "
            "<!-- wp:group {\"className\":...} --> — doit être inline sur la même ligne"))

    return issues


def check_forbidden_phrases(content: str) -> list[Issue]:
    """Détecte les formulations interdites par charte éditoriale."""
    issues: list[Issue] = []
    content_lower = content.lower()
    for phrase, reason in FORBIDDEN_PHRASES.items():
        if phrase in content_lower:
            issues.append(Issue("error", "FORBIDDEN-PHRASE",
                f'Phrase interdite : "{phrase}" — {reason}'))
    return issues


def check_em_dash(content: str) -> list[Issue]:
    """Le tiret cadratin (—) est interdit dans tout contenu généré."""
    count = content.count("—")
    if count > 0:
        return [Issue("error", "EM-DASH",
            f"Tiret cadratin (—) : {count} occurrence(s) — remplacer par '-' ou reformuler")]
    return []


def check_consulte_le(content: str) -> list[Issue]:
    """'Consulté le [date]' interdit dans les références MLA."""
    pattern = re.compile(r"consult[ée]\s+le\s+\d", re.IGNORECASE)
    if pattern.search(content):
        return [Issue("error", "CONSULTE-LE",
            '"Consulté le [date]" trouvé dans les références — interdit, supprimer la date d\'accès')]
    return []


def check_forbidden_callouts(content: str) -> list[Issue]:
    """Blocs callout colorés interdits sur Enseigna et SP Ressources."""
    issues: list[Issue] = []
    for color in FORBIDDEN_COLORS:
        if color in content.lower():
            issues.append(Issue("error", "FORBIDDEN-CALLOUT",
                f"Couleur callout interdite : {color} — ces blocs ne doivent pas figurer sur SP Ressources"))
    return issues


def check_latex_science(content: str, filepath: Path) -> list[Issue]:
    """Les articles scientifiques doivent utiliser LaTeX/MathJax pour les formules."""
    issues: list[Issue] = []

    # Détection article scientifique : slug ou contenu
    slug = filepath.stem.lower()
    is_science_slug = any(kw in slug for kw in SCIENCE_SLUGS)
    content_lower = content.lower()
    is_science_content = any(marker in content_lower for marker in SCIENCE_CONTENT_MARKERS)

    if not (is_science_slug or is_science_content):
        return []

    # Chercher les notations unicode chimiques HORS blocs Sources
    # (on exclu le contenu après "Sources 📚" car les références peuvent avoir des symboles)
    sources_pos = content.find("Sources 📚")
    main_content = content[:sources_pos] if sources_pos != -1 else content

    unicode_chem_chars = ["²⁺", "²⁻", "³⁺", "³⁻", "⁻", "⁺", "₂", "₃", "₄", "₅", "₆"]
    has_unicode = any(char in main_content for char in unicode_chem_chars)
    has_latex = r"\(" in content or r"\[" in content

    if has_unicode and not has_latex:
        issues.append(Issue("error", "LATEX-MISSING",
            "Article scientifique avec notation Unicode (²⁺, ₂…) sans LaTeX/MathJax — "
            r"convertir en \( ... \) ou \[ ... \]"))
    elif has_unicode and has_latex:
        issues.append(Issue("warning", "LATEX-MIXED",
            r"Mélange notation Unicode + LaTeX/MathJax — vérifier que toutes les formules utilisent \( \) ou \[ \]"))

    return issues


def check_h1_first(content: str) -> list[Issue]:
    """Le H1 doit être le premier bloc Gutenberg heading."""
    # Trouver le premier <!-- wp:heading ... -->
    first_wp_heading = re.search(r'<!-- wp:heading(\s*\{[^}]*\})?\s*-->', content)
    if not first_wp_heading:
        return []

    attrs = first_wp_heading.group(1) or ""
    if '"level":1' not in attrs and '{"level":1}' not in attrs:
        return [Issue("warning", "H1-NOT-FIRST",
            "Le premier bloc wp:heading n'est pas un H1 (level:1) — vérifier la structure")]
    return []


# ─── Orchestration ────────────────────────────────────────────────────────────

CHECKS = [
    check_sources_block,
    check_forbidden_phrases,
    check_em_dash,
    check_consulte_le,
    check_forbidden_callouts,
]


def lint_file(path: Path, apply_fix: bool = False) -> FileReport:
    report = FileReport(path=path)
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        report.issues.append(Issue("error", "READ-ERROR", str(e)))
        return report

    if apply_fix:
        fixed_content, was_fixed = fix_sources(content)
        if was_fixed:
            path.write_text(fixed_content, encoding="utf-8")
            report.fixed = True
            content = fixed_content  # lint the fixed version

    for check in CHECKS:
        report.issues.extend(check(content))

    # Checks avec paramètres supplémentaires
    report.issues.extend(check_latex_science(content, path))
    report.issues.extend(check_h1_first(content))

    return report


def lint_paths(targets: list[Path], apply_fix: bool = False) -> list[FileReport]:
    files: list[Path] = []
    for target in targets:
        if target.is_dir():
            files.extend(sorted(target.glob("*.gutenberg.html")))
        elif target.suffix in (".html", ".htm"):
            files.append(target)

    if not files:
        print("Aucun fichier .gutenberg.html trouvé.")
        return []

    return [lint_file(f, apply_fix=apply_fix) for f in files]


# ─── Affichage ────────────────────────────────────────────────────────────────

def print_report(reports: list[FileReport], apply_fix: bool = False) -> int:
    """Affiche le rapport et retourne le code de sortie (0=OK, 1=erreurs)."""
    total_errors = 0
    total_warnings = 0
    total_fixed = sum(1 for r in reports if r.fixed)

    mode = "Linter + Fix" if apply_fix else "Linter"
    print(f"\n🔍 SP Ressources {mode} — {len(reports)} fichier(s)\n")

    for report in reports:
        errors = [i for i in report.issues if i.severity == "error"]
        warnings = [i for i in report.issues if i.severity == "warning"]

        fix_tag = " [Sources corrigées ✓]" if report.fixed else ""

        if report.is_clean:
            print(f"  ✅ {report.path.name}{fix_tag}")
        else:
            status = "❌" if errors else "⚠️"
            print(f"  {status} {report.path.name}{fix_tag}")
            for issue in report.issues:
                print(f"    {issue}")

        total_errors += len(errors)
        total_warnings += len(warnings)

    print(f"\n{'─' * 60}")
    if apply_fix and total_fixed:
        print(f"🔧 {total_fixed} fichier(s) avec Sources corrigées")
    if total_errors == 0 and total_warnings == 0:
        print("✅ Tous les fichiers sont conformes — prêts pour upload WP\n")
        return 0
    else:
        parts = []
        if total_errors:
            parts.append(f"{total_errors} erreur(s)")
        if total_warnings:
            parts.append(f"{total_warnings} avertissement(s)")
        print(f"{'❌' if total_errors else '⚠️'} {', '.join(parts)} restante(s) après correction\n")
        return 1 if total_errors else 0


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    apply_fix = "--fix" in args
    path_args = [a for a in args if a != "--fix"]

    if path_args:
        targets = [Path(a) for a in path_args]
    else:
        from _shared.core.tenant_paths import TenantPaths
        targets = [TenantPaths().output_dir("superprof-ressources") / "html"]

    reports = lint_paths(targets, apply_fix=apply_fix)
    if not reports:
        sys.exit(0)

    exit_code = print_report(reports, apply_fix=apply_fix)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
