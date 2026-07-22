# Semantic density: occurrence-based model (SOSEO / DSEO)

Reference loaded on demand from `edito-refresh`. **Never reason in
"density %"**: reason in coverage + occurrences.

## Principle: two axes

1. **Coverage (BREADTH)**: use as many terms of the semantic field as possible. TOP 3 articles cover ~90% of the relevant terms.
2. **Moderation (DEPTH)**: do not repeat the same terms excessively.

The common mistake is NOT using too many different terms; it is
**repeating the same 5-6 terms too often**. Aim for breadth, not depth.

## Repetition caps (article of ~1800 words)

| Element | Limit |
|---------|--------|
| Main keyword (exact match) | **3-6 occurrences** (H1 + intro + 1-2 H2s + conclusion) |
| Top 10 important topic terms | 2-5 occurrences each, distributed |
| Other semantic-field terms | 1-3 occurrences each |
| Spacing | not the same term in 2 consecutive paragraphs |

## Mandatory synonymy rule

Any term appearing **3 times or more** → replaced by a synonym/paraphrase
in ≥ 50% of its occurrences. French content examples:
- « musculation » → « renforcement musculaire », « travail en salle »
- « coach » → « entraîneur », « préparateur physique »
- « séance » → « session », « créneau », « entraînement »

## SOSEO / DSEO target (YourTextGuru)

The target is **variable: it depends on each query's SERP**, never on a
uniform threshold. The YTG guide provides the competitors' average scores
(`top3_soseo`/`top3_dseo` and `top10_soseo`/`top10_dseo`); the rule:

| Metric | Rule vs TOP 3 average | Rule vs TOP 10 average |
|----------|------------------------|--------------------------|
| **SOSEO** (coverage) | article **> average** (e.g. average 60% → aim for > 60%) | article **> average** |
| **DSEO** (danger) | article **strictly < average** (e.g. average 5% → stay < 5%) | article **strictly < average** |

Beat the average, do not blow past it: an article at 116% SOSEO / 37% DSEO is
unusable (over-optimisation). Exceeding the SOSEO average by a few points
is enough; the DSEO must always stay below both averages.

## ❌ Forbidden / ✅ Correct

Forbidden: stacking 3+ technical terms in one sentence; repeating a term in 2
consecutive paragraphs; vocabulary "catalogue" sentences; forcing a technical
term where a common word suffices; concentrating the vocabulary in one section.

Correct: specialised vocabulary when it adds precision; paraphrases rather than
repetitions; uniform distribution; write for the reader first; let some
paragraphs "breathe" in natural prose.

## Example

French content example:

```
❌ SUROPTIMISÉ :
"Le squat, exercice polyarticulaire d'hypertrophie, sollicite les quadriceps...
La charge progressive en squat permet l'hypertrophie des quadriceps..."
→ 3x "squat", 2x "hypertrophie", 2x "quadriceps" en 3 phrases

✅ OPTIMAL :
"Le squat sollicite simultanément plusieurs groupes musculaires majeurs :
quadriceps, fessiers et ischio-jambiers. C'est un mouvement fondamental pour
développer la force du bas du corps. En augmentant progressivement la charge,
vous stimulez une croissance musculaire durable."
→ 1x "squat", termes variés, lecture fluide
```

*Canonical reference for the SOSEO/DSEO model (migrated from the former STYLE_GUIDE.md §11,
deleted). Cited by the full_refresh and semantic_reorientation strategies.*
