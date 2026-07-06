#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Submit parallel conversion jobs - one PBS job per dataset
#
# Usage:
#   ./submit_convert_parallel.sh control
#   ./submit_convert_parallel.sh exp1
#   ./submit_convert_parallel.sh exp5
# ═══════════════════════════════════════════════════════════════════════════════

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <experiment_name>"
    echo "  e.g., $0 control"
    echo "        $0 exp1"
    echo "        $0 exp5"
    exit 1
fi

EXP_NAME="$1"

# All datasets from convert_to_netcdf.py
# pft_lim1, pft_lim2, pft_lim3, pft_lim4, pft_lim5, nutrients, co2, carbon_tracers
DATASETS=(
    "pft_lim1"
    "pft_lim2"
    "pft_lim3"
    "pft_lim4"
    "pft_lim5"
    "nutrients"
    "co2"
    "carbon_tracers"
)

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "Submitting parallel conversion jobs for experiment: ${EXP_NAME}"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

# Submit one job for each dataset
for DATASET in "${DATASETS[@]}"; do
    echo "Submitting job for dataset: ${DATASET}"
    qsub -v EXP_NAME="${EXP_NAME}",DATASET="${DATASET}" submit_convert_single.pbs

    # Small delay to avoid overwhelming the scheduler
    sleep 0.5
done

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "All ${#DATASETS[@]} jobs submitted for ${EXP_NAME}"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Monitor with: qstat -u \$USER"
echo "Check logs in: /home5/ksuselj1/nobackup/OIF/logs/convert_${EXP_NAME}_*.log"
