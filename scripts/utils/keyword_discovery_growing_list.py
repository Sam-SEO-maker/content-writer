"""
Keyword Discovery — onglet "New growing List" (SP Ressources)

Pour chaque ligne de l'onglet où col B (main_keyword) est vide :
1. Appelle la GSC sur 12 mois pour l'URL (col A)
2. Sélectionne le mot-clé avec le plus de clicks (sinon le plus d'impressions)
3. Écrit le résultat en col B

Lancer depuis la racine du projet :
    python scripts/utils/keyword_discovery_growing_list.py
"""

import os
import re
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from google.oauth2 import service_account
from googleapiclient.discovery import build

from scripts.audit.gsc_analyzer import GSCAnalyzer

try:
    import anthropic as _anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# spreadsheet_id / onglet lus depuis la config du tenant (§4bis-A), repli littéral.
from _shared.core.sheets_config import get_spreadsheet_id, get_primary_tab_name
_BLOG_ID = "superprof-ressources"
SPREADSHEET_ID = get_spreadsheet_id(_BLOG_ID, default="1Vutb06Fcm3awnANPbtLkI1EvhbE9d-TXrZRLTrmmLlQ")
SHEET_NAME = get_primary_tab_name(_BLOG_ID, default="New growing List")
GSC_PROPERTY = "https://www.superprof.fr/ressources/"

SA_PATH = Path(
    os.environ.get("GOOGLE_SA_PATH", "~/.credentials/google/google-service-account.json")
).expanduser()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/webmasters.readonly",
]

# Rate limiting : pause entre chaque appel GSC
SLEEP_BETWEEN_CALLS = 1.0

# Première ligne à traiter (les lignes précédentes sont ignorées)
FIRST_ROW = 34


# ---------------------------------------------------------------------------
# Sheet helpers
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    "le", "la", "les", "de", "du", "des", "en", "et", "ou", "un", "une",
    "au", "aux", "ce", "se", "sa", "son", "ses", "sur", "par", "pour",
    "que", "qui", "est", "il", "elle", "ils", "elles", "on", "je", "tu",
    "nous", "vous", "dans", "avec", "sans", "sous", "leur", "leurs",
}


def _normalize_keyword(kw: str) -> set[str]:
    """Normalise un mot-clé en ensemble de mots significatifs (sans stop words ni accents)."""
    kw = unicodedata.normalize("NFD", kw.lower())
    kw = "".join(c for c in kw if unicodedata.category(c) != "Mn")
    words = re.findall(r"[a-z]+", kw)
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def _is_near_duplicate(kw: str, reference: str, threshold: float = 0.7) -> bool:
    """Retourne True si kw est une variante trop proche de reference."""
    kw_words = _normalize_keyword(kw)
    ref_words = _normalize_keyword(reference)
    if not kw_words or not ref_words:
        return kw.lower().strip() == reference.lower().strip()
    overlap = len(kw_words & ref_words) / min(len(kw_words), len(ref_words))
    return overlap >= threshold


def _slug_words(url: str) -> str:
    """Extrait les mots significatifs du slug d'URL (dernière partie du path)."""
    path = url.rstrip("/").split("/")[-1]
    path = re.sub(r"\.[a-z]+$", "", path)
    words = [w for w in path.replace("-", " ").split() if len(w) > 2]
    return " ".join(words)


def select_secondary_keyword(
    url: str,
    main_keyword: str,
    candidates: list[dict],
) -> "str | None":
    """
    Sélectionne le meilleur mot-clé secondaire parmi les candidats GSC.

    Si ≥ 2 candidats non-dupliqués, appelle Claude Haiku pour choisir
    celui qui correspond le mieux au sujet de l'article.
    Fallback : premier candidat de la liste triée.
    """
    filtered = [c for c in candidates if not _is_near_duplicate(c["query"], main_keyword)]
    if not filtered:
        return None
    if len(filtered) == 1:
        return filtered[0]["query"]

    if not _ANTHROPIC_AVAILABLE:
        return filtered[0]["query"]

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return filtered[0]["query"]

    slug = _slug_words(url)
    numbered = "\n".join(f"{i + 1}. {c['query']}" for i, c in enumerate(filtered[:15]))
    prompt = (
        f"Tu sélectionnes le meilleur mot-clé secondaire pour un article.\n\n"
        f"URL de l'article : {url}\n"
        f"Mots du slug : {slug}\n"
        f"Mot-clé principal : {main_keyword}\n\n"
        f"Requêtes GSC disponibles (triées par performance) :\n{numbered}\n\n"
        f"Le mot-clé secondaire servira de H1 (différent du title généré depuis le mot-clé principal). "
        f"Choisis celui qui :\n"
        f"- correspond le mieux au sujet réel de l'article (déduit du slug)\n"
        f"- n'est pas une reformulation du mot-clé principal\n"
        f"- représente un angle de recherche complémentaire\n\n"
        f"Réponds uniquement avec le mot-clé exact tel qu'il apparaît dans la liste, rien d'autre."
    )

    try:
        client = _anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = message.content[0].text.strip().strip('"').strip("'")
        # Valider que la réponse est bien dans la liste
        answer_lower = answer.lower()
        for c in filtered[:15]:
            if c["query"].lower() == answer_lower:
                return c["query"]
        # Si pas de correspondance exacte, fallback sur le premier
        return filtered[0]["query"]
    except Exception as e:
        print(f"  [WARN] Claude API indisponible ({e}) — fallback sur candidat #1")
        return filtered[0]["query"]


