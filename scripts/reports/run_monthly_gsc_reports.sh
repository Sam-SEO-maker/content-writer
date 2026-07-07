#!/bin/bash
# Lancé par launchd le 1er de chaque mois à 8h (heure de Paris)
# Génère les rapports GSC mensuels pour enseigna.fr et superprof.fr/ressources/

set -euo pipefail

PROJECT="/Users/samuel/Desktop/Claude Code/Content Writer"
VENV="$PROJECT/.venv/bin/python3"
LOG_DIR="$PROJECT/_local/logs"
LOG="$LOG_DIR/gsc_monthly_$(date +%Y-%m).log"

mkdir -p "$LOG_DIR"

echo "=== Rapport GSC mensuel — $(date '+%d/%m/%Y %H:%M') ===" >> "$LOG"

echo "[1/2] Enseigna..." >> "$LOG"
"$VENV" "$PROJECT/scripts/reports/enseigna_gsc_monthly_report.py" >> "$LOG" 2>&1 \
  && echo "  → OK" >> "$LOG" \
  || echo "  → ERREUR (voir log)" >> "$LOG"

echo "[2/2] Superprof Ressources..." >> "$LOG"
"$VENV" "$PROJECT/scripts/reports/superprof_ressources_gsc_monthly_report.py" >> "$LOG" 2>&1 \
  && echo "  → OK" >> "$LOG" \
  || echo "  → ERREUR (voir log)" >> "$LOG"

echo "=== Terminé ===" >> "$LOG"
