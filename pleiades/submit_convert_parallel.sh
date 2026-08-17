#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Submit conversion jobs — ONE PBS job per experiment.
#
# Each job gets one exclusive 40-core sky_ele node and runs every
# (dataset x 5-year chunk) pair concurrently on it.
#
# Usage:
#   ./submit_convert_parallel.sh control
#   ./submit_convert_parallel.sh control exp1 exp5
#   NCONC=4 ./submit_convert_parallel.sh control         # lower concurrency
#
# NCONC defaults to 8 in submit_convert_experiment.pbs. Values >=12 have been seen
# to OOM/hang the node at K_MAX=38, so only raise it deliberately.
#
# Sea ice is only converted for the control experiment.
# ═══════════════════════════════════════════════════════════════════════════════

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <experiment_name> [more experiments...]"
    echo "  e.g., $0 control"
    echo "        $0 control exp1 exp5"
    exit 1
fi

PBS_SCRIPT="submit_convert_experiment.pbs"

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "Submitting one conversion job per experiment: $*"
echo "Each job: 1 node, 40 cores, all datasets x 7 five-year chunks (1992-2026)"
[[ -n "${NCONC}" ]] && echo "Concurrency override: NCONC=${NCONC}"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

for EXP_NAME in "$@"; do
    VARS="EXP_NAME=${EXP_NAME}"
    [[ -n "${NCONC}" ]] && VARS="${VARS},NCONC=${NCONC}"

    echo "Submitting job for experiment: ${EXP_NAME}"
    [[ "${EXP_NAME}" == "control" ]] && echo "  (includes sea_ice)"
    qsub -v "${VARS}" "${PBS_SCRIPT}"

    sleep 0.5
done

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "Submitted $# job(s)"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Monitor with: qstat -u \$USER"
echo "Job logs    : /home5/ksuselj1/nobackup/OIF/logs/convert_<exp>.log"
echo "Chunk logs  : /home5/ksuselj1/nobackup/OIF/logs/chunks/convert_<exp>_<dataset>_<years>.log"
