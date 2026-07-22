"""
Validation déterministe d'un plan éditorial (content_plan.md).

Vérifie *mécaniquement* les invariants de structure produits par la skill
`seo-outline` (étape 2bis de /refresh) :
  - hiérarchie des titres : >= 3 H2, pas de H2/H3 orphelin, 2-4 H3 par H2,
    `?` sur les titres interrogatifs,
  - couverture : chaque PAA collectée apparait dans le plan,
  - preuves : >= 3 sources (liens http) et >= 2 statistiques (chiffrées) placées.

100% déterministe : aucun appel LLM/API. La *rédaction* du plan reste au subagent
Max (skill seo-outline) ; ce module ne fait que le noter, comme `ytg qc` note un
HTML déjà rédigé. Réutilisable hors CLI (import direct, tests).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List


def _strip_comments(markdown: str) -> str:
    """
    Retire les commentaires HTML (<!-- ... -->) avant analyse.

    Le scaffold `plan init` injecte les signaux (PAA, sources, invariants) dans des
    commentaires : ils ne doivent PAS compter comme du contenu rédigé, sinon un plan
    vide validerait la couverture PAA. Seul le texte hors commentaire est analysé.
    """
    return re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)


def _strip_accents(s: str) -> str:
    """Normalise pour comparaison insensible aux accents (é→e, œ→oe partiel)."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Mots interrogatifs FR déclenchant l'attente d'un `?` en fin de titre.
_INTERROGATIVE_STARTS = (
    "comment", "pourquoi", "quel", "quelle", "quels", "quelles", "quand",
    "où", "ou", "qui", "quoi", "combien", "est-ce", "est ce", "faut-il",
    "peut-on", "que", "qu'est",
)


@dataclass
class PlanViolation:
    """Un manquement précis, rattaché à un titre quand c'est pertinent."""
    rule: str          # slug court, ex. "h3_orphan"
    message: str       # phrase actionnable
    heading: str = ""  # titre concerné (vide si global)


@dataclass
class Heading:
    level: int         # 2 ou 3
    text: str
    body_words: int = 0
    children: list = field(default_factory=list)  # H3 sous un H2


@dataclass
class PlanReport:
    verdict: str                       # "OK" | "NEEDS_FIX"
    violations: List[PlanViolation]
    h2_count: int
    paa_total: int
    paa_covered: int
    source_links: int
    stats_found: int

    @property
    def ok(self) -> bool:
        return self.verdict == "OK"


# --------------------------------------------------------------------------- #
# Parsing du markdown de plan                                                  #
# --------------------------------------------------------------------------- #

def _parse_headings(markdown: str) -> tuple[List[Heading], List["PlanViolation"]]:
    """
    Extrait l'arbre H2>H3 d'un content_plan.md.

    Un H2/H3 est une ligne `## ` / `### `. Le "corps" d'un titre = les mots des
    lignes non-titres qui le suivent jusqu'au prochain titre (approxime le volume
    rédactionnel prévu pour appliquer le seuil des 150 mots).
    """
    h2s: List[Heading] = []
    empty: List[PlanViolation] = []
    current_h2: Heading | None = None
    current_h3: Heading | None = None

    # Syntaxe ATX stricte (comme le rendu markdown→HTML de WordPress) :
    #   - `##`/`###` en début de ligne, puis SOIT un espace + texte, SOIT rien.
    #     `##Titre` collé (sans espace) = texte littéral, PAS un heading (ignoré).
    #   - `#` de fermeture optionnels retirés (`## Titre ##` → « Titre »).
    #   - `##` seul ou `## ` sans texte = heading vide → red flag Gutenberg, signalé.
    def _heading_level(line: str) -> int | None:
        """2 ou 3 si `line` est un heading ATX H2/H3 valide, sinon None."""
        m = re.match(r"^(#{2,3})(?:\s+.*)?$", line)
        if not m:
            return None
        return len(m.group(1))

    def _heading_text(line: str) -> str:
        """Texte du heading, `#` de fermeture ATX retirés."""
        body = re.sub(r"^#{2,3}\s*", "", line)
        return re.sub(r"\s*#+\s*$", "", body).strip()

    for raw in markdown.splitlines():
        line = raw.rstrip()
        level = _heading_level(line)
        if level == 2:
            text = _heading_text(line)
            if not text:
                empty.append(PlanViolation(
                    "empty_heading", "Titre `##` sans texte (heading vide invalide)."))
                continue
            current_h2 = Heading(level=2, text=text)
            h2s.append(current_h2)
            current_h3 = None
            continue
        if level == 3:
            text = _heading_text(line)
            if not text:
                empty.append(PlanViolation(
                    "empty_heading", "Titre `###` sans texte (heading vide invalide)."))
                continue
            current_h3 = Heading(level=3, text=text)
            if current_h2 is not None:
                current_h2.children.append(current_h3)
            else:
                # H3 avant tout H2 : arbre malformé, rattaché à un H2 fantôme.
                orphan_parent = Heading(level=2, text="(sans H2 parent)")
                orphan_parent.children.append(current_h3)
                h2s.append(orphan_parent)
                current_h2 = orphan_parent
            continue
        # Ligne de corps : compter les mots pour le titre courant (H3 sinon H2).
        words = len(line.split())
        if current_h3 is not None:
            current_h3.body_words += words
        elif current_h2 is not None:
            current_h2.body_words += words

    return h2s, empty


