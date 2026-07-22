# Source brief: schema and flow

Reference loaded on demand from `source-research`. The skill's output format
and how it feeds generation.

## Schema

```json
{
  "sujet": "…",
  "sources": [
    {
      "source": "Name of the organisation/author (e.g. INSEE)",
      "url": "https://… (deep-link to the precise page)",
      "year": 2025,
      "claim": "The exact data point/statement this source supports"
    }
  ],
  "lacunes": ["Points not covered, to handle with caution or without figures"]
}
```

Field by field:

- **`sujet`**: the topic/URL being documented, as received.
- **`sources[]`**: verified sources, one entry per (source × claim). The same source
  can appear twice if it supports two distinct claims.
  - `source`: identifiable organisation or author (not "a study").
  - `url`: precise page carrying the information (deep-link), never a homepage.
  - `year`: year **of the data** (not of consultation), integer. Mandatory for
    any statistic; otherwise the source is discarded (see `source-quality.md`).
  - `claim`: the exact statement supported, so that generation does not cite the
    source out of its scope.
- **`lacunes[]`**: what could not be sourced: generation handles these points without
  invented figures, or avoids them.

## Filled example

```json
{
  "sujet": "Le soutien scolaire au collège en France",
  "sources": [
    {
      "source": "DEPP (Ministère de l'Éducation nationale)",
      "url": "https://www.education.gouv.fr/…/note-depp-2025-soutien-scolaire",
      "year": 2025,
      "claim": "Part des collégiens bénéficiant d'un accompagnement scolaire hors classe"
    },
    {
      "source": "INSEE",
      "url": "https://www.insee.fr/fr/statistiques/…",
      "year": 2024,
      "claim": "Dépense moyenne des ménages en cours particuliers"
    }
  ],
  "lacunes": ["Efficacité comparée présentiel vs en ligne : pas de source primaire datée"]
}
```

## Injection flow (current state)

The brief travels **as an argument** (conversational), not via a file:

1. The skill (invoked on its own or by the `refresh` orchestrator, "Source
   research" step) produces this JSON.
2. `refresh` passes it **as an argument** to the `content-generator` subagent, **alongside**
   the `generation_prompt.txt` path (see `.claude/commands/refresh.md`, steps 2-3).
3. The subagent uses it for **the content** (sourced quotes, dated statistics)
   and to fill in the **`eeat_sources`** field of the metadata
   (`source`/`url`/`year`; the `claim` does not go there, it only serves in-text placement;
   see `format-wordpress/SKILL.md`).

> The brief **does not go through** `generation_prompt.txt`: that file only contains
> the data produced by `cw refresh` (GSC/SERP/PAA/intent/assets). Do not look for a
> "sources" slot in it.

## Backlog: making the flow deterministic

To reproduce the brief without intervention, mirror the earlier PAA fix: add the field
to `MinimalRow` (`cli/commands/refresh.py`), propagate it into `audit_data`, then render
a `### Sources vérifiées` section in `ghostwriter._build_generation_prompt`
(`scripts/ghostwriter/ghostwriter.py`, next to the PAA section). Not done to date.
