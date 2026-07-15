"""
Commande `finalize` — chaîne déterministe post-génération (Phase 3bis).

À lancer APRÈS que le subagent `content-generator` a écrit le HTML brut. Chaîne :
  1. save_refreshed_html()  → HTML nu + .gutenberg.html + CSV tableaux
  2. AssetManager           → valide + restaure les assets (Règle d'Or)
  3. YTGQualityCheck        → verdict OPTIMAL / A_CORRIGER / BLOQUE
  4. Maillage               → EnseignaAvisLinker (enseigna) ; rappel directive
                              SuperprofRotator (superprof, injectée pré-génération)

La GÉNÉRATION reste hors de cette commande (subagent, abonnement Max). `finalize`
est déterministe et re-jouable : un second passage après correction d'un
A_CORRIGER refait save → QC → maillage sans régénérer.
"""

import json
from pathlib import Path

import click


@click.command()
@click.argument("url")
@click.option("--blog", "blog_id", required=True, help="Blog ID (enseigna, superprof-ressources, …)")
@click.option("--html-file", "html_file", required=True,
              help="Chemin du HTML brut écrit par le subagent de génération.")
@click.option("--title", default="", help="Titre article (col E) — sinon slug de l'URL.")
@click.option("--apply-linking", is_flag=True, default=False,
              help="Applique le maillage (écrit les fichiers). Sinon dry-run.")
def finalize(url, blog_id, html_file, title, apply_linking):
    """
    Chaîne post-génération : save → assets → QC YTG → maillage.

    URL de l'article, --blog le tenant, --html-file le HTML brut généré.
    """
    base = Path.cwd()
    html_path = Path(html_file)
    if not html_path.is_absolute():
        html_path = base / html_path
    if not html_path.exists():
        click.echo(f"[ERREUR] HTML introuvable : {html_path}", err=True)
        raise click.Abort()

    html = html_path.read_text(encoding="utf-8")
    url_slug = url.rstrip("/").rsplit("/", 1)[-1]

    click.echo(f"\n{'='*70}")
    click.echo("FINALIZE (post-génération)")
    click.echo(f"{'='*70}")
    click.echo(f"URL:  {url}")
    click.echo(f"Blog: {blog_id}")

    # -------------------------------------------------------------------
    # 1. Sauvegarde (nu + gutenberg + CSV)
    # -------------------------------------------------------------------
    click.echo("\n[1/4] Sauvegarde (nu + gutenberg + CSV)…")
    from scripts.utils.output_manager import OutputManager

    om = OutputManager(base_path=base)
    saved = om.save_refreshed_html(
        site_id=blog_id,
        url_slug=url_slug,
        html_content=html,
        title=title or None,
    )
    click.echo(f"  ✓ {saved}")

    # -------------------------------------------------------------------
    # 2. Validation des assets (Règle d'Or)
    # -------------------------------------------------------------------
    click.echo("\n[2/4] Validation des assets (Règle d'Or)…")
    assets_report = _validate_assets(base, blog_id, url, html, saved)
    click.echo(f"  {assets_report}")

    # -------------------------------------------------------------------
    # 3. QC sémantique YTG
    # -------------------------------------------------------------------
    click.echo("\n[3/4] QC sémantique YTG…")
    verdict = _run_ytg_qc(base, blog_id, url, saved)

    # BLOQUE = problème de fond → arrêt + alerte humaine (pas de maillage)
    if verdict == "BLOQUE":
        click.echo("\n❌ Verdict BLOQUE — arrêt. Sur-optimisation grave : "
                   "revue humaine requise, pas de re-génération automatique.")
        click.echo("   Maillage NON appliqué (article non finalisable en l'état).")
        return

    # -------------------------------------------------------------------
    # 4. Maillage interne
    # -------------------------------------------------------------------
    click.echo("\n[4/4] Maillage interne…")
    _run_linking(base, blog_id, url, apply_linking)

    click.echo(f"\n{'='*70}")
    if verdict == "A_CORRIGER":
        click.echo("⚠ FINALIZE OK — verdict A_CORRIGER : le subagent doit recorriger "
                   "les termes signalés puis relancer `finalize` (boucle, cap 2-3).")
    else:
        click.echo("✅ FINALIZE OK — article prêt (contenu + verdict YTG + liens).")
    click.echo(f"{'='*70}")


