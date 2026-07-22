# E-E-A-T: detailed framework (Experience, Expertise, Authoritativeness, Trust)

Reference loaded on demand from `edito-refresh`. The 4 pillars with ❌/✅
pairs and signals. **Key principle**: Trust is the most important element;
without trust, the other signals are insufficient.

## 1. Experience (hands-on experience)

French content examples:
- ❌ « Acadomia est une plateforme de soutien scolaire. »
- ✅ « Après avoir testé Acadomia pendant 3 mois avec ma fille en 4ème, voici notre retour détaillé… L'enseignante a d'abord évalué le niveau, puis proposé un plan personnalisé. »

Signals: specific concrete details, nuances only a practitioner would know, field vocabulary, real screenshots/photos if available.

## 2. Expertise (technical competence)

French content examples:
- ❌ « Beaucoup d'élèves prennent des cours particuliers. »
- ✅ « Selon le DEPP (ministère de l'Éducation), 40% des collégiens bénéficient de soutien scolaire (2025). Le marché représente 2,5 milliards € annuels. »

Signals: academic sources (CNRS, INSERM, DEPP), data < 2 years old, technical vocabulary explained, recognised experts, methodologically sound studies.

## 3. Authoritativeness (authority)

French content examples:
- ❌ « Un expert recommande cette plateforme. »
- ✅ « Dr. Marie Dupont, directrice du laboratoire de psychologie de l'apprentissage à la Sorbonne et auteure de "Apprendre Efficacement" (Dunod, 2023), recommande… »

Signals: author with full credentials, academic/professional titles, recognised affiliations, dated publications, citations of primary sources, links to authority sites.

## 4. Trustworthiness (reliability)

Signals: transparent disclaimers, methodology explained, visible dates, verifiable sources with links, absence of conflicts of interest (or full transparency).

> **Site note**: the **editorial independence statement** is **forbidden on
> Enseigna** (see its skill), do not include it. It is not prescribed for any
> current site by default.

## Institutional sources (cross-cutting principle)

**Minimum: ≥ 3 institutional sources cited with a link** (uniform, all sites).

**Types of domains to target** (valid whatever the site):
- **Governmental / official**: ministries, public agencies, regulatory authorities.
- **Academic**: open archives, peer-reviewed journals, university presses.
- **Statistical**: national statistics institute, international bodies (OECD…).

**Concrete domains are per-site knowledge, not cross-cutting**: they live
in the site's directory `sites/<site-slug>/sources/authority-map.md` (per subject + a
cross-cutting base), consumed at tier 1 of the `source-research` skill. Do not
maintain a list of domains here. Forbidden domains (competitors, aggregators):
`source-research/references/blacklisted-domains.md`.

**Never link to Wikipedia** (all sites): Wikipedia aggregates primary sources
without being an E-E-A-T authority itself. Trace back to the source it cites (study,
official text, institution) and link that instead.

## YMYL (Your Money or Your Life)

Topics impacting the reader's health, finances or happiness → high E-E-A-T level required.
- **Education**: institutional sources, official data, demonstrated pedagogical expertise.
- **Finance/pricing (Enseigna)**: price transparency, objective comparisons.

## Author and bio: handled by WordPress, NOT in the HTML

The author, their bio and credentials are handled by the **WordPress profile**,
outside the article body. **Do not insert an "About the author" block in the
generated HTML.** (The author name remains an E-E-A-T fact, simply carried by the CMS.)

## E-E-A-T audit grid (0-100): to assess an existing article

Experience /25 · Expertise /25 · Authority /25 · Trust /25.
- < 40: full rewrite · 40-60: partial rewrite (E-E-A-T enrichment)
- 60-80: targeted update · > 80: light refresh (stats, dates)

*Source: merger of the former EEAT_GUIDE.md (knowledge migrated into references). Decisions
applied: min 3 sources uniform (C10), bio outside HTML (C11), independence statement forbidden (C12).*
