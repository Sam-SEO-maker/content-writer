"""Full YTG audit — adapt SLUGS and BASE to target site."""
import json
import time
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

from scripts.audit.ytg_analyzer import YTGAnalyzer
from scripts.sheets.sheets_client import SheetsClient
from bs4 import BeautifulSoup

SLUGS = [
    "le-sport-a-jeun-que-faut-il-savoir",
    "sports-conseils-perte-de-poids",
    "hormones-et-sport",
    "preparateur-mental-sport",
    "les-principaux-exercices-de-crossfit",
    "tout-savoir-sur-le-velo-elliptique",
    "exercices-triceps-elastiques",
    "curl-biceps-musculation",
    "musculation-des-biceps",
    "curl-zottman",
    "exercices-pour-muscler-les-biceps",
    "musculation-developpe-militaire",
    "exercices-musculation-epaules",
    "exercices-de-musculation-celebres",
    "alimentation-pour-recuperation-musculaire",
    "sports-alimentation-perte-de-poids",
    "coaching-sportif-comment-se-muscler",
    "coaching-sportif-comment-se-muscler-le-dos",
    "comment-ameliorer-le-retour-veineux-des-jambes",
    "courses-faut-il-favoriser-la-vitesse-ou-lendurance-pour-maigrir",
    "tout-savoir-sur-le-crossfit",
    "connaitre-les-bases-de-la-nutrition-pour-perdre-du-poids",
    "quest-ce-que-la-chrononutrition",
    "quels-aliments-pour-augmenter-ma-masse-musculaire",
    "le-regime-mediterraneen-pour-manger-equilibre",
    "hydratation-performance-sportive",
    "vitamines-mineraux-sport",
    "tout-savoir-sur-la-nutrition-sportive",
    "les-exercices-a-faire-pour-muscler-ses-abdos-fessiers",
    "les-erreurs-de-debutant-a-eviter-en-crossfit",
    "tout-savoir-sur-la-natation",
    "quels-sont-les-bienfaits-de-la-natation",
    "coaching-sportif-lyon",
    "choix-coaching-sportif-lyon",
    "muscles-corps-humain",
    "coach-perdre-du-poids-lyon",
    "type-de-boxe-quest-ce-que-la-boxe-anglaise",
    "anatomie-muscles-du-dos",
    "comment-bien-utiliser-un-velo-elliptique",
    "erreurs-exercices-biceps",
    "aquabike-lyon-lieux-de-pratique",
    "quest-ce-que-la-boxe-americaine",
    "etirements-musculation-triceps",
    "conseils-exercices-triceps",
    "quels-etirements-pour-soulager-les-jambes-lourdes",
    "coaching-sportif-quel-sport-contre-les-jambes-lourdes",
    "conseils-musculation-lyon",
    "construction-programme-crossfit",
    "quelle-est-lhistoire-du-crossfit",
    "les-avantages-de-la-cuisson-a-la-vapeur-pour-perdre-du-poids",
    "quelle-est-lhistoire-de-la-natation",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
from _shared.core.tenant_paths import TenantPaths
BASE = TenantPaths(base_path=PROJECT_ROOT).output_dir("enseigna")


def main():
    analyzer = YTGAnalyzer()

    # Guide index
    all_guides = analyzer.list_guides_all()
    guide_index = {
        g.get("query", "").lower().strip(): str(g.get("id", ""))
        for g in all_guides if g.get("query")
    }
    print(f"Guide index: {len(guide_index)} entries", flush=True)

    # Keyword mapping from spreadsheet
    # ⚠️ OBSOLÈTE : onglet "Refreshs_Audit" + ancien spreadsheet ID. Script legacy —
    # préférer `cw ytg qc --blog enseigna` (scripts/audit/ytg_qc.py) qui lit les
    # onglets réels ("Avis"/"Versus") via KeywordResolver.
    sc = SheetsClient("1F99FtN8fWQlQm0ZTJphBRz_c64iDs2DvohyHyM2Tk1M")
    rows = sc._sheets_service.spreadsheets().values().get(
        spreadsheetId=sc.spreadsheet_id, range="Refreshs_Audit!A:D"
    ).execute().get("values", [])
    slug_to_kw = {}
    for r in rows[1:]:
        if len(r) > 3 and r[0] == "enseigna.fr":
            s = r[2].strip("/").split("/")[-1]
            slug_to_kw[s] = r[3]

    # All HTML files
    all_html = list(BASE.glob("html_child_posts/*.html")) + list(BASE.glob("html_parent_posts/*.html"))

    def find_html(slug):
        slug_u = slug.replace("-", "_")
        for suffix in ["_corrected.html", "_refreshed.html"]:
            for f in all_html:
                fn = f.name
                fn_clean = fn.replace("https_enseigna_fr_", "").replace("_corrected.html", "").replace("_refreshed.html", "")
                if slug_u == fn_clean or slug_u in fn_clean or slug in fn_clean.replace("_", "-"):
                    candidate = f.parent / (fn.split("_refreshed")[0].split("_corrected")[0] + suffix)
                    if candidate.exists():
                        return candidate
        return None

    # Rate limiter
    api_times = []

    def rate_wait():
        now = time.time()
        api_times[:] = [t for t in api_times if now - t < 60]
        if len(api_times) >= 13:
            sl = 60 - (now - api_times[0]) + 1
            print(f"  [RL] {sl:.0f}s...", flush=True)
            time.sleep(sl)
        api_times.append(time.time())

    results = []
    for i, slug in enumerate(SLUGS):
        kw = slug_to_kw.get(slug, "")
        if not kw:
            results.append({"slug": slug, "status": "NO_KW"})
            print(f"  [{i+1}/51] {slug[:35]}: NO_KW", flush=True)
            continue

        gid = guide_index.get(kw.lower().strip())
        if not gid:
            results.append({"slug": slug, "kw": kw, "status": "NO_GUIDE"})
            print(f"  [{i+1}/51] {slug[:35]}: NO_GUIDE ({kw})", flush=True)
            continue

        hf = find_html(slug)
        if not hf:
            results.append({"slug": slug, "kw": kw, "status": "NO_HTML"})
            print(f"  [{i+1}/51] {slug[:35]}: NO_HTML", flush=True)
            continue

        is_corrected = "_corrected" in hf.name
        text = BeautifulSoup(hf.read_text(encoding="utf-8"), "html.parser").get_text(" ", strip=True)

        rate_wait()
        try:
            serp = analyzer.fetch_serp_scores(gid) or {}
        except Exception:
            serp = {}

        rate_wait()
        try:
            an = analyzer.analyze_content(gid, text)
        except Exception:
            an = None

        if not an:
            results.append({"slug": slug, "kw": kw, "status": "ANALYZE_FAIL", "file": hf.name})
            print(f"  [{i+1}/51] {slug[:35]}: FAIL", flush=True)
            continue

        s, d = an["our_soseo"], an["our_dseo"]
        tmin = an.get("target_soseo_min", 0)
        tmax = an.get("target_soseo_max", 0)
        dmax = an.get("target_dseo_max", 0)
        t3s = serp.get("top3_soseo", 0)
        t3d = serp.get("top3_dseo", 0)

        in_target = s >= tmin and d <= dmax
        v = "OK" if in_target else ("CLOSE" if s >= tmin * 0.85 and d <= dmax * 1.15 else "MISS")
        tag = "C" if is_corrected else "R"

        results.append({
            "slug": slug, "kw": kw,
            "soseo": s, "dseo": d,
            "target_min": tmin, "target_max": tmax, "dseo_max": dmax,
            "top3_soseo": t3s, "top3_dseo": t3d,
            "file": hf.name, "is_corrected": is_corrected,
            "verdict": v,
        })
        print(f"  [{i+1}/51] {slug[:35]}: S={s:.0f} D={d:.0f} [{v}] ({tag})", flush=True)

    # Save
    out = BASE / "ytg_final_audit.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # Summary table
    print(f"\n{'='*140}")
    print(f"{'URL slug':<50} | {'KW':<30} | {'SOSEO':>6} | {'DSEO':>5} | {'Cible':>12} | {'Src':>3} | Verdict")
    print(f"{'-'*140}")

    ok = close = miss = fail = 0
    for r in sorted(results, key=lambda x: (0 if x.get("verdict") == "OK" else 1 if x.get("verdict") == "CLOSE" else 2, -(x.get("soseo", 0)))):
        if "status" in r:
            print(f"{r['slug']:<50} | {r.get('kw',''):<30} | {r['status']}")
            fail += 1
            continue
        s, d = r["soseo"], r["dseo"]
        tmin, dmax = r["target_min"], r["dseo_max"]
        tag = "C" if r["is_corrected"] else "R"
        v = r["verdict"]
        if v == "OK":
            ok += 1
        elif v == "CLOSE":
            close += 1
        else:
            miss += 1
        print(f"{r['slug']:<50} | {r['kw'][:30]:<30} | {s:>6.0f} | {d:>5.0f} | S>={tmin:.0f} D<={dmax:.0f} | {tag:>3} | {v}")

    an_count = len([r for r in results if "status" not in r])
    if an_count:
        avg_s = sum(r["soseo"] for r in results if "status" not in r) / an_count
        avg_d = sum(r["dseo"] for r in results if "status" not in r) / an_count
        print(f"\nTotal: {len(results)} | Analysed: {an_count} | OK: {ok} | CLOSE: {close} | MISS: {miss} | FAIL: {fail}")
        print(f"Avg SOSEO: {avg_s:.1f}% | Avg DSEO: {avg_d:.1f}%")


if __name__ == "__main__":
    main()
