# Parallel NetCDF Conversion on Pleiades

This directory contains scripts for converting ECCO-Darwin binary output to NetCDF format, with support for parallel processing to avoid walltime limits.

## Problem

The original `submit_convert.pbs` script processes all datasets (pft_lim1-5, nutrients, co2, carbon_tracers) in a single job, which can exceed the 4-hour walltime limit.

## Solution: Parallel Jobs

The new approach submits **one PBS job per dataset**, allowing them to run in parallel:

- **8 separate jobs** (pft_lim1, pft_lim2, pft_lim3, pft_lim4, pft_lim5, nutrients, co2, carbon_tracers)
- Each job uses **4 CPUs, 16 GB RAM, 30 minutes walltime**
- Jobs run independently and in parallel
- Much faster total completion time

## Quick Start

```bash
# Submit parallel jobs for an experiment
./submit_convert_parallel.sh control
./submit_convert_parallel.sh exp1
./submit_convert_parallel.sh exp5

# Monitor jobs
qstat -u $USER

# Check logs
ls -lh /home5/ksuselj1/nobackup/OIF/logs/convert_*
```

## Files

### Main Scripts

1. **`submit_convert_parallel.sh`** - Master submission script
   - Takes experiment name as argument
   - Submits 8 separate PBS jobs (one per dataset)
   - Usage: `./submit_convert_parallel.sh <experiment>`

2. **`submit_convert_single.pbs`** - PBS script for single dataset
   - Processes ONE dataset at a time
   - Called by `submit_convert_parallel.sh`
   - 30-minute walltime per dataset

3. **`convert_to_netcdf.py`** - Python conversion script
   - Now supports `--skip-existing` flag
   - Can process specific datasets with `--datasets`

### Legacy Scripts

- **`submit_convert.pbs`** - Original monolithic script (still works)
- **`submit_convert_co2.pbs`** - CO2-only conversion (still works)

## Usage Examples

### Parallel Conversion (Recommended)

```bash
# Convert all datasets for control experiment in parallel
./submit_convert_parallel.sh control

# This submits 8 jobs:
#   - Job 1: pft_lim1
#   - Job 2: pft_lim2
#   - Job 3: pft_lim3
#   - Job 4: pft_lim4
#   - Job 5: pft_lim5
#   - Job 6: nutrients
#   - Job 7: co2
#   - Job 8: carbon_tracers
```

### Single Dataset Conversion

```bash
# Convert just one dataset manually
qsub -v EXP_NAME=control,DATASET=nutrients submit_convert_single.pbs
```

### Skip Existing Files

```bash
# Add --skip-existing flag in submit_convert_single.pbs if desired
python convert_to_netcdf.py /path/to/data --datasets nutrients --skip-existing
```

## Monitoring

### Check Job Status

```bash
# List your running jobs
qstat -u $USER

# Watch jobs in real-time
watch -n 5 'qstat -u $USER'
```

### Check Logs

```bash
# View logs (one per dataset per experiment)
ls -lh /home5/ksuselj1/nobackup/OIF/logs/convert_*.log

# View specific log
cat /home5/ksuselj1/nobackup/OIF/logs/convert_control_nutrients.log

# Check for errors
grep -i error /home5/ksuselj1/nobackup/OIF/logs/convert_*.log
```

### Check Output Files

```bash
# List generated NetCDF files
ls -lh /home5/ksuselj1/nobackup/OIF/ED_experiments/control/run/diags/monthly_netcdf/

# Should see:
#   pft_lim1.nc
#   pft_lim2.nc
#   pft_lim3.nc
#   pft_lim4.nc
#   pft_lim5.nc
#   nutrients.nc
#   co2.nc
#   carbon_tracers.nc
```

## Resource Usage

### Per-Dataset Job

- **CPUs**: 4
- **Memory**: 16 GB
- **Walltime**: 30 minutes
- **Queue**: normal
- **Node**: sky_ele

