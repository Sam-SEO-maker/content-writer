"""
Commandes de plan éditorial (content_plan.md).

Usage:
    cw plan check <url> --site superprof.fr-ressources

`plan check` valide *mécaniquement* le plan produit à l'étape 2bis de /refresh
(skill seo-outline) : hiérarchie des titres, couverture PAA, preuves. 100%
déterministe — aucun appel LLM/API. La rédaction du plan reste au subagent Max ;
cette commande ne fait que le noter (patron identique à `ytg qc` / `finalize`).
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

import click
from cli.options import blog_option

from scripts.audit.plan_validator import validate_plan


CONTEXT_DIR = Path.cwd() / "_shared" / "context"


def _slugify_url(url: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "_", url.lower())
    return re.sub(r"_+", "_", slug).strip("_")


def _find_context_dir(url: str) -> Optional[Path]:
    """Résout le context_dir d'une URL (même stratégie que ytg._find_audit_file)."""
    candidate = CONTEXT_DIR / _slugify_url(url)
    if (candidate / "audit_data.json").exists():
        return candidate
    if not CONTEXT_DIR.exists():
        return None
    for d in CONTEXT_DIR.iterdir():
        if not d.is_dir():
            continue
        audit_file = d / "audit_data.json"
        if not audit_file.exists():
            continue
        try:
            data = json.loads(audit_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("url") == url:
            return d
    return None


@click.group()
def plan():
    """Plan éditorial (content_plan.md) : scaffold + validation SEO déterministe."""
    pass


_PLAN_TEMPLATE = """\
<!-- EDITORIAL PLAN, page: {url}

     Outline written by the agent via the `seo-outline` skill, then validated by
     `cw plan check`. The CLI laid out the structure and injected the signals below;
     it writes NO prose. Fill in the H2/H3, place the PAA and the proofs,
     delete the comments as you go.

     SIGNALS (extracted from audit_data.json; to cover, not to copy verbatim):
       Main keyword: {main_keyword}
       Intent / action: {action}
       PAA to cover ({paa_count}):
{paa_block}
       Secondary keywords: {secondary}
       Assets to preserve (Golden Rule): {assets}

     INVARIANTS (checked by `cw plan check`):
       - >= 3 H2, no orphan H2 or H3
       - under an H2: 0 H3, or >= 2 H3 (never a single one)
       - split into 2-4 H3 as soon as the H2 exceeds ~150 words; max 4 H3/H2
       - `?` on every interrogative heading
       - >= 3 institutional source links + >= 2 numbered statistics, per H2
       - every PAA above covered by at least one section

     STRUCTURE TO WRITE (>= 3 H2). Put each heading on its own `## Title` line,
     then its content below; add `### Subheading` lines if the H2 exceeds
     ~150 words. NEVER emit a `##` without text (empty heading = invalid). -->
"""


def _format_paa_block(paa_raw: str) -> tuple[str, int]:
    from scripts.audit.plan_validator import _split_terms
    terms = _split_terms(paa_raw)
    if not terms:
        return "    (no PAA collected)", 0
    return "\n".join(f"    - {t}" for t in terms), len(terms)


@plan.command(name="init")
@click.argument("url")
@blog_option(required=True)
@click.option("--force", is_flag=True, help="Écrase un content_plan.md existant.")
def init(url: str, blog: str, force: bool):
    """
    Scaffold déterministe de content_plan.md au bon chemin.

    Crée le fichier dans le context_dir de l'URL, pré-rempli d'un template + des
    signaux (PAA, mot-clé, intent, assets) extraits de audit_data.json. Le CLI
    pose la STRUCTURE ; l'agent RÉDIGE ensuite l'outline via la skill seo-outline,
    puis `cw plan check` valide. Aucune phrase rédigée par le CLI (règle : la
    génération passe par le subagent Max, jamais l'API).
    """
    context_dir = _find_context_dir(url)
    if context_dir is None:
        click.echo(
            f"❌ Aucun context_dir pour {url}. Lance d'abord "
            f"`cw refresh {url} --site {blog}`.",
            err=True,
        )
        sys.exit(2)

    plan_file = context_dir / "content_plan.md"
    if plan_file.exists() and not force:
        click.echo(
            f"⚠️  {plan_file} existe déjà. --force pour l'écraser.", err=True)
        sys.exit(2)

    try:
        audit = json.loads((context_dir / "audit_data.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        audit = {}

    paa_block, paa_count = _format_paa_block(audit.get("people_also_ask", "") or "")
    content = _PLAN_TEMPLATE.format(
        url=url,
        main_keyword=audit.get("main_keyword", "(unknown)") or "(unknown)",
        action=audit.get("action", "(unknown)") or "(unknown)",
        paa_count=paa_count,
        paa_block=paa_block,
        secondary=audit.get("secondary_keywords", "") or "(none)",
        assets=json.dumps(audit.get("assets_counts", {}), ensure_ascii=False),
    )
    plan_file.write_text(content, encoding="utf-8")

    click.echo(f"✅ Squelette créé : {plan_file}")
    click.echo(f"   {paa_count} PAA injectée(s) à couvrir.")
    click.echo(
        "   → Remplis l'outline via la skill `seo-outline`, puis "
        f"`cw plan check {url} --site {blog}`.")


@plan.command(name="check")
@click.argument("url")
@blog_option(required=True)
@click.option(
    "--plan-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Chemin explicite du content_plan.md (sinon résolu depuis l'URL).",
)
@click.option("--json", "as_json", is_flag=True, help="Sortie JSON (scriptable).")
def check(url: str, blog: str, plan_file: Optional[Path], as_json: bool):
    """
    Valide un content_plan.md contre les invariants SEO (seo-outline).

    Verdict OK → passer à la génération. NEEDS_FIX → corriger le plan (bon
    marché) avant de rédiger l'article. Code de sortie 1 si NEEDS_FIX.
    """
    context_dir = _find_context_dir(url)
    paa_raw = ""

    if plan_file is None:
        if context_dir is None:
            click.echo(
                f"❌ Aucun context_dir trouvé pour {url}. "
                f"Lance d'abord `cw refresh {url} --site {blog}`.",
                err=True,
            )
            sys.exit(2)
        plan_file = context_dir / "content_plan.md"
        if not plan_file.exists():
            click.echo(
                f"❌ Pas de content_plan.md dans {context_dir}. "
                f"L'étape 2bis (skill seo-outline) ne l'a pas encore produit.",
                err=True,
            )
            sys.exit(2)

    # PAA : depuis l'audit résolu (si trouvé), sinon plan sans check de couverture.
    if context_dir is not None:
        try:
            audit = json.loads((context_dir / "audit_data.json").read_text(encoding="utf-8"))
            paa_raw = audit.get("people_also_ask", "") or ""
        except (json.JSONDecodeError, OSError):
            pass

    markdown = plan_file.read_text(encoding="utf-8")
    report = validate_plan(markdown, paa_raw=paa_raw)

    if as_json:
        click.echo(json.dumps({
            "verdict": report.verdict,
            "h2_count": report.h2_count,
            "paa_covered": report.paa_covered,
            "paa_total": report.paa_total,
            "source_links": report.source_links,
            "stats_found": report.stats_found,
            "violations": [
                {"rule": v.rule, "heading": v.heading, "message": v.message}
                for v in report.violations
            ],
        }, ensure_ascii=False, indent=2))
    else:
        _echo_human(report, plan_file)

    sys.exit(0 if report.ok else 1)


def _echo_human(report, plan_file: Path):
    icon = "✅" if report.ok else "⚠️"
    click.echo(f"{icon} Plan : {report.verdict}   ({plan_file})")
    click.echo(
        f"  H2: {report.h2_count}  |  PAA couvertes: "
        f"{report.paa_covered}/{report.paa_total}  |  "
        f"sources: {report.source_links}  |  stats: {report.stats_found}"
    )
    if report.violations:
        click.echo(f"\n  {len(report.violations)} manquement(s) à corriger :")
        for v in report.violations:
            where = f" [{v.heading}]" if v.heading else ""
            click.echo(f"  • ({v.rule}){where} {v.message}")
    else:
        click.echo("  Aucun manquement — prêt pour la génération.")
