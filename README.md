# Content Writer

Agent autonome de **refresh SEO multi-tenant** : optimise des contenus existants
à partir de signaux data (GSC + DataForSEO), en préservant l'identité éditoriale
de chaque tenant. Décisions data-driven (audit → décision → génération → QC → maillage).

Tenants actuels : `enseigna`, `superprof-ressources`. Le registre est ouvert
(`_shared/config/sites.json`) : onboarder un tenant = 1 dossier `tenants/{id}/`
+ 1 entrée dans `sites.json`, zéro code.

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env   # puis renseigner les credentials (DataForSEO, WP, GSC…)
```

## Utilisation

Le CLI est `content_writer.py`. La liste des groupes et commandes à jour est
auto-générée par Click :

```bash
python3 content_writer.py --help
python3 content_writer.py <groupe> --help    # ex. refresh, batch, audit, tenant
```

Exemple : `python3 content_writer.py refresh <url> --blog enseigna`

## Règle d'Or (invariant)

Ne jamais réduire les assets d'un article refreshé : `assets_after ≥ assets_before`
(images, tableaux, vidéos, liens internes **et** externes, y compris vers des concurrents).

## Documentation

- **Orientation générale** (rôle, architecture, workflow, index skills/commandes) :
  [CLAUDE.md](CLAUDE.md).
- **Règles éditoriales** (SEO/GEO/E-E-A-T, forme HTML/WP) : les skills
  [`edito-refresh`](.claude/skills/edito-refresh/SKILL.md) et
  [`format-wordpress`](.claude/skills/format-wordpress/SKILL.md), chargées par le
  subagent de génération.
- **Règles par tenant** : `tenants/{id}/prompts/site.md`.
- **Architecture des sorties** : [OUTPUT_ARCHITECTURE.md](_shared/docs/OUTPUT_ARCHITECTURE.md).

## Tests

```bash
python3 -m pytest tests/ -q
```

## Licence

Projet interne, tous droits réservés.
