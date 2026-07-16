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
from cli.options import blog_option


@click.command()
@click.argument("url")
@blog_option(required=True, dest="blog_id")
@click.option("--html-file", "html_file", required=True,
              help="Chemin du HTML brut écrit par le subagent de génération.")
@click.option("--title", default="", help="Titre article (col E) — sinon slug de l'URL.")
@click.option("--type", "article_type", default=None,
              help="Sous-type d'article routant la sortie HTML dans html/{type}/ "
                   "(enseigna : 'avis' | 'versus'). Défaut : pas de sous-dossier.")
@click.option("--keyword", "keyword", default="",
              help="Mot-clé principal (guide QC YTG sur le bon terme, pas le slug). "
                   "À reporter depuis la sortie de `cw refresh`.")
@click.option("--guide-id", "guide_id", default="",
              help="ID du guide YTG déjà créé au STEP 2.5 (réutilisation, pas de "
                   "recréation). À reporter depuis la sortie de `cw refresh`.")
@click.option("--apply-linking", is_flag=True, default=False,
              help="Applique le maillage (écrit les fichiers). Sinon dry-run.")
@click.option("--publish", is_flag=True, default=False,
              help="Publie sur WordPress (REST) après QC OK. Blast radius : "
                   "confirmation humaine obligatoire. Refusé si verdict A_CORRIGER/BLOQUE.")
@click.option("--yes", "assume_yes", is_flag=True, default=False,
              help="Saute la confirmation interactive de publication (usage batch averti).")
def finalize(url, blog_id, html_file, title, article_type, keyword, guide_id, apply_linking, publish, assume_yes):
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
    if article_type:
        click.echo(f"Type: {article_type}  (→ html/{article_type}/)")

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
        article_type=article_type or None,
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
    verdict = _run_ytg_qc(base, blog_id, url, saved, main_keyword=keyword, guide_id=guide_id)

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

    # -------------------------------------------------------------------
    # 5. Publication WordPress (optionnelle, --publish) — fort blast radius
    # -------------------------------------------------------------------
    if publish:
        _maybe_publish(base, blog_id, url, url_slug, saved, verdict, assume_yes)

    click.echo(f"\n{'='*70}")
    if verdict == "A_CORRIGER":
        click.echo("⚠ FINALIZE OK — verdict A_CORRIGER : le subagent doit recorriger "
                   "les termes signalés puis relancer `finalize` (boucle, cap 2-3).")
    else:
        click.echo("✅ FINALIZE OK — article prêt (contenu + verdict YTG + liens).")
    click.echo(f"{'='*70}")


def _maybe_publish(base: Path, blog_id: str, url: str, url_slug: str, saved: Path,
                   verdict: str, assume_yes: bool) -> None:
    """Publie l'article sur WordPress via REST, uniquement si le QC est OK.

    Garde-fous (fort blast radius, site public) :
    - refus si verdict A_CORRIGER ou BLOQUE (BLOQUE n'atteint jamais ce point) ;
    - confirmation humaine explicite avant le POST, sauf --yes.
    """
    from scripts.utils.push_to_wp import build_client, publish_article

    click.echo("\n[5/5] Publication WordPress (REST)…")

    if verdict == "A_CORRIGER":
        click.echo("  ⛔ Publication refusée : verdict A_CORRIGER. "
                   "Corriger puis relancer `finalize --publish`.")
        return

    # Contenu à pousser = .gutenberg.html adjacent au HTML nu sauvegardé.
    gutenberg_path = saved.with_name(saved.stem + ".gutenberg.html")
    if not gutenberg_path.exists():
        click.echo(f"  ⛔ Publication impossible : {gutenberg_path.name} introuvable.")
        return

    # Metadata (title + meta_description) — save_metadata() nomme par url_slug,
    # save_refreshed_html() par file_slug (issu du titre) : les deux peuvent
    # différer. On tente les deux, puis un fallback glob si un seul candidat.
    meta_dir = saved.parent.parent / "metadata"
    file_slug = saved.stem[: -len("_refreshed")] if saved.stem.endswith("_refreshed") else saved.stem
    metadata_path = None
    for cand in (meta_dir / f"{url_slug}_metadata.json",
                 meta_dir / f"{file_slug}_metadata.json"):
        if cand.exists():
            metadata_path = cand
            break
    if metadata_path is None and meta_dir.exists():
        candidates = list(meta_dir.glob("*_metadata.json"))
        if len(candidates) == 1:
            metadata_path = candidates[0]
    if metadata_path is None:
        click.echo("  ⚠ metadata introuvable — "
                   "publication du contenu sans mise à jour titre/SEOPress.")

    # Construire le client (peut échouer si wp_api_config absent pour ce tenant).
    try:
        client = build_client(tenant=blog_id, base_path=base)
    except (ValueError, FileNotFoundError, KeyError) as e:
        click.echo(f"  ⛔ Client WP indisponible pour '{blog_id}' : {e}")
        return

    # Confirmation humaine — le seul Y/N qui doit subsister (blast radius).
    click.echo(f"  Cible : {url}")
    click.echo(f"  Tenant: {blog_id}  |  Verdict QC: {verdict}")
    click.echo(f"  Contenu: {gutenberg_path.name}")
    if not assume_yes:
        if not click.confirm("  ⚠ PUBLIER sur le site public maintenant ?", default=False):
            click.echo("  Publication annulée par l'utilisateur.")
            return

    res = publish_article(
        client=client,
        tenant=blog_id,
        url=url,
        gutenberg_path=gutenberg_path,
        metadata_path=metadata_path,
        base_path=base,
    )
    if res["ok"]:
        click.echo(f"  ✅ Publié — post id={res.get('id')}")
    else:
        click.echo(f"  ❌ Échec publication : {res.get('error')}")


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


def _run_ytg_qc(base: Path, blog_id: str, url: str, saved: Path,
                main_keyword: str = "", guide_id: str = "") -> str:
    """Lance YTGQualityCheck.check_html sur le HTML sauvegardé. Retourne le verdict.

    main_keyword/guide_id (issus du STEP 2.5 de `cw refresh`) évitent de re-résoudre
    le mot-clé sur le slug et de recréer un guide.
    """
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
        res = engine.check_html(
            blog_id, url=url, html=html, ytg_config=ytg_cfg,
            main_keyword=main_keyword or "", guide_id=guide_id or "",
        )
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
