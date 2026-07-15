"""
YTG Batch Audit for all HTML articles in _shared/outputs/.

Scans enseigna.fr and superprof.fr, deduplicates files,
resolves keywords from metadata JSON, then audits each article via YTG API
(guide lookup + SERP scores + content analysis).

Usage:
    python scripts/audit/ytg_batch_audit.py
"""
import json
import re
import time
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

from scripts.audit.ytg_analyzer import YTGAnalyzer
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "_shared" / "outputs"

SITES = ["enseigna", "superprof-ressources"]


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, max_calls=13, window=60.0):
        self.timestamps: list[float] = []
        self.max_calls = max_calls
        self.window = window

    def wait(self):
        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t < self.window]
        if len(self.timestamps) >= self.max_calls:
            sleep_time = self.window - (now - self.timestamps[0]) + 1
            print(f"  [RateLimit] Sleeping {sleep_time:.0f}s...", flush=True)
            time.sleep(sleep_time)
        self.timestamps.append(time.time())


# ---------------------------------------------------------------------------
# File Discovery & Deduplication
# ---------------------------------------------------------------------------

def discover_html_files(site_id: str) -> list[Path]:
    """Find all _refreshed.html files, deduplicate (prefer slug-named)."""
    from _shared.core.tenant_paths import TenantPaths
    base = TenantPaths(base_path=PROJECT_ROOT).output_dir(site_id)
    all_files: list[Path] = []

    for folder in ["html_child_posts", "html_parent_posts"]:
        folder_path = base / folder
        if folder_path.exists():
            all_files.extend(folder_path.glob("*_refreshed.html"))

    # Dedup: group by slug content
    # URL-style: https_cours_particuliers_com_ia_aide_soutien_scolaire_refreshed.html
    # Slug-style: ia-aide-soutien-scolaire_refreshed.html
    site_prefix = "https_" + site_id.replace(".", "_").replace("-", "_") + "_"

    groups: dict[str, list[Path]] = {}
    for f in all_files:
        name = f.stem.replace("_refreshed", "")
        # Normalize: remove site URL prefix, convert _ to -
        if name.startswith(site_prefix):
            normalized = name[len(site_prefix):].replace("_", "-")
        else:
            normalized = name.replace("_", "-")
        # Further normalize
        normalized = normalized.lower().strip("-")

        if normalized not in groups:
            groups[normalized] = []
        groups[normalized].append(f)

    # Pick the slug-named version (shorter name = slug-based)
    deduped: list[Path] = []
    for slug, files in groups.items():
        if len(files) == 1:
            deduped.append(files[0])
        else:
            # Prefer slug-named (shorter filename, no URL prefix)
            slug_files = [f for f in files if not f.name.startswith("https_")]
            deduped.append(slug_files[0] if slug_files else files[0])

    return sorted(deduped, key=lambda f: f.name)


def resolve_keyword(html_path: Path, site_id: str) -> str:
    """Resolve main keyword from metadata JSON or slug."""
    from _shared.core.tenant_paths import TenantPaths
    metadata_dir = TenantPaths(base_path=PROJECT_ROOT).output_dir(site_id) / "metadata"

    # Try multiple matching strategies
    stem = html_path.stem.replace("_refreshed", "")
    site_prefix = "https_" + site_id.replace(".", "_").replace("-", "_") + "_"

    # Strategy 1: direct match with URL-style prefix
    if not stem.startswith("https_"):
        url_stem = site_prefix + stem.replace("-", "_")
    else:
        url_stem = stem

    candidates = [
        metadata_dir / f"{url_stem}_metadata.json",
        metadata_dir / f"{stem}_metadata.json",
    ]

    # Strategy 2: scan all JSON files for partial match
    slug_parts = stem.replace("_", "-").split("-")
    key_parts = slug_parts[:3] if len(slug_parts) >= 3 else slug_parts

    for candidate in candidates:
        if candidate.exists():
            try:
                meta = json.loads(candidate.read_text(encoding="utf-8"))
                kws = meta.get("target_keywords", [])
                if kws:
                    return kws[0]
            except Exception:
                pass

    # Strategy 3: scan JSON dir for partial match
    if metadata_dir.exists():
        for jf in metadata_dir.glob("*_metadata.json"):
            jf_clean = jf.stem.replace("_metadata", "").replace(site_prefix, "").replace("_", "-").lower()
            if all(p in jf_clean for p in key_parts):
                try:
                    meta = json.loads(jf.read_text(encoding="utf-8"))
                    kws = meta.get("target_keywords", [])
                    if kws:
                        return kws[0]
                except Exception:
                    pass

    # Fallback: derive from slug
    slug = stem.replace(site_prefix, "").replace("_", " ").replace("-", " ")
    return slug