### Total Resources

When running all 8 datasets in parallel:
- **Total CPUs**: 32 (8 jobs × 4 CPUs)
- **Total Memory**: 128 GB (8 jobs × 16 GB)
- **Total Walltime**: ~30 minutes (all parallel)

Compare to monolithic approach:
- **Total CPUs**: 16 (1 job × 16 CPUs)
- **Total Memory**: 64 GB
- **Total Walltime**: 4+ hours (sequential)

## File Overwriting Behavior

### Default (No flag)

By default, `convert_to_netcdf.py` **OVERWRITES** existing files:

```bash
# This will REPLACE nutrients.nc if it exists
python convert_to_netcdf.py /path/to/data --datasets nutrients
```

### Skip Existing Files

Use `--skip-existing` to avoid reprocessing:

```bash
# This will SKIP conversion if nutrients.nc already exists
python convert_to_netcdf.py /path/to/data --datasets nutrients --skip-existing
```

To enable this in the PBS script, modify `submit_convert_single.pbs` line 54:

```bash
# Original (overwrites):
python "${SCRIPT}" "${DATA_DIR}" --k_max "${K_MAX}" --datasets "${DATASET}"

# With skip-existing:
python "${SCRIPT}" "${DATA_DIR}" --k_max "${K_MAX}" --datasets "${DATASET}" --skip-existing
```

## Troubleshooting

### Jobs Failing

1. Check the log files:
   ```bash
   tail -n 50 /home5/ksuselj1/nobackup/OIF/logs/convert_<exp>_<dataset>.log
   ```

2. Common issues:
   - Missing input files: Check that binary files exist in `monthly/` directory
   - Memory issues: Increase memory in `submit_convert_single.pbs` (line 10)
   - Walltime exceeded: Increase walltime (line 11)

### Incomplete Conversions

Check which datasets completed:

```bash
# List output files
ls -lh /home5/ksuselj1/nobackup/OIF/ED_experiments/control/run/diags/monthly_netcdf/*.nc

# If some are missing, resubmit just those datasets
qsub -v EXP_NAME=control,DATASET=pft_lim3 submit_convert_single.pbs
```

### Wrong Experiment

If you submitted jobs for the wrong experiment, delete them:

```bash
# List job IDs
qstat -u $USER

# Delete specific job
qdel <job_id>

# Delete all your jobs (use with caution!)
qselect -u $USER | xargs qdel
```

## Performance Tips

1. **Use parallel conversion** for large experiments (3+ hours of conversion time)
2. **Use monolithic** (`submit_convert.pbs`) for quick tests or small experiments
3. **Adjust resources** in `submit_convert_single.pbs` if needed:
   - More CPUs won't help (xmitgcm is mostly single-threaded)
   - More memory helps for large datasets
   - Adjust walltime if datasets are very large

## Dataset Descriptions

- **pft_lim1-5**: Phytoplankton functional type limitations and diagnostics (one per PFT)
- **nutrients**: FeT, NO3, PO4, SiO2 tracers
- **co2**: CO2 flux and pCO2 fields
- **carbon_tracers**: DIC, DOC, ALK tracers

## Advanced Usage

### Convert Specific Datasets Only

```bash
# Convert just nutrients and co2 for exp1
./submit_convert_parallel.sh exp1

# Then cancel the other jobs if needed
qstat -u $USER  # find job IDs
qdel <job_id>   # cancel unwanted jobs
```

### Different k_max

Edit `K_MAX` variable in `submit_convert_single.pbs` (line 18):

```bash
K_MAX=20  # Save 20 vertical levels instead of 10
```

### Submit to Different Queue

Edit `submit_convert_single.pbs` line 12:

```bash
#PBS -q devel      # For quick tests (2 hour limit)
#PBS -q normal     # Standard queue (default)
#PBS -q long       # For very long jobs (120 hour limit)
```
