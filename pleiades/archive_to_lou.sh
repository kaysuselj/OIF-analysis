#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Archive raw MDS output from /nobackup to Lou, ONE TARBALL PER VARIABLE PREFIX
# PER STREAM.
#
# RUN THIS ON A LOU FRONT END (lfe), NOT on pfe:
#     ssh lfe
# Per the NAS docs, the Lustre /nobackup filesystems are mounted on the LFEs, and
# /u/$USER on an LFE is your Lou home. On a pfe, /u/$USER is just your regular
# (small, quota'd) home directory -- writing tarballs there would fill your home
# and free nothing on /nobackup.
#
# Why per-prefix tarballs: MDS writes one .data/.meta pair per prefix per
# iteration, so a stream directory holds thousands of small files. Lou has no disk
# quota but does have a hard limit of 300,000 inodes (250,000 soft), and it is
# tape-backed, so it handles a few large files far better than many small ones.
# Bundling per prefix keeps the inode count tiny AND means a later retrieval pulls
# back exactly the variable you need (one tar) instead of seeking across the tree.
#
# Usage (from an LFE):
#   ./archive_to_lou.sh --dry-run control            # preview, transfer nothing
#   ./archive_to_lou.sh control                      # archive one experiment
#   ./archive_to_lou.sh control exp1 exp5            # several
#   STREAMS="monthly daily" ./archive_to_lou.sh exp1 # subset of streams
#
# Safety: this script never deletes anything. It writes tarballs to a staging
# dir, ships them to Lou with shiftc --verify, and reports what landed. Delete
# the raw files yourself only after you've confirmed the archive AND validated
# the NetCDF conversion you care about.
# ═══════════════════════════════════════════════════════════════════════════════
set -uo pipefail

USER_NAME="${USER}"
NOBACKUP_BASE="/nobackup/${USER_NAME}/OIF/ED_experiments"
LOU_BASE="/u/${USER_NAME}/OIF/ED_experiments_raw"
STAGING_BASE="/nobackup/${USER_NAME}/OIF/_archive_staging"

# Streams to archive (override with STREAMS="monthly daily")
STREAMS="${STREAMS:-3hourly daily monthly budget}"

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=1
    shift
fi

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 [--dry-run] <experiment> [more experiments...]"
    echo "  e.g. $0 --dry-run control"
    echo "       $0 control exp1 exp5"
    echo "       STREAMS=\"monthly\" $0 exp1"
    exit 1
fi

# Must be on an LFE: that is the only place where BOTH /nobackup (source) and the
# Lou home /u/$USER (destination) are visible. On a pfe, /u/$USER resolves to your
# regular home, so this would quietly fill your home quota instead of archiving.
# Guard on the hostname rather than just "does /u/$USER exist", because that test
# passes on a pfe too.
HOSTNAME_SHORT=$(hostname -s 2>/dev/null || hostname)
case "${HOSTNAME_SHORT}" in
    lfe*) : ;;   # good
    *)
        echo "ERROR: this must run on a Lou front end (lfe), not '${HOSTNAME_SHORT}'."
        echo "       On a pfe, /u/${USER_NAME} is your regular home, NOT Lou --"
        echo "       archiving there would fill your home and free nothing on /nobackup."
        echo "       Do:  ssh lfe   then re-run this script."
        echo ""
        echo "       (Override with FORCE_HOST=1 only if you are certain the paths"
        echo "        below are correct on this machine.)"
        echo "         source: ${NOBACKUP_BASE}"
        echo "         dest  : ${LOU_BASE}"
        [[ "${FORCE_HOST:-0}" == "1" ]] || exit 1
        echo "       FORCE_HOST=1 set — continuing anyway."
        ;;
esac

if [[ ! -d "${NOBACKUP_BASE}" ]]; then
    echo "ERROR: source not found: ${NOBACKUP_BASE}"
    echo "       /nobackup should be mounted on the LFEs; check the path."
    exit 1
fi

# shiftc is preferred (checksums, restartable). cp/mcp also work on an LFE since
# /nobackup is mounted locally there, so fall back rather than refusing to run.
XFER="shiftc"
if ! command -v shiftc >/dev/null 2>&1; then
    echo "NOTE: shiftc not found; falling back to cp (no checksum verification)."
    echo "      To get shiftc, try: module load shift"
    XFER="cp"
fi

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "Archive raw MDS → Lou"
echo "  Host        : ${HOSTNAME_SHORT}"
echo "  Experiments : $*"
echo "  Streams     : ${STREAMS}"
echo "  Source      : ${NOBACKUP_BASE}/<exp>/run/diags/<stream>/"
echo "  Staging     : ${STAGING_BASE}"
echo "  Destination : ${LOU_BASE}/<exp>/<stream>/   (Lou home)"
echo "  Transfer    : ${XFER}"
[[ ${DRY_RUN} -eq 1 ]] && echo "  MODE        : DRY RUN (nothing written or transferred)"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""

TOTAL_TARS=0
TOTAL_FAIL=0

