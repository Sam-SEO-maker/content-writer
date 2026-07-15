"""Génère les CSV de tableaux (+ zip par article) pour Superprof Ressources.

Pour chaque article, extrait les <table> du fichier `{slug}.gutenberg.html`
et écrit un CSV par tableau, nommé `{slug-à-tirets}_tableau_{descriptif-sujet}.csv`
(descripteur = sujet déduit du heading le plus proche, PAS les en-têtes — voir
mémoire feedback-csv-naming-tablepress). Puis zippe par article dans csv_zips/.

Usage:
    python -m scripts.utils.generate_table_csv [fichier_urls.txt]
    (sans argument : tous les {slug}.gutenberg.html du dossier html/)
"""
from __future__ import annotations

import csv
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.utils.table_csv_extractor import _parse_table
from scripts.utils.output_manager import dated_batch_folder_name

from _shared.core.tenant_paths import TenantPaths
OUT = TenantPaths().output_dir("superprof-ressources")
HTML = OUT / "html"
CSVDIR = OUT / "csv"
ZIPDIR = OUT / "csv_zips"
EMO = re.compile("[\U0001F000-\U0001FAFF←-➿⬀-⯿☀-⛿️⃣‍]")
STOP = re.compile(r"\b(les?|la|des?|du|un|une|au|aux|et|d|l|en|pour|sur|ce|cette)\b", re.I)


def subj_slug(s: str) -> str:
    s = EMO.sub("", s)
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")
    s = STOP.sub(" ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return "-".join(s.split("-")[:5])[:60] or "tableau"


def hyphen_slug(url: str) -> str:
    return url.rstrip("/").split("/")[-1].replace(".html", "")


def gutenberg_for(url: str) -> Path:
    return HTML / f"{hyphen_slug(url)}.gutenberg.html"


def gen_for(art: str, html: str, batch_folder: str | None = None) -> list[Path]:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []
    batch_folder = batch_folder or dated_batch_folder_name()
    csv_dir = CSVDIR / batch_folder
    zip_dir = ZIPDIR / batch_folder
    # remove stale CSV/zip for this article first
    for p in csv_dir.glob(f"{art}_tableau_*.csv"):
        p.unlink()
    (zip_dir / f"{art}_tableaux.zip").unlink(missing_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)
    zip_dir.mkdir(parents=True, exist_ok=True)
    seen: dict[str, int] = {}
    made = []
    for table in tables:
        rows = _parse_table(table)
        if not rows:
            continue
        head = ""
        for prev in table.find_all_previous(["h3", "h2"]):
            head = prev.get_text(strip=True)
            break
        desc = subj_slug(head)
        if desc in seen:
            seen[desc] += 1
            desc = f"{desc}-{seen[desc]}"
        else:
            seen[desc] = 1
        path = csv_dir / f"{art}_tableau_{desc}.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as fh:
            csv.writer(fh, quoting=csv.QUOTE_ALL).writerows(rows)
        made.append(path)
    if made:
        with zipfile.ZipFile(zip_dir / f"{art}_tableaux.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for p in made:
                z.write(p, p.name)
    return made


def main() -> int:
    batch_folder = dated_batch_folder_name()
    if len(sys.argv) > 1:
        urls = [l.strip() for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
        # Cherche le .gutenberg.html dans le sous-dossier daté du jour, sinon
        # scan récursif (au cas où il a été généré un autre jour).
        targets = []
        for u in urls:
            slug = hyphen_slug(u)
            dated_path = HTML / batch_folder / f"{slug}.gutenberg.html"
            if dated_path.exists():
                targets.append((slug, dated_path))
            else:
                matches = list(HTML.rglob(f"{slug}.gutenberg.html"))
                targets.append((slug, matches[0] if matches else dated_path))
    else:
        targets = [(p.name[: -len(".gutenberg.html")], p)
                   for p in sorted(HTML.rglob("*.gutenberg.html"))]
    total = 0
    for art, path in targets:
        if not path.exists():
            print(f"  ✗ ABSENT {path.name}")
            continue
        made = gen_for(art, path.read_text(encoding="utf-8"), batch_folder=batch_folder)
        if made:
            total += len(made)
            flag = "  ⚠ >3 (ok si lexique/grammaire)" if len(made) > 3 else ""
            print(f"  {art}: {len(made)} CSV{flag}")
    print(f"\nTotal CSV générés: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