# ---------------------------------------------------------------------------
# Main Audit
# ---------------------------------------------------------------------------

def main():
    analyzer = YTGAnalyzer()
    if not analyzer.is_configured:
        print("ERROR: YTG API key not configured. Set YTG_API_KEY in .env")
        sys.exit(1)

    rate = RateLimiter()

    # Build guide index (one API call)
    print("Loading YTG guide index...", flush=True)
    all_guides = analyzer.list_guides_all()
    guide_index: dict[str, str] = {}
    for g in all_guides:
        query = g.get("query", g.get("keyword", ""))
        gid = g.get("id", "")
        if query and gid:
            guide_index[query.lower().strip()] = str(gid)
    print(f"  {len(guide_index)} guides in index\n", flush=True)

    all_results: dict[str, list[dict]] = {}

    for site_id in SITES:
        print(f"\n{'='*80}")
        print(f"  SITE: {site_id}")
        print(f"{'='*80}\n")

        files = discover_html_files(site_id)
        if not files:
            print(f"  No HTML files found for {site_id}")
            continue

        print(f"  {len(files)} articles (after dedup)\n")

        results: list[dict] = []

        for i, html_path in enumerate(files):
            kw = resolve_keyword(html_path, site_id)
            short_name = html_path.name[:50]

            # Find guide
            gid = guide_index.get(kw.lower().strip())
            if not gid:
                # Try partial match
                kw_words = set(kw.lower().split())
                for q, qid in guide_index.items():
                    if kw_words and kw_words.issubset(set(q.split())):
                        gid = qid
                        break

            if not gid:
                results.append({
                    "kw": kw, "html_file": html_path.name,
                    "folder": html_path.parent.name,
                    "status": "NO_GUIDE",
                })
                print(f"  [{i+1}/{len(files)}] {short_name}: NO_GUIDE ({kw})", flush=True)
                continue

            # Read HTML
            html = html_path.read_text(encoding="utf-8")
            text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

            # Fetch SERP scores
            rate.wait()
            try:
                serp = analyzer.fetch_serp_scores(gid) or {}
            except Exception as e:
                serp = {}
                print(f"    SERP error: {e}", flush=True)

            # Analyze content
            rate.wait()
            try:
                analysis = analyzer.analyze_content(gid, text)
            except Exception as e:
                results.append({
                    "kw": kw, "html_file": html_path.name,
                    "folder": html_path.parent.name,
                    "guide_id": gid, "status": "ANALYZE_FAIL",
                })
                print(f"  [{i+1}/{len(files)}] {short_name}: ANALYZE_FAIL", flush=True)
                continue

            if not analysis:
                results.append({
                    "kw": kw, "html_file": html_path.name,
                    "folder": html_path.parent.name,
                    "guide_id": gid, "status": "ANALYZE_FAIL",
                })
                print(f"  [{i+1}/{len(files)}] {short_name}: ANALYZE_FAIL", flush=True)
                continue

            our_s = analysis["our_soseo"]
            our_d = analysis["our_dseo"]
            t3s = serp.get("top3_soseo", 0)
            t3d = serp.get("top3_dseo", 0)
            tmin = analysis.get("target_soseo_min", 0)
            dmax = analysis.get("target_dseo_max", 0)

            # Verdict based on TOP 3 comparison
            # Target: SOSEO >= top3_soseo, DSEO <= top3_dseo
            target_s = t3s if t3s > 0 else tmin
            target_d = t3d if t3d > 0 else dmax

            if our_s >= target_s and our_d <= target_d:
                verdict = "OK"
            elif our_s >= target_s * 0.85 and our_d <= target_d * 1.15:
                verdict = "CLOSE"
            else:
                verdict = "NEEDS_FIX"

            result = {
                "kw": kw,
                "html_file": html_path.name,
                "html_path": str(html_path),
                "folder": html_path.parent.name,
                "guide_id": gid,
                "soseo": our_s,
                "dseo": our_d,
                "top3_soseo": t3s,
                "top3_dseo": t3d,
                "target_min": target_s,
                "dseo_max": target_d,
                "verdict": verdict,
                "term_colors": analysis.get("term_colors", {}),
                "term_scores": analysis.get("term_scores", {}),
                "term_targets": analysis.get("term_targets", {}),
            }
            results.append(result)

            icon = "OK" if verdict == "OK" else ("~" if verdict == "CLOSE" else "FIX")
            print(
                f"  [{i+1}/{len(files)}] {short_name}: "
                f"S={our_s:.0f}% D={our_d:.0f}% "
                f"(TOP3: S={t3s:.0f} D={t3d:.0f}) [{icon}]",
                flush=True,
            )

        # Save results
        from _shared.core.tenant_paths import TenantPaths
        out_path = TenantPaths(base_path=PROJECT_ROOT).output_dir(site_id) / "ytg_batch_results.json"
        out_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        all_results[site_id] = results
        print(f"\n  Saved: {out_path}")

    # Final summary
    print(f"\n\n{'='*120}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*120}\n")

    print(f"{'Site':<25} | {'Article':<45} | {'KW':<30} | {'SOSEO':>6} | {'DSEO':>5} | {'TOP3 S':>7} | {'TOP3 D':>7} | Verdict")
    print(f"{'-'*120}")

    total_ok = total_close = total_fix = total_fail = 0

    for site_id, results in all_results.items():
        for r in sorted(results, key=lambda x: (
            0 if x.get("verdict") == "OK" else 1 if x.get("verdict") == "CLOSE" else 2,
            -(x.get("soseo", 0)),
        )):
            if "status" in r:
                print(f"{site_id:<25} | {r['html_file'][:45]:<45} | {r['kw'][:30]:<30} | {r['status']}")
                total_fail += 1
                continue

            v = r["verdict"]
            if v == "OK":
                total_ok += 1
            elif v == "CLOSE":
                total_close += 1
            else:
                total_fix += 1

            print(
                f"{site_id:<25} | {r['html_file'][:45]:<45} | {r['kw'][:30]:<30} | "
                f"{r['soseo']:>6.0f} | {r['dseo']:>5.0f} | {r['top3_soseo']:>7.0f} | "
                f"{r['top3_dseo']:>7.0f} | {v}"
            )

    analyzed = total_ok + total_close + total_fix
    print(f"\nTotal: {analyzed + total_fail} | OK: {total_ok} | CLOSE: {total_close} | NEEDS_FIX: {total_fix} | FAIL: {total_fail}")

    if analyzed:
        all_s = [r["soseo"] for rs in all_results.values() for r in rs if "soseo" in r]
        all_d = [r["dseo"] for rs in all_results.values() for r in rs if "dseo" in r]
        print(f"Avg SOSEO: {sum(all_s)/len(all_s):.1f}% | Avg DSEO: {sum(all_d)/len(all_d):.1f}%")


if __name__ == "__main__":
    main()
