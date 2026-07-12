#!/bin/bash
# Run all 4 IC (Increased Consumption) scenarios sequentially.
# IC = MD + 22 TWh baseload (230 TWh total Norwegian demand).
#
# Usage:
#   nohup bash run_all_IC.sh > run_all_IC.log 2>&1 &
#   tail -f run_all_IC.log

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

echo "================================================================"
echo "Nuclear IC scenarios — started $(date)"
echo "Working directory: $SCRIPT_DIR"
echo "Python: $(which python)"
echo "================================================================"

# Ensure timeseries symlink exists
if [ ! -e scenarios/nuclear_IC/data/timeseries_profiles.csv ]; then
    ln -s "$SCRIPT_DIR/scenarios/baseline/data/timeseries_profiles.csv" \
          "$SCRIPT_DIR/scenarios/nuclear_IC/data/timeseries_profiles.csv"
    echo "Created timeseries symlink"
fi

# Run scenarios sequentially
for SCENARIO in BL_IC SMR1_IC SMR3_IC SMR6_IC; do
    echo ""
    echo "================================================================"
    echo "Starting $SCENARIO — $(date)"
    echo "================================================================"
    python run_nuclear_IC.py "$SCENARIO"
    echo ""
    echo "$SCENARIO completed — $(date)"
done

echo ""
echo "================================================================"
echo "All IC scenarios completed — $(date)"
echo "================================================================"
