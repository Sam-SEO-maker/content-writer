"""Détecte les articles traitant d'une œuvre littéraire et génère les champs ACF.

Périmètre : articles SP Ressources uniquement.
Œuvres ciblées : romans, nouvelles, pièces de théâtre, recueils, albums jeunesse.
Exclus : "nouvelle" générique ("bonne nouvelle", "une nouvelle façon"), genres abstraits
sans œuvre unique, œuvres non littéraires (chansons, discours), biographies multi-œuvres.

Stratégie de détection (AND) :
  1. Signal fort de fiche/analyse littéraire dans le H1 ou le texte d'intro (<800 car.)
  2. Présence d'un auteur littéraire nommé (prénom + nom reconnu, ou Maupassant/Zola/etc.)
  3. OU présence explicite d'un titre entre guillemets associé à un auteur

Sortie : _shared/outputs/superprof-ressources/acf/{slug}_acf.json
Champs : book_name, author_name, genre, date_published (AAAA ou "")
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

# Signal fort : expressions qui désignent explicitement un travail sur une œuvre
_STRONG_SIGNALS = re.compile(
    r'\b(fiche de lecture|analyse litt[eé]raire|commentaire litt[eé]raire'
    r'|commentaire compos[eé]|r[eé]sum[eé] de l[\'’]œuvre'
    r'|explication de texte|étude de l[\'’]œuvre'
    r'|les personnages de|l[\'’]intrigue de'
    r'|publié(?:e)? en \d{4}|parution en \d{4})\b',
    re.IGNORECASE,
)

# Auteurs littéraires connus fréquemment étudiés au lycée/collège
_KNOWN_AUTHORS = re.compile(
    r'\b(Maupassant|Guy de Maupassant|Zola|Flaubert|Balzac|Hugo|Stendhal|Molière'
    r'|Racine|Corneille|Baudelaire|Verlaine|Rimbaud|Voltaire|Rousseau|Camus|Sartre'
    r'|Proust|Dumas|Verne|Sand|Colette|Prévert|Apollinaire|Musset|Vigny|Mérimée'
    r'|Laclos|Diderot|Montesquieu|La Fontaine|Rabelais|Montaigne|Marivaux'
    r'|Giraudoux|Anouilh|Ionesco|Beckett|Brisou-Pellen|Pennac|Modiano)\b',
    re.IGNORECASE,
)

# Titre entre guillemets (français ou anglais) dans un contexte littéraire
_TITLE_IN_QUOTES = re.compile(
    r'[«""“«]([^»""”»]{3,80})[»""”»]'
)

_YEAR_RE = re.compile(r'\b(1[0-9]{3}|20[0-2][0-9])\b')

_GENRE_MAP = [
    (re.compile(r'\bnouvelle(?:\s+réaliste|\s+fantastique|\s+de\b|\s+de\s+Maupassant|\s+[«""])|\bune nouvelle\s+de\b', re.I), 'Nouvelle'),
    (re.compile(r'\bnouvelle réaliste\b|\broman réaliste\b|\bnouveau roman\b', re.I), 'Roman réaliste'),
    (re.compile(r'\broman\b', re.I), 'Roman'),
    (re.compile(r'\balb?um jeunesse\b', re.I), 'Album jeunesse'),
    (re.compile(r'\brecueil\b', re.I), 'Recueil'),
    (re.compile(r'\bpo[eè]me\b|\bpo[eé]sie\b', re.I), 'Poème'),
    (re.compile(r'\bpi[eè]ce\b|\bth[eé][aâ]tre\b|\btrag[eé]die\b|\bcom[eé]die\b', re.I), 'Pièce de théâtre'),
    (re.compile(r'\bessai\b', re.I), 'Essai'),
]


def _clean(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip()


def is_literary_article(html: str) -> bool:
    """
    Retourne True si le HTML traite d'une œuvre littéraire précise.
    Exige : signal fort de fiche/analyse ET auteur nommé (ou les deux dans le H1).
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Signal dans le H1/titre principal
    h1 = soup.find('h1')
    h1_text = h1.get_text(' ', strip=True) if h1 else ''

    # Intro = texte des 2 premiers paragraphes (pas tout l'article)
    intro_parts = []
    for tag in soup.find_all(['h1', 'h2', 'p'], limit=6):
        intro_parts.append(tag.get_text(' ', strip=True))
    intro = ' '.join(intro_parts)

    has_strong_signal = bool(_STRONG_SIGNALS.search(h1_text) or _STRONG_SIGNALS.search(intro))
    has_known_author = bool(_KNOWN_AUTHORS.search(h1_text) or _KNOWN_AUTHORS.search(intro))

    return has_strong_signal or has_known_author


