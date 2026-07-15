"""QC checker pour les articles Superprof Ressources (format Gutenberg maison).

Lecture seule. Scanne les fichiers `*_refreshed.gutenberg.html` et signale les
defauts recurrents (voir mémoire feedback-sp-ressources-qc-checklist) :
  - blocs obligatoires manquants (2 infobox, count-up, citation, bloc sources)
  - count-up non numerique (countUpNumber ne commence pas par un chiffre)
  - H3 isole dans une section H2
  - titre/question interrogatif sans " ?"
  - question de FAQ (H3) sans emoji de tete
  - tiret cadratin —, H1 multiple/absent
  - tableau <table> sans CSV correspondant dans csv/

Usage:
    python -m scripts.utils.sp_qc_check [fichier_urls.txt]
    (sans argument : scanne tous les *_refreshed.gutenberg.html du dossier html/)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from _shared.core.tenant_paths import TenantPaths
OUT = TenantPaths().output_dir("superprof-ressources")
HTML = OUT / "html"
CSVDIR = OUT / "csv"

EMO = "\U0001F000-\U0001FAFF←-⇿⌀-➿⬀-⯿☀-⛿️⃣‍"
LEAD_EMOJI = re.compile(r"^\s*[" + EMO + r"]")
QSTART = re.compile(r"^(comment|pourquoi|qu'est-ce|qui |quel|quelle|quels|quelles|combien|où|en quoi|à quoi|est-ce)", re.I)
FAQ_H2 = re.compile(r"questions fr[ée]quentes|foire aux questions|\bFAQ\b|questions sur", re.I)


def url_to_gutenberg(url: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_")
    return HTML / f"{slug}_refreshed.gutenberg.html"


def hyphen_slug(url: str) -> str:
    return url.rstrip("/").split("/")[-1].replace(".html", "")


def headings(t: str):
    return [(int(m.group(1)), re.sub(r"<[^>]+>", "", m.group(2)).strip())
            for m in re.finditer(r"<h([1-3])\b[^>]*>(.*?)</h\1>", t, re.S)]


def check_file(path: Path, url: str | None) -> list[str]:
    t = path.read_text(encoding="utf-8")
    issues = []
    # mandatory blocks
    if len(re.findall(r"<!-- wp:advgb/infobox ", t)) < 2:
        issues.append("infobox<2")
    if "<!-- wp:advgb/count-up " not in t:
        issues.append("count-up manquant")
    if "<!-- wp:superprof/quote-block" not in t:
        issues.append("citation manquante")
    if "wp-block-wp-sp-gutenberg-blocks-block-sources" not in t:
        issues.append("bloc sources manquant")
    if t.count('{"level":1}') != 1:
        issues.append(f"H1 x{t.count(chr(34)+'level'+chr(34)+':1')}")
    if "—" in t:
        issues.append("tiret cadratin")
    # count-up numeric
    for b in re.finditer(r'"countUpNumber":"((?:[^"\\]|\\.)*)"', t):
        num = re.sub(r"<[^>]+>", "", b.group(1)).strip()
        if not re.match(r"\s*\d", num):
            issues.append(f"count-up non-num {num[:18]!r}")
    # lone H3
    secs = []
    cur = None
    for lvl, _ in headings(t):
        if lvl == 2:
            cur = []; secs.append(cur)
        elif lvl == 3 and cur is not None:
            cur.append(1)
    if any(len(s) == 1 for s in secs):
        issues.append("H3 isolé")
    # interrogatives without ?
    for lvl, txt in headings(t):
        if "?" in txt:
            continue
        core = re.sub(r"^[\s" + EMO + r"]+", "", txt)
        if " : " in core:
            continue
        if QSTART.match(core):
            issues.append(f"question sans ? {core[:30]!r}")
    # FAQ h3 without leading emoji
    h2pos = [(m.start(), re.sub(r"<[^>]+>", "", m.group(1))) for m in re.finditer(r"<h2\b[^>]*>(.*?)</h2>", t, re.S)]
    for i, (pos, txt) in enumerate(h2pos):
        if not FAQ_H2.search(txt):
            continue
        end = h2pos[i + 1][0] if i + 1 < len(h2pos) else len(t)
        for hm in re.finditer(r"<h3\b[^>]*>(.*?)</h3>", t[pos:end], re.S):
            plain = re.sub(r"<[^>]+>", "", hm.group(1)).strip()
            if not LEAD_EMOJI.match(plain):
                issues.append("FAQ sans emoji")
                break
    # tables without CSV
    ntab = len(re.findall(r"<table", t))
    if ntab and url:
        art = hyphen_slug(url)
        ncsv = len(list(CSVDIR.glob(f"{art}_tableau_*.csv")))
        if ncsv < ntab:
            issues.append(f"tableaux={ntab} mais CSV={ncsv}")
    return issues


def main() -> int:
    if len(sys.argv) > 1:
        urls = [l.strip() for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
        targets = [(url_to_gutenberg(u), u) for u in urls]
    else:
        targets = [(p, None) for p in sorted(HTML.glob("*_refreshed.gutenberg.html"))]

    clean = 0
    for path, url in targets:
        if not path.exists():
            print(f"  ✗ ABSENT {path.name}")
            continue
        issues = check_file(path, url)
        if issues:
            print(f"  ⚠ {path.name[:60]}")
            for i in issues:
                print(f"       - {i}")
        else:
            clean += 1
    print(f"\n{clean}/{len(targets)} articles sans défaut détecté")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
