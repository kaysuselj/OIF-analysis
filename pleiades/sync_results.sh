#!/bin/bash
# Sync NetCDF output from Pleiades to local machine.
# Run this from your LOCAL computer.
#
# Usage:
#   bash sync_results.sh
#   bash sync_results.sh --dry-run   (preview without transferring)

PLEIADES_USER="ksuselj1"
REMOTE_HOST="pfe.nas.nasa.gov"
BASE_REMOTE="/home5/${PLEIADES_USER}/nobackup/OIF/ED_experiments"
BASE_LOCAL="/Users/ksuselj/Desktop/Projects/OIF/data_oif"

EXPERIMENTS=("control" "exp1" "exp5")

DRY_RUN=""
if [[ "${1}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
    echo "[dry-run] No files will be transferred."
fi

# Open a single master SSH connection — authenticate once with RSA token here.
SOCKET="/tmp/ssh_pleiades_$$"
echo "Connecting to ${REMOTE_HOST} (enter RSA token once) ..."
ssh -M -S "${SOCKET}" -o ControlPersist=yes -fN "${PLEIADES_USER}@${REMOTE_HOST}"

trap 'ssh -S "${SOCKET}" -O exit "${REMOTE_HOST}" 2>/dev/null' EXIT

for EXP in "${EXPERIMENTS[@]}"; do
    REMOTE_DIR="${BASE_REMOTE}/${EXP}/run/diags/monthly_netcdf"
    LOCAL_DIR="${BASE_LOCAL}/${EXP}/run/diags/monthly_netcdf"

    echo ""
    echo "── ${EXP} ──────────────────────────────────"
    echo "  From: ${PLEIADES_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"
    echo "  To  : ${LOCAL_DIR}/"

    mkdir -p "${LOCAL_DIR}"

    rsync -avz --progress \
        -e "ssh -S ${SOCKET}" \
        ${DRY_RUN} \
        --include="*.nc" \
        --exclude="*" \
        "${PLEIADES_USER}@${REMOTE_HOST}:${REMOTE_DIR}/" \
        "${LOCAL_DIR}/"
done

echo ""
echo "All experiments synced."
