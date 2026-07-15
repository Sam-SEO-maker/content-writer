---
description: Refresh batch depuis Google Sheets (toutes les URLs d'une action donnée pour un blog).
argument-hint: --action <PARTIAL_REFRESH|FULL_REFRESH|REFRESH_TITLES> --blog <id> [--limit N]
allowed-tools: Bash(python3 content_writer.py batch refresh:*), Task, Read, Write
---

Lance un refresh batch. Le `--spreadsheet-id` est repris de `.env` si absent.

```bash
python3 content_writer.py batch refresh $ARGUMENTS
```

`cw batch refresh` prépare le contexte de chaque URL (fetch → audit → décision →
prompt), comme `/refresh` mais en série. La génération de chaque article reste
déléguée au subagent **content-generator** (abonnement Max) après recherche de
sources, article par article — ne pas générer en masse dans la session principale.

Rapporter : nombre d'URLs traitées, stratégies retenues, et les URLs prêtes pour
génération.