for EXP in "$@"; do
    EXP_DIR="${NOBACKUP_BASE}/${EXP}/run/diags"
    if [[ ! -d "${EXP_DIR}" ]]; then
        echo "SKIP ${EXP}: ${EXP_DIR} does not exist"
        continue
    fi

    for STREAM in ${STREAMS}; do
        SRC="${EXP_DIR}/${STREAM}"
        [[ -d "${SRC}" ]] || { echo "  skip ${EXP}/${STREAM}: no such directory"; continue; }

        # Distinct variable prefixes: strip the .<iter>.data/.meta suffix.
        # MDS names look like  mldDepth.0000271740.data
        # Deliberately avoids `mapfile` (bash 4+) and `find -printf` (GNU only) so
        # this also runs under the bash 3.2 / BSD userland on a Mac for testing.
        PREFIX_LIST=$(
            find "${SRC}" -maxdepth 1 -type f \( -name '*.data' -o -name '*.meta' \) 2>/dev/null \
                | sed -e 's|.*/||' \
                | sed -E 's/\.[0-9]{6,}\.(data|meta)$//' \
                | sort -u
        )

        if [[ -z "${PREFIX_LIST}" ]]; then
            echo "  skip ${EXP}/${STREAM}: no MDS .data/.meta files found"
            continue
        fi

        NPREFIX=$(printf '%s\n' "${PREFIX_LIST}" | wc -l | tr -d ' ')
        echo "── ${EXP}/${STREAM}: ${NPREFIX} prefixes ────────────────────────"

        STAGE="${STAGING_BASE}/${EXP}/${STREAM}"
        DEST="${LOU_BASE}/${EXP}/${STREAM}"
        [[ ${DRY_RUN} -eq 0 ]] && mkdir -p "${STAGE}"
        [[ ${DRY_RUN} -eq 0 ]] && mkdir -p "${DEST}"

        while IFS= read -r PREFIX; do
            [[ -n "${PREFIX}" ]] || continue
            NFILES=$(find "${SRC}" -maxdepth 1 -type f -name "${PREFIX}.*" | wc -l)
            SIZE=$(du -csh $(find "${SRC}" -maxdepth 1 -type f -name "${PREFIX}.*") 2>/dev/null \
                   | tail -1 | awk '{print $1}')
            TAR="${STAGE}/${EXP}_${STREAM}_${PREFIX}.tar"

            if [[ ${DRY_RUN} -eq 1 ]]; then
                printf "  [dry-run] %-24s %5s files  %8s  ->  %s\n" \
                       "${PREFIX}" "${NFILES}" "${SIZE:-?}" "${DEST}/$(basename "${TAR}")"
                TOTAL_TARS=$((TOTAL_TARS + 1))
                continue
            fi

            printf "  %-24s %5s files  %8s ... " "${PREFIX}" "${NFILES}" "${SIZE:-?}"

            # -C so paths inside the tar are relative to the stream dir, which makes
            # extraction straightforward: tar -xf ... -C <target stream dir>
            if ! tar -cf "${TAR}" -C "${SRC}" \
                    $(cd "${SRC}" && ls -1 "${PREFIX}".*[0-9].data "${PREFIX}".*[0-9].meta 2>/dev/null); then
                echo "TAR FAILED"
                TOTAL_FAIL=$((TOTAL_FAIL + 1))
                rm -f "${TAR}"
                continue
            fi

            # --verify makes shiftc checksum both ends; worth it before you delete
            # the only copy of anything. (--create-tar=no: we already tarred.)
            if [[ "${XFER}" == "shiftc" ]]; then
                XFER_OK=0
                shiftc --wait --verify --create-tar=no "${TAR}" "${DEST}/" >/dev/null 2>&1 && XFER_OK=1
            else
                XFER_OK=0
                cp -p "${TAR}" "${DEST}/" && XFER_OK=1
            fi

            if [[ ${XFER_OK} -eq 1 ]]; then
                echo "archived"
                rm -f "${TAR}"          # staging copy only; raw source untouched
                TOTAL_TARS=$((TOTAL_TARS + 1))
            else
                echo "${XFER} FAILED (tar kept at ${TAR})"
                TOTAL_FAIL=$((TOTAL_FAIL + 1))
            fi
        # Feed the prefix list via a here-string rather than a pipe: a pipe would put
        # the loop in a subshell and the TOTAL_* counters would not survive it.
        done <<< "${PREFIX_LIST}"
        echo ""
    done
done

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "SUMMARY"
echo "  Tarballs archived : ${TOTAL_TARS}"
echo "  Failures          : ${TOTAL_FAIL}"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Verify on Lou before deleting anything from /nobackup (you are on ${HOSTNAME_SHORT}):"
echo "  ls -lh ${LOU_BASE}/<exp>/<stream>/"
echo "  # spot-check a tar's contents without staging the whole thing off tape:"
echo "  tar -tvf ${LOU_BASE}/<exp>/<stream>/<exp>_<stream>_<PREFIX>.tar | head"
echo ""
echo "Watch your Lou inode usage (300,000 hard limit) — per-prefix tars keep this low:"
echo "  quota -v          # or: dmfquota"
echo ""
echo "To retrieve one variable later (run from an LFE):"
echo "  ${XFER} ${LOU_BASE}/<exp>/<stream>/<exp>_<stream>_<PREFIX>.tar ${NOBACKUP_BASE}/<exp>/run/diags/<stream>/"
echo "  cd ${NOBACKUP_BASE}/<exp>/run/diags/<stream>/ && tar -xf <exp>_<stream>_<PREFIX>.tar"

[[ ${TOTAL_FAIL} -gt 0 ]] && exit 1
exit 0