def _validate_assets(base: Path, blog_id: str, url: str, html: str, saved: Path) -> str:
    """Valide assets_after ≥ assets_before via AssetManager + le contexte d'audit."""
    from scripts.assets.asset_manager import AssetManager

    # Assets baseline : audit_data.json du contexte (écrit à l'étape refresh)
    from scripts.audit.ytg_qc import url_to_context_slug
    slug = url_to_context_slug(url)
    audit_path = base / "_shared" / "context" / slug / "audit_data.json"
    if not audit_path.exists():
        return "baseline introuvable (audit_data.json absent) — validation ignorée."

    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"baseline illisible ({str(e)[:60]}) — validation ignorée."

    original_assets = {"counts": audit.get("assets_counts", {})}
    if not original_assets["counts"]:
        return "counts baseline vides — validation ignorée."

    am = AssetManager()
    result = am.validate(original_assets=original_assets, new_content=html)
    if getattr(result, "is_valid", True):
        return "✓ assets préservés (après ≥ avant)."

    # Tentative de restauration
    restored = am.restore_missing_assets(html, original_assets, result)
    if restored != html:
        saved.write_text(restored, encoding="utf-8")
        return "assets manquants restaurés et réécrits."
    return "⚠ assets manquants NON restaurables — à vérifier manuellement."


def _run_ytg_qc(base: Path, blog_id: str, url: str, saved: Path) -> str:
    """Lance YTGQualityCheck.check_html sur le HTML sauvegardé. Retourne le verdict."""
    from scripts.audit.ytg_qc import (
        YTGQualityCheck, VERDICT_A_CORRIGER, VERDICT_BLOQUE, VERDICT_SKIP,
    )

    from _shared.core.tenant_paths import TenantPaths
    cfg_path = TenantPaths(base_path=base).blog_config(blog_id)
    ytg_cfg = {}
    if cfg_path.exists():
        try:
            ytg_cfg = json.loads(cfg_path.read_text(encoding="utf-8")).get("ytg", {}) or {}
        except Exception:
            ytg_cfg = {}
    if ytg_cfg.get("enabled") is False:
        click.echo("  YTG désactivé pour ce blog — QC ignoré.")
        return VERDICT_SKIP

    try:
        engine = YTGQualityCheck()
        html = saved.read_text(encoding="utf-8")
        res = engine.check_html(blog_id, url=url, html=html, ytg_config=ytg_cfg)
        res.html_path = str(saved)
        engine.persist(res)
        click.echo(f"  Verdict: {res.verdict} — {res.message}")
        if res.verdict == VERDICT_A_CORRIGER and res.under_optimized_terms:
            click.echo(f"  À enrichir : {', '.join(res.under_optimized_terms[:8])}")
        if res.verdict == VERDICT_A_CORRIGER and res.over_optimized_terms:
            click.echo(f"  À réduire  : {', '.join(res.over_optimized_terms[:8])}")
        return res.verdict
    except Exception as e:
        click.echo(f"  QC non-bloquant, erreur ignorée : {str(e)[:120]}")
        return VERDICT_SKIP


def _run_linking(base: Path, blog_id: str, url: str, apply_linking: bool):
    """Applique le maillage selon le tenant."""
    if blog_id == "enseigna":
        from scripts.linking.enseigna_avis_linker import EnseignaAvisLinker

        linker = EnseignaAvisLinker(base_path=base)
        results = linker.process(urls=[url], dry_run=not apply_linking)
        for r in results:
            if r.error:
                click.echo(f"  ⚠ {r.url} : {r.error}")
            else:
                click.echo(f"  {r.url} : {len(r.links_added)} lien(s) "
                           f"{'appliqué(s)' if apply_linking else 'planifié(s) (dry-run)'}")
        if not apply_linking:
            click.echo("  (dry-run — relancer avec --apply-linking pour écrire)")
    elif blog_id == "superprof-ressources":
        click.echo("  Superprof : les liens de landing sont injectés par "
                   "SuperprofRotator.get_prompt_directive() AVANT la génération. "
                   "Vérifier leur présence dans le HTML généré.")
    else:
        click.echo(f"  Aucun maillage automatique câblé pour '{blog_id}'.")