def extract_acf_fields(html: str, slug: str = '') -> dict | None:
    """
    Tente d'extraire les 4 champs ACF depuis le HTML.

    Retourne None si l'article ne traite pas d'une œuvre précise.
    Retourne un dict avec les 4 clés (certaines peuvent être "") sinon.
    """
    if not is_literary_article(html):
        return None

    soup = BeautifulSoup(html, 'html.parser')
    full_text = soup.get_text(' ', strip=True)

    # Intro étendue pour l'extraction des métadonnées
    intro_parts = []
    for tag in soup.find_all(['h1', 'h2', 'h3', 'p'], limit=12):
        intro_parts.append(tag.get_text(' ', strip=True))
    intro = ' '.join(intro_parts)

    # --- Titre de l'œuvre ---
    book_name = ''
    h1 = soup.find('h1')
    h1_text = h1.get_text(' ', strip=True) if h1 else ''

    # 1. Titre entre guillemets dans H1 ou intro
    search_zone = h1_text + ' ' + intro[:1500]
    for m in _TITLE_IN_QUOTES.finditer(search_zone):
        candidate = _clean(m.group(1))
        if len(candidate) >= 3 and candidate.count(' ') <= 8:
            book_name = candidate
            break

    # 2. Si pas de guillemets : extraire le titre depuis le H1 avant un mot-clé séparateur
    if not book_name and h1_text:
        # "Pierre et Jean résumé" → "Pierre et Jean"
        # "Au hasard d'une rencontre 1ère année" → "Au hasard d'une rencontre"
        separators = re.compile(
            r'\s*[\|:–-]\s*|\s+(?:résumé|analyse|fiche|étude|explication|commentaire|critique|personnages|extrait)\b',
            re.IGNORECASE,
        )
        h1_clean = separators.split(h1_text)[0].strip()
        # Supprimer le nom de l'auteur s'il est en fin de titre
        if _KNOWN_AUTHORS.search(h1_clean):
            h1_clean = _KNOWN_AUTHORS.sub('', h1_clean).strip(' ,')
        if 3 <= len(h1_clean) <= 80 and h1_clean.count(' ') <= 7:
            book_name = h1_clean

    # --- Auteur ---
    author_name = ''
    m = _KNOWN_AUTHORS.search(intro)
    if m:
        # Tenter de capturer "Prénom de NomConnu" ou "Prénom NomConnu"
        full_name_re = re.compile(
            r'([A-ZÁÀÂÄÉÈÊËÎÏÔÙÛÜÇ][a-záàâäéèêëîïôùûüç\-]+\s+(?:de\s+)?)'
            + re.escape(m.group(0)),
            re.IGNORECASE,
        )
        fm = full_name_re.search(intro[:2000])
        raw = _clean(fm.group(0) if fm else m.group(0))
        # Nettoyer les mots parasites communs
        raw = re.sub(r'\b(roman|nouvelle|récit|œuvre|texte|auteur|écrivain)\s+de\s+', '', raw, flags=re.I)
        author_name = raw.strip()

    # --- Genre (chercher d'abord dans intro, pas le texte entier pour éviter les faux positifs) ---
    genre = ''
    for pat, label in _GENRE_MAP:
        if pat.search(intro[:800]):
            genre = label
            break
    if not genre:
        for pat, label in _GENRE_MAP:
            if pat.search(full_text[:2000]):
                genre = label
                break

    # --- Date de première publication (la plus ancienne >= 1000) ---
    years = [int(y) for y in _YEAR_RE.findall(full_text) if 1000 <= int(y) <= 2024]
    # Filtrer les années trop récentes (>= 2010) sauf si c'est la seule trouvée
    lit_years = [y for y in years if y < 2010]
    date_published = str(min(lit_years)) if lit_years else (str(min(years)) if years else '')

    return {
        'book_name': book_name,
        'author_name': author_name,
        'genre': genre,
        'date_published': date_published,
    }


def save_acf_if_literary(
    site_id: str,
    file_slug: str,
    html_content: str,
    tenant_output_dir: Path,
) -> Path | None:
    """
    Détecte si l'article traite d'une œuvre littéraire.
    Si oui, écrit le JSON ACF et retourne son chemin. Sinon retourne None.

    Actif uniquement pour superprof-ressources.
    Ne remplace pas un fichier ACF existant (pour ne pas écraser les corrections manuelles).

    Args:
        tenant_output_dir: dossier de sortie du tenant (tenants/{id}/outputs/).
    """
    if site_id != 'superprof-ressources':
        return None

    acf_dir = tenant_output_dir / 'acf'
    out = acf_dir / f'{file_slug}_acf.json'
    if out.exists():
        return None  # déjà créé (manuellement ou lors d'un run précédent)

    fields = extract_acf_fields(html_content, slug=file_slug)
    if fields is None:
        return None

    acf_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fields, indent=2, ensure_ascii=False), encoding='utf-8')
    return out
