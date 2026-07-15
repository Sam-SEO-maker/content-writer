---
description: Applique le moteur de décision (data-driven GSC/DataForSEO) sur les URLs d'un blog depuis Google Sheets.
argument-hint: --blog <id> [--spreadsheet-id ID]
allowed-tools: Bash(python3 content_writer.py batch decision:*), Read
---

Exécute le moteur de décision en batch : pour chaque URL du blog, calcule
l'action stratégique (TITLE_OPTIMIZATION / PARTIAL_REFRESH / FULL_REFRESH /
EEAT_REWRITE / NO_ACTION…) à partir des signaux GSC + DataForSEO.

```bash
python3 content_writer.py batch decision $ARGUMENTS
```

Lecture + écriture de la colonne décision dans le Sheet. N'entraîne aucune
génération : c'est l'étape 5 du workflow (décision), en amont du refresh.

Rapporter la répartition des actions décidées par le moteur.
