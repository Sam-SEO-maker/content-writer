"""Corrections QC déterministes pour les articles Superprof Ressources.

Applique sur les fichiers `*_refreshed.gutenberg.html` les fixes sûrs et
automatisables (voir mémoire feedback-sp-ressources-qc-checklist) :
  1. H3 isolé dans un H2  -> démoté en <p><strong>…</strong></p>
  2. Titre/question interrogatif sans " ?"  -> ajout de " ?" (avant emoji final)
  3. Question de FAQ (H3) sans emoji de tête  -> ajout d'un emoji (palette rotative)

NE corrige PAS (éditorial, à faire à la main / à la génération) : count-up non
numérique, chronologie -> timeline, blocs obligatoires manquants.

Usage:
    python -m scripts.utils.sp_qc_fix [fichier_urls.txt]      # applique
    python -m scripts.utils.sp_qc_fix [fichier_urls.txt] --dry # simulation
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from _shared.core.tenant_paths import TenantPaths
HTML = TenantPaths().output_dir("superprof-ressources") / "html"
EMO = "\U0001F000-\U0001FAFF←-⇿⌀-➿⬀-⯿☀-⛿️⃣‍"
LEAD_EMOJI = re.compile(r"^\s*[" + EMO + r"]")
QSTART = re.compile(r"^(comment|pourquoi|qu'est-ce|qui |quel|quelle|quels|quelles|combien|où|en quoi|à quoi|est-ce|faut-il|peut-on)", re.I)
FAQ_H2 = re.compile(r"questions fr[ée]quentes|foire aux questions|\bFAQ\b|questions sur", re.I)
PAL = ["🤔", "💡", "🔍", "📌", "🧐", "📖", "❓", "💬"]


def url_to_gutenberg(url: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_")
    return HTML / f"{slug}_refreshed.gutenberg.html"


def fix_lone_h3(t: str) -> tuple[str, int]:
    hb = re.compile(r"<!-- wp:heading(?: \{[^}]*\})? -->\s*<h([1-3])[^>]*>(.*?)</h\1>\s*<!-- /wp:heading -->", re.S)
    blocks = list(hb.finditer(t))
    secs = []; cur = None
    for b in blocks:
        lvl = int(b.group(1))
        if lvl == 2:
            cur = []; secs.append(cur)
        elif lvl == 3 and cur is not None:
            cur.append(b)
    lone = [s[0] for s in secs if len(s) == 1]
    for b in sorted(lone, key=lambda x: -x.start()):
        txt = b.group(2).strip()
        new = f"<!-- wp:paragraph -->\n<p><strong>{txt}</strong></p>\n<!-- /wp:paragraph -->"
        t = t[:b.start()] + new + t[b.end():]
    return t, len(lone)


def fix_questions(t: str) -> tuple[str, int]:
    def add_q(txt):
        core = re.sub(r"[\s" + EMO + r"]+$", "", txt)
        trail = txt[len(core):].strip()
        return core + " ?" + ((" " + trail) if trail else "")
    n = 0
    for pat in (r"(<h2\b[^>]*>)(.*?)(</h2>)", r"(<h3\b[^>]*>)(.*?)(</h3>)", r"(<p><strong>)(.*?)(</strong></p>)"):
        edits = []
        for mm in re.finditer(pat, t, re.S):
            inner = mm.group(2)
            if "<" in inner:
                continue
            txt = inner.strip()
            if "?" in txt:
                continue
            core = re.sub(r"^[\s" + EMO + r"]+", "", txt)
            if " : " in core or not QSTART.match(core):
                continue
            edits.append((mm.start(), mm.end(), mm.group(1) + add_q(txt) + mm.group(3)))
        for s, e, new in sorted(edits, key=lambda x: -x[0]):
            t = t[:s] + new + t[e:]; n += 1
    return t, n


def fix_faq_emoji(t: str) -> tuple[str, int]:
    h2s = [(m.start(), re.sub(r"<[^>]+>", "", m.group(1))) for m in re.finditer(r"<h2\b[^>]*>(.*?)</h2>", t, re.S)]
    edits = []; counter = 0
    for i, (pos, txt) in enumerate(h2s):
        if not FAQ_H2.search(txt):
            continue
        end = h2s[i + 1][0] if i + 1 < len(h2s) else len(t)
        for hm in re.finditer(r"(<h3\b[^>]*>)(.*?)(</h3>)", t[pos:end], re.S):
            inner = hm.group(2)
            if LEAD_EMOJI.match(re.sub(r"<[^>]+>", "", inner).strip()):
                continue
            emo = PAL[counter % len(PAL)]; counter += 1
            edits.append((pos + hm.start(), pos + hm.end(), hm.group(1) + emo + " " + inner.lstrip() + hm.group(3)))
    for s, e, new in sorted(edits, key=lambda x: -x[0]):
        t = t[:s] + new + t[e:]
    return t, len(edits)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    if args:
        targets = [url_to_gutenberg(l.strip()) for l in Path(args[0]).read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        targets = sorted(HTML.glob("*_refreshed.gutenberg.html"))
    tot = {"h3": 0, "q": 0, "faq": 0}
    touched = 0
    for p in targets:
        if not p.exists():
            print(f"  ✗ ABSENT {p.name}"); continue
        t = p.read_text(encoding="utf-8"); orig = t
        t, a = fix_lone_h3(t); t, b = fix_questions(t); t, c = fix_faq_emoji(t)
        if t != orig:
            touched += 1; tot["h3"] += a; tot["q"] += b; tot["faq"] += c
            if not dry:
                p.write_text(t, encoding="utf-8")
            print(f"  {'(dry) ' if dry else ''}{p.name[:55]}  h3-demote={a} ?+={b} faq-emoji={c}")
    print(f"\n{touched} fichiers {'à modifier' if dry else 'modifiés'} | "
          f"H3 démotés={tot['h3']} ?ajoutés={tot['q']} emojis FAQ={tot['faq']}")
    print("(NB: count-up non-num, chronologie→timeline, blocs manquants = à traiter à la main)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
