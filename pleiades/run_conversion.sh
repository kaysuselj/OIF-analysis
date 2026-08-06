#!/bin/bash
# Simple wrapper to submit conversion jobs with experiment name in job name
#
# Usage:
#   ./run_conversion.sh control
#   ./run_conversion.sh exp1
#   ./run_conversion.sh exp1 efficiency_npp_co2        # Single dataset only
#   ./run_conversion.sh control "" 12                  # Lower concurrency (less memory)

EXP_NAME="$1"
DATASET="${2:-}"  # Optional: specific dataset
NCONC="${3:-16}"  # Optional: concurrency (default 16, was 24)

if [[ -z "${EXP_NAME}" ]]; then
    echo "Usage: $0 <experiment_name> [dataset] [concurrency]"
    echo ""
    echo "Examples:"
    echo "  $0 control                           # All datasets, 16 tasks parallel"
    echo "  $0 control \"\" 12                     # All datasets, 12 tasks parallel (less memory)"
    echo "  $0 ross_sea                          # All datasets for ross_sea"
    echo "  $0 exp1 efficiency_npp_co2           # Only one dataset for exp1"
    echo "  $0 exp1 efficiency_export 8          # One dataset, 8 tasks (very conservative)"
    echo ""
    echo "Concurrency options:"
    echo "  24 = default (fast, but ~100-120 GB memory)"
    echo "  16 = recommended (safer, ~70-90 GB memory)"
    echo "  12 = conservative (slower, ~50-70 GB memory)"
    echo "  8  = very safe (slow, ~30-50 GB memory)"
    exit 1
fi

# Set job name based on experiment (truncate to 15 chars for PBS)
JOB_NAME="oif_$(echo ${EXP_NAME} | cut -c1-10)"

# Submit with experiment-specific job name and concurrency
if [[ -n "${DATASET}" ]]; then
    echo "Submitting ${EXP_NAME} - dataset: ${DATASET} - concurrency: ${NCONC}"
    qsub -N "${JOB_NAME}" -v EXP_NAME="${EXP_NAME}",DATASET="${DATASET}",NCONC="${NCONC}" submit_convert_experiment.pbs
else
    echo "Submitting ${EXP_NAME} - all datasets - concurrency: ${NCONC}"
    qsub -N "${JOB_NAME}" -v EXP_NAME="${EXP_NAME}",NCONC="${NCONC}" submit_convert_experiment.pbs
fi

echo "Job submitted with name: ${JOB_NAME}"
echo "Concurrency: ${NCONC} tasks in parallel"
echo "Check status: qstat -u \$USER"
echo "View log: tail -f ~/nobackup/OIF/logs/convert_${EXP_NAME}.log"
