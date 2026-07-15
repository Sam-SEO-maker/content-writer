"""Pousse les articles refreshés (Gutenberg) sur WordPress via l'API REST.

Pour chaque URL fournie :
1. Résout le post WP (par slug)
2. Sauvegarde la version live actuelle dans wp_backups/{id}_before.json (si absente)
3. POST title + content (gutenberg) + meta SEOPress (titre + description), status=publish

Usage:
    python -m scripts.utils.push_to_wp <fichier_urls.txt>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from scripts.scraping.wordpress_api_client import WordPressAPIClient

from _shared.core.tenant_paths import TenantPaths

_TENANT = "superprof-ressources"
_TP = TenantPaths()
BLOG_CFG = _TP.blog_config(_TENANT)
OUT = _TP.output_dir(_TENANT)
BACKUPS = OUT / "wp_backups"


def _slug(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_")


def build_client() -> WordPressAPIClient:
    cfg = json.loads(BLOG_CFG.read_text())["wp_api_config"]
    return WordPressAPIClient(
        api_base_url=cfg["api_base_url"],
        user_env_var=cfg["user_env_var"],
        password_env_var=cfg["password_env_var"],
        timeout=cfg.get("timeout", 30),
    )


def push_url(client: WordPressAPIClient, url: str) -> dict:
    slug = _slug(url)
    gut = OUT / "html" / f"{slug}_refreshed.gutenberg.html"
    meta_p = OUT / "metadata" / f"{slug}_metadata.json"
    if not gut.exists():
        return {"url": url, "ok": False, "error": "no_gutenberg_file"}
    if not meta_p.exists():
        return {"url": url, "ok": False, "error": "no_metadata_file"}

    content = gut.read_text(encoding="utf-8")
    meta = json.loads(meta_p.read_text(encoding="utf-8"))

    post = client.get_post_by_url(url)
    if not post:
        return {"url": url, "ok": False, "error": "post_not_found"}
    pid = post["id"]

    # Backup once
    BACKUPS.mkdir(parents=True, exist_ok=True)
    bkp = BACKUPS / f"{pid}_before.json"
    if not bkp.exists():
        bkp.write_text(json.dumps({
            "id": pid, "slug": post.get("slug"),
            "title": post.get("title"), "raw": post.get("raw"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    wp_meta = {
        "_seopress_titles_title": meta.get("title", ""),
        "_seopress_titles_desc": meta.get("meta_description", ""),
    }
    res = client.update_post(
        post_id=pid,
        title=meta.get("title"),
        content=content,
        meta=wp_meta,
        status="publish",
    )
    return {"url": url, "id": pid, "ok": res["ok"], "error": res["error"]}


def main() -> int:
    load_dotenv()
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.utils.push_to_wp <fichier_urls.txt>")
        return 2
    urls = [l.strip() for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
    client = build_client()
    ok = fail = 0
    for i, url in enumerate(urls, 1):
        r = push_url(client, url)
        if r["ok"]:
            ok += 1
            print(f"[{i:>2}/{len(urls)}] ✓ id={r.get('id')} {url.split('/ressources/')[1]}")
        else:
            fail += 1
            print(f"[{i:>2}/{len(urls)}] ✗ {r.get('error')} :: {url}")
    print(f"\nPushed OK: {ok} | Failed: {fail}")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
