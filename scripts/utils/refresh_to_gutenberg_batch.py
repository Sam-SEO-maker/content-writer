"""
Batch convertisseur HTML → Gutenberg pour les outputs existants.

Pour chaque article dans `_shared/outputs/{site}/html/*_refreshed.html` (ou tests/) :
- Lit le H1 éditorial depuis metadata.seo.h1 OU depuis le HTML existant
- Retire les anciens wrappers <article>, <section class="introduction"> s'ils existent
- Applique gutenberg_formatter.to_gutenberg() pour wrapper chaque élément en bloc <!-- wp:* -->
- Préfixe avec le bloc H1 Gutenberg
- Sauvegarde en *_refreshed.gutenberg.html (ou *_seraphine.gutenberg.html pour les tests Andra)

Usage:
    python scripts/utils/refresh_to_gutenberg_batch.py [--dry-run] [--keep-source]

Par défaut, le .html nu source est SUPPRIMÉ une fois le .gutenberg.html écrit
avec succès (c'est l'artefact de build, pas un livrable). Utiliser --keep-source
pour le conserver (ex. si un audit/linking qui lit *_refreshed.html doit suivre).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Tuple

from bs4 import BeautifulSoup, Comment

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.utils.gutenberg_formatter import to_gutenberg

OUTPUTS_ROOT = REPO_ROOT / "_shared" / "outputs"


def wrap_h1_block(h1_text: str) -> str:
    return (
        '<!-- wp:heading {"level":1} -->\n'
        f'<h1 class="wp-block-heading">{h1_text}</h1>\n'
        '<!-- /wp:heading -->'
    )


def strip_wrappers(html: str) -> Tuple[str, Optional[str]]:
    """Retire <article>, <section> et commentaires d'en-tête ; renvoie (inner_html, h1_text_si_trouvé)."""
    soup = BeautifulSoup(html, "html.parser")

    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()

    h1_tag = soup.find("h1")
    h1_text = h1_tag.get_text(strip=True) if h1_tag else None
    if h1_tag:
        h1_tag.decompose()

    article = soup.find("article")
    if article:
        article.unwrap()

    for section in soup.find_all("section"):
        section.unwrap()

    return str(soup), h1_text


def find_metadata(html_path: Path, metadata_dir: Path) -> Optional[dict]:
    """Cherche le metadata.json correspondant à un fichier HTML."""
    stem = html_path.stem.replace("_refreshed", "").replace("_seraphine", "")
    candidates = [
        metadata_dir / f"{stem}_metadata.json",
        metadata_dir / f"{html_path.stem.replace('_refreshed', '')}_metadata.json",
    ]
    for c in candidates:
        if c.exists():
            try:
                return json.loads(c.read_text(encoding="utf-8"))
            except Exception:
                pass
    return None


def get_h1_from_metadata(meta: dict) -> Optional[str]:
    """Extrait le H1 depuis metadata.json (essaie plusieurs emplacements)."""
    if not meta:
        return None
    return meta.get("h1") or meta.get("seo", {}).get("h1")


def convert_file(html_path: Path, metadata_dir: Optional[Path], dry_run: bool = False,
                 delete_source: bool = True) -> dict:
    """Convertit un fichier HTML brut en Gutenberg flat."""
    raw = html_path.read_text(encoding="utf-8")

    inner_html, h1_from_body = strip_wrappers(raw)

    h1 = None
    source = None
    if metadata_dir:
        meta = find_metadata(html_path, metadata_dir)
        h1_meta = get_h1_from_metadata(meta) if meta else None
        if h1_meta:
            h1 = h1_meta
            source = "metadata.seo.h1"

    if not h1 and h1_from_body:
        h1 = h1_from_body
        source = "<h1> in body"

    if not h1:
        return {"path": html_path, "status": "SKIP_NO_H1"}

    gutenberg_body = to_gutenberg(inner_html)
    final = wrap_h1_block(h1) + "\n\n" + gutenberg_body + "\n"

    if html_path.name.endswith("_seraphine.html"):
        out_path = html_path.with_name(html_path.stem + ".gutenberg.html")
    else:
        out_path = html_path.with_name(html_path.stem.replace("_refreshed", "_refreshed.gutenberg") + ".html")
        if "gutenberg" not in out_path.stem:
            out_path = html_path.with_name(html_path.stem + ".gutenberg.html")

    deleted_source = False
    if not dry_run:
        out_path.write_text(final, encoding="utf-8")
        # Le .html nu est la source de build, pas un livrable : on le supprime
        # une fois le gutenberg écrit avec succès (sauf --keep-source).
        if delete_source and out_path.exists() and out_path.stat().st_size > 0:
            html_path.unlink()
            deleted_source = True

    return {"path": html_path, "out": out_path, "h1": h1, "source": source,
            "status": "OK", "deleted_source": deleted_source}