def _is_interrogative(text: str) -> bool:
    low = text.strip().lower().lstrip("#").strip()
    # retirer un emoji/symbole de tête éventuel
    low = low.lstrip("🔵🟡🟢🔴✅❓📌•-–ﾃ ").strip()
    return low.startswith(_INTERROGATIVE_STARTS)


def _split_terms(raw: str) -> List[str]:
    """PAA / secondary_keywords sont des strings séparées par ' | '."""
    if not raw:
        return []
    return [t.strip() for t in raw.split("|") if t.strip()]


# --------------------------------------------------------------------------- #
# Règles                                                                       #
# --------------------------------------------------------------------------- #

def _check_hierarchy(h2s: List[Heading]) -> List[PlanViolation]:
    v: List[PlanViolation] = []

    real_h2s = [h for h in h2s if h.text != "(sans H2 parent)"]
    if len(real_h2s) < 3:
        v.append(PlanViolation(
            "min_h2",
            f"{len(real_h2s)} H2 dans le plan, minimum 3 attendus.",
        ))

    for h2 in h2s:
        if h2.text == "(sans H2 parent)":
            for child in h2.children:
                v.append(PlanViolation(
                    "h3_before_h2",
                    "H3 placé avant tout H2 (hiérarchie invalide).",
                    child.text,
                ))
            continue

        n_children = len(h2.children)

        # H2 orphelin : ni corps, ni enfants.
        if n_children == 0 and h2.body_words == 0:
            v.append(PlanViolation(
                "h2_orphan", "H2 sans contenu ni H3 (orphelin).", h2.text))

        # H3 orphelin : exactement 1 H3 sous un H2.
        if n_children == 1:
            v.append(PlanViolation(
                "h3_orphan",
                "H2 avec un seul H3 : fusionner dans le corps ou ajouter un 2e H3.",
                h2.text,
            ))

        # Plafond : > 4 H3.
        if n_children > 4:
            v.append(PlanViolation(
                "h3_over_cap",
                f"{n_children} H3 sous ce H2 (max 4) : scinder le H2 en deux.",
                h2.text,
            ))

        # Seuil de subdivision : > 150 mots de corps direct sans H3.
        if n_children == 0 and h2.body_words > 150:
            v.append(PlanViolation(
                "h2_needs_split",
                f"H2 ~{h2.body_words} mots sans H3 : subdiviser en 2-4 H3 (>150 mots).",
                h2.text,
            ))

        # Ponctuation interrogative sur le H2 et ses H3.
        for h in [h2, *h2.children]:
            if _is_interrogative(h.text) and not h.text.rstrip().endswith("?"):
                v.append(PlanViolation(
                    "missing_question_mark",
                    "Titre interrogatif sans `?` final.",
                    h.text,
                ))

    return v


def _check_paa_coverage(markdown: str, paa_raw: str) -> tuple[List[PlanViolation], int, int]:
    paa = _split_terms(paa_raw)
    if not paa:
        return [], 0, 0
    body = _strip_accents(markdown.lower())
    violations, covered = [], 0
    for q in paa:
        # couverture souple : la moitié+ des mots signifiants de la PAA présents.
        # comparaison sans accents (le plan peut varier sur é/e, etc.).
        tokens = [t for t in re.findall(r"\w+", _strip_accents(q.lower())) if len(t) > 3]
        if not tokens:
            covered += 1
            continue
        hits = sum(1 for t in tokens if t in body)
        if hits >= max(1, (len(tokens) + 1) // 2):
            covered += 1
        else:
            violations.append(PlanViolation(
                "paa_uncovered", f"PAA non couverte par le plan : « {q} »."))
    return violations, len(paa), covered


def _check_proof(markdown: str) -> tuple[List[PlanViolation], int, int]:
    links = re.findall(r"https?://[^\s)\]]+", markdown)
    # une statistique = un nombre avec %, ou un nombre suivi d'un mot (année, unité).
    stats = re.findall(r"\b\d+([.,]\d+)?\s?%|\b(19|20)\d{2}\b|\b\d{2,}\b", markdown)
    v: List[PlanViolation] = []
    if len(links) < 3:
        v.append(PlanViolation(
            "few_sources",
            f"{len(links)} lien(s) source dans le plan, minimum 3 institutionnels.",
        ))
    if len(stats) < 2:
        v.append(PlanViolation(
            "few_stats",
            f"{len(stats)} statistique(s) repérée(s), minimum 2 chiffrées datées.",
        ))
    return v, len(links), len(stats)


def validate_plan(markdown: str, paa_raw: str = "") -> PlanReport:
    """Point d'entrée : parse le plan et applique toutes les règles.

    Les commentaires HTML (signaux injectés par `plan init`) sont retirés d'abord :
    seul le contenu réellement rédigé par l'agent est évalué.
    """
    markdown = _strip_comments(markdown)
    h2s, empty_headings = _parse_headings(markdown)
    violations: List[PlanViolation] = []
    violations += empty_headings
    violations += _check_hierarchy(h2s)

    paa_v, paa_total, paa_covered = _check_paa_coverage(markdown, paa_raw)
    violations += paa_v

    proof_v, source_links, stats_found = _check_proof(markdown)
    violations += proof_v

    verdict = "OK" if not violations else "NEEDS_FIX"
    real_h2 = len([h for h in h2s if h.text != "(sans H2 parent)"])
    return PlanReport(
        verdict=verdict,
        violations=violations,
        h2_count=real_h2,
        paa_total=paa_total,
        paa_covered=paa_covered,
        source_links=source_links,
        stats_found=stats_found,
    )
