#!/bin/bash
# Vérifie au login si le rapport GSC du mois courant a été généré.
# Si non et qu'on est après le 1er du mois, affiche une notification macOS.

LOCAL_DIR="/Users/samuel/Desktop/Claude Code/Content Writer/_local"
MONTH=$(date +%Y-%m)
DAY=$(date +%d)

ENSEIGNA_PDF="$LOCAL_DIR/enseigna_gsc_${MONTH}.pdf"
SP_PDF="$LOCAL_DIR/superprof_ressources_gsc_${MONTH}.pdf"

# Pas de rappel avant le 1er du mois
if [ "$DAY" -lt "1" ]; then
  exit 0
fi

MISSING=""
[ ! -f "$ENSEIGNA_PDF" ]  && MISSING="enseigna.fr"
[ ! -f "$SP_PDF" ]        && MISSING="$MISSING superprof/ressources"

if [ -n "$MISSING" ]; then
  osascript -e "display notification \"Rapport(s) GSC manquant(s) pour $MONTH : $MISSING — Lance : bash scripts/reports/run_monthly_gsc_reports.sh\" with title \"Content Writer — Rapport GSC\" sound name \"Glass\""
fi
