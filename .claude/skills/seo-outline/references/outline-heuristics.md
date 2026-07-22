# Outline heuristics: subdivision edge cases

Details of the judgment calls from `SKILL.md` (loaded on demand). The base algorithm:
count the **planned** paragraph words per section, apply the thresholds.

## Subdividing an H2 into H3s

```
planned_words(H2) < 150   → 0 H3s (content directly under the H2)
150 ≤ words < ~400        → 2 to 3 H3s
~400 ≤ words ≤ ~600       → 3 to 4 H3s
words > ~600              → split into 2 H2s (each re-evaluated)
```

- Never **a single** H3: either stay at 0 (direct content), or 2 or more. An isolated
  H3 signals an arbitrary split: merge it into the body of the H2.
- Never **more than 4** H3s: beyond that, the H2 actually covers two topics → split
  it. Two H2s with 3 H3s each beat one H2 with 6 H3s.

## H2 at the limit (around 150 words)

Grey zone of 130-170 words: decide by **cohesion**, not by the word counter.

- The content answers **one** question → keep it as an H2 without H3s, even at 160 words.
- The content covers **two distinct angles** (e.g. "advantages" + "limitations") →
  subdivide into 2 H3s even at 140 words. Subdivision follows meaning; the 150
  threshold is only a default trigger.

## Multiple PAAs under one H2

- 2-3 related PAAs (same intent) → one H2 with one H3 per PAA (direct answer at
  the top of each H3). Respects the floor of 2 H3s.
- A single PAA → H2 without H3s, the direct answer opens the H2.
- Heterogeneous PAAs → do not force them under one H2; spread them across several H2s.

## Choosing 3 vs 4 H3s

- Prefer **3 balanced H3s** over 4 unbalanced ones (a starved 30-word H3 =
  merge it with a neighbour).
- Go to 4 H3s only if each holds roughly 80 words or more and covers its own angle.

## Interrogative headings

- Only turn into a question what **is** a question (often a PAA reused
  verbatim), as in this French example: « Combien coûte un cours particulier ? ».
- A declarative heading stays declarative, without a `?` (French example: « Le tarif moyen d'un cours »).
- Do not stack questions: alternate interrogative and declarative headings for rhythm.
