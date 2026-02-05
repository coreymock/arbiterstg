#!/bin/zsh
set -e

TEXT="${1:-input.txt}"
TRACE="trace.json"
REPORT="arbiter_report.json"

echo "Generating trace..."
python3 safe_tracegen.py --infile "$TEXT" --out "$TRACE"

echo "Running Arbiter..."
python3 arbiterstg.py "$TRACE" -o "$REPORT"

echo ""
echo "Done."
echo "Trace:   $TRACE"
echo "Report:  $REPORT"