def read_rows(sheets) -> list[tuple[int, str, str, str]]:
    """
    Lit l'onglet à partir de FIRST_ROW et retourne les lignes avec URL en col A.

    Returns:
        Liste de (row_index_1based, url, main_keyword, secondary_keyword)
    """
    result = sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SHEET_NAME}'!A{FIRST_ROW}:C",
    ).execute()

    rows = result.get("values", [])
    out = []
    for i, row in enumerate(rows, start=FIRST_ROW):
        url = row[0].strip() if row else ""
        if not url.startswith("http"):
            continue
        main_kw = row[1].strip() if len(row) > 1 else ""
        sec_kw = row[2].strip() if len(row) > 2 else ""
        out.append((i, url, main_kw, sec_kw))
    return out


def write_keyword(sheets, row_index: int, keyword: str) -> None:
    """Écrit le mot-clé principal découvert en colonne B."""
    sheets.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SHEET_NAME}'!B{row_index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[keyword]]},
    ).execute()


def write_secondary_keyword(sheets, row_index: int, keyword: str) -> None:
    """Écrit le mot-clé secondaire en colonne C."""
    sheets.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SHEET_NAME}'!C{row_index}",
        valueInputOption="USER_ENTERED",
        body={"values": [[keyword]]},
    ).execute()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not SA_PATH.exists():
        print(f"[ERREUR] Service account introuvable : {SA_PATH}")
        sys.exit(1)

    creds = service_account.Credentials.from_service_account_file(str(SA_PATH), scopes=SCOPES)
    sheets = build("sheets", "v4", credentials=creds)
    gsc_analyzer = GSCAnalyzer(gsc_property=GSC_PROPERTY)

    rows = read_rows(sheets)
    to_process_primary = [(idx, url) for idx, url, main_kw, _ in rows if not main_kw]

    print(f"[INFO] {len(rows)} URLs dans la feuille")
    print(f"[INFO] Phase 1 — {len(to_process_primary)} URLs sans mot-clé principal (col B)")

    filled = 0
    no_data = 0
    errors = []

    # --- Phase 1 : Remplir col B (mot-clé principal) ---
    for i, (row_index, url) in enumerate(to_process_primary):
        try:
            keyword = gsc_analyzer.fetch_top_keyword_12m(url)
            if keyword:
                write_keyword(sheets, row_index, keyword)
                print(f"[OK] Ligne {row_index} → '{keyword}'  ({url[:70]})")
                filled += 1
            else:
                print(f"[SKIP] Ligne {row_index} — aucune donnée GSC  ({url[:70]})")
                no_data += 1
        except Exception as e:
            msg = f"Ligne {row_index} — {url[:60]}: {e}"
            print(f"[ERREUR] {msg}")
            errors.append(msg)

        if i < len(to_process_primary) - 1:
            time.sleep(SLEEP_BETWEEN_CALLS)

    print(f"\n--- Résumé Phase 1 ---")
    print(f"  Remplis    : {filled}")
    print(f"  Sans données GSC : {no_data}")
    print(f"  Erreurs    : {len(errors)}")
    if errors:
        for e in errors:
            print(f"    ✗ {e}")

    # Relire la feuille pour avoir les col B fraîchement remplies
    rows = read_rows(sheets)
    to_process_secondary = [
        (idx, url, main_kw)
        for idx, url, main_kw, sec_kw in rows
        if main_kw and not sec_kw
    ]

    print(f"\n[INFO] Phase 2 — {len(to_process_secondary)} URLs sans mot-clé secondaire (col C)")

    filled_sec = 0
    no_data_sec = 0
    errors_sec = []

    # --- Phase 2 : Remplir col C (mot-clé secondaire) ---
    for i, (row_index, url, main_kw) in enumerate(to_process_secondary):
        try:
            candidates = gsc_analyzer.fetch_top_keywords_12m(url, limit=20)
            # Exclure le mot-clé principal
            candidates = [c for c in candidates if c["query"].lower() != main_kw.lower()]

            secondary = select_secondary_keyword(url, main_kw, candidates)
            if secondary:
                write_secondary_keyword(sheets, row_index, secondary)
                print(f"[SEC] Ligne {row_index} → '{secondary}'  ({url[:70]})")
                filled_sec += 1
            else:
                print(f"[SKIP-SEC] Ligne {row_index} — aucun candidat secondaire  ({url[:70]})")
                no_data_sec += 1
        except Exception as e:
            msg = f"Ligne {row_index} — {url[:60]}: {e}"
            print(f"[ERREUR-SEC] {msg}")
            errors_sec.append(msg)

        if i < len(to_process_secondary) - 1:
            time.sleep(SLEEP_BETWEEN_CALLS)

    print(f"\n--- Résumé Phase 2 ---")
    print(f"  Remplis    : {filled_sec}")
    print(f"  Sans candidat : {no_data_sec}")
    print(f"  Erreurs    : {len(errors_sec)}")
    if errors_sec:
        for e in errors_sec:
            print(f"    ✗ {e}")


if __name__ == "__main__":
    main()
