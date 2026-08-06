#!/bin/bash
# Simple wrapper to submit conversion jobs with experiment name in job name
#
# Usage:
#   ./run_conversion.sh control
#   ./run_conversion.sh exp1 -d efficiency_npp_co2
#   ./run_conversion.sh control -n 12
#   ./run_conversion.sh control -d efficiency_export -n 8

# Defaults
DATASET=""
NCONC=16  # Default: 16 tasks in parallel (safer than 24)

# Show usage
usage() {
    cat <<EOF
Usage: $0 <experiment_name> [options]

Required:
  <experiment_name>      Experiment to process (control, ross_sea, exp1, etc.)

Options:
  -d, --dataset NAME     Process only this dataset (default: all datasets)
  -n, --nconc NUM        Number of parallel tasks (default: 16)
  -h, --help             Show this help message

Examples:
  $0 control                              # All datasets, 16 tasks parallel
  $0 control -n 12                        # All datasets, 12 tasks (less memory)
  $0 ross_sea                             # All datasets for ross_sea
  $0 exp1 -d efficiency_npp_co2           # Only one dataset for exp1
  $0 control -d efficiency_export -n 8    # One dataset, 8 tasks (very safe)

Concurrency options (-n):
  24 = fast, but ~100-120 GB memory
  16 = recommended (default), ~70-90 GB memory
  12 = conservative, ~50-70 GB memory
  8  = very safe, ~30-50 GB memory

Available datasets:
  efficiency_npp_co2, efficiency_export, efficiency_dic_nutrients,
  pft_biomass, fe_budget, physical, pft_lim1-5, nutrients, carbon_tracers, co2
EOF
    exit 1
}

# Parse arguments
if [[ $# -eq 0 ]]; then
    usage
fi

# First argument is always experiment name (unless it's a flag)
if [[ "$1" == -* ]]; then
    echo "ERROR: First argument must be experiment name"
    echo ""
    usage
fi

EXP_NAME="$1"
shift

# Parse optional flags
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dataset)
            DATASET="$2"
            shift 2
            ;;
        -n|--nconc)
            NCONC="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            echo ""
            usage
            ;;
    esac
done

# Set job name based on experiment (truncate to 10 chars for PBS)
JOB_NAME="oif_$(echo ${EXP_NAME} | cut -c1-10)"

# Build qsub command
QSUB_VARS="EXP_NAME=${EXP_NAME},NCONC=${NCONC}"
if [[ -n "${DATASET}" ]]; then
    QSUB_VARS="${QSUB_VARS},DATASET=${DATASET}"
fi

# Submit job
echo "═══════════════════════════════════════════════════════════"
echo "Submitting conversion job:"
echo "  Experiment:   ${EXP_NAME}"
echo "  Dataset:      ${DATASET:-all datasets}"
echo "  Concurrency:  ${NCONC} tasks in parallel"
echo "  Job name:     ${JOB_NAME}"
echo "═══════════════════════════════════════════════════════════"

qsub -N "${JOB_NAME}" -v "${QSUB_VARS}" submit_convert_experiment.pbs

echo ""
echo "Job submitted!"
echo "Check status: qstat -u \$USER"
echo "View log:     tail -f ~/nobackup/OIF/logs/convert_${EXP_NAME}.log"
echo "Kill job:     qdel <job_id>"