def process_site(site_dir: Path, dry_run: bool = False, delete_source: bool = True) -> list:
    """Traite tous les *_refreshed.html d'un dossier site."""
    html_dir = site_dir / "html"
    metadata_dir = site_dir / "metadata"
    if not html_dir.exists():
        return []

    results = []
    for f in sorted(html_dir.glob("*_refreshed.html")):
        if "gutenberg" in f.stem:
            continue
        results.append(convert_file(f, metadata_dir if metadata_dir.exists() else None, dry_run, delete_source))
    return results


def process_tests_andra(dry_run: bool = False, delete_source: bool = True) -> list:
    """Traite les fichiers tests/seraphine_andra/html/*_seraphine.html."""
    from _shared.core.tenant_paths import TenantPaths
    tests_dir = TenantPaths(base_path=REPO_ROOT).output_dir("superprof-ressources") / "tests" / "seraphine_andra" / "html"
    if not tests_dir.exists():
        return []

    results = []
    for f in sorted(tests_dir.glob("*_seraphine.html")):
        if "gutenberg" in f.stem:
            continue
        results.append(convert_file(f, metadata_dir=None, dry_run=dry_run, delete_source=delete_source))
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Simulate without writing files")
    ap.add_argument("--keep-source", action="store_true",
                    help="Conserve le .html nu source (par défaut : supprimé après build gutenberg réussi)")
    args = ap.parse_args()
    delete_source = not args.keep_source

    print("=" * 70)
    print("Batch HTML → Gutenberg conversion")
    print("=" * 70)

    all_results = []
    from _shared.core.tenant_paths import TenantPaths
    for site in ("superprof-ressources", "enseigna"):
        site_dir = TenantPaths(base_path=REPO_ROOT).output_dir(site)
        results = process_site(site_dir, dry_run=args.dry_run, delete_source=delete_source)
        if results:
            print(f"\n[{site}] {len(results)} fichiers traités")
            for r in results:
                emoji = "✓" if r["status"] == "OK" else "⚠"
                msg = f"  {emoji} {r['path'].name} → {r['status']}"
                if r["status"] == "OK":
                    msg += f" (H1 from {r['source']})"
                    if r.get("deleted_source"):
                        msg += " [source supprimée]"
                print(msg)
            all_results.extend(results)

    tests_results = process_tests_andra(dry_run=args.dry_run, delete_source=delete_source)
    if tests_results:
        print(f"\n[tests Andra] {len(tests_results)} fichiers traités")
        for r in tests_results:
            emoji = "✓" if r["status"] == "OK" else "⚠"
            msg = f"  {emoji} {r['path'].name} → {r['status']}"
            if r["status"] == "OK":
                msg += f" (H1 from {r['source']})"
            print(msg)
        all_results.extend(tests_results)

    print("\n" + "=" * 70)
    ok = sum(1 for r in all_results if r["status"] == "OK")
    skipped = sum(1 for r in all_results if r["status"] != "OK")
    print(f"Résumé : {ok} OK, {skipped} skipped, {len(all_results)} total")
    if args.dry_run:
        print("(--dry-run : aucun fichier écrit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
