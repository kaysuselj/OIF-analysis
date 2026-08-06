#!/bin/bash
# Simple wrapper to submit conversion jobs with experiment name in job name
#
# Usage:
#   ./run_conversion.sh control
#   ./run_conversion.sh exp1
#   ./run_conversion.sh exp1 efficiency_core   # Single dataset only

EXP_NAME="$1"
DATASET="${2:-}"  # Optional: specific dataset

if [[ -z "${EXP_NAME}" ]]; then
    echo "Usage: $0 <experiment_name> [dataset]"
    echo ""
    echo "Examples:"
    echo "  $0 control                    # All datasets for control"
    echo "  $0 ross_sea                   # All datasets for ross_sea"
    echo "  $0 exp1 efficiency_core       # Only efficiency_core for exp1"
    exit 1
fi

# Set job name based on experiment (truncate to 15 chars for PBS)
JOB_NAME="oif_$(echo ${EXP_NAME} | cut -c1-10)"

# Submit with experiment-specific job name
if [[ -n "${DATASET}" ]]; then
    echo "Submitting ${EXP_NAME} - dataset: ${DATASET}"
    qsub -N "${JOB_NAME}" -v EXP_NAME="${EXP_NAME}",DATASET="${DATASET}" submit_convert_experiment.pbs
else
    echo "Submitting ${EXP_NAME} - all datasets"
    qsub -N "${JOB_NAME}" -v EXP_NAME="${EXP_NAME}" submit_convert_experiment.pbs
fi

echo "Job submitted with name: ${JOB_NAME}"
echo "Check status: qstat -u \$USER"
echo "View log: tail -f ~/nobackup/OIF/logs/convert_${EXP_NAME}.log"
