#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Submit parallel conversion jobs - one PBS job per dataset
# Each job processes all 5-year chunks from 1992-2026
#
# Usage:
#   ./submit_convert_parallel.sh control
#   ./submit_convert_parallel.sh exp1
#   ./submit_convert_parallel.sh exp5
#
# Sea ice is only converted for control experiment
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

# Add sea_ice only for control experiment
if [[ "${EXP_NAME}" == "control" ]]; then
    DATASETS+=("sea_ice")
fi

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "Submitting parallel conversion jobs for experiment: ${EXP_NAME}"
echo "Datasets: ${#DATASETS[@]} (each will process 7 five-year chunks: 1992-2026)"
if [[ "${EXP_NAME}" == "control" ]]; then
    echo "Note: Including sea_ice dataset for control experiment"
fi
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
echo "Each job will process 7 five-year chunks (1992-2026)"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Monitor with: qstat -u \$USER"
echo "Check logs in: /home5/ksuselj1/nobackup/OIF/logs/convert_${EXP_NAME}_*.log"
