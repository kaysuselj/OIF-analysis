#!/usr/bin/env python3
"""
Convert ECCO-Darwin MDS binary output to NetCDF.

Usage
-----
    # Convert all years, all datasets
    python convert_to_netcdf.py <data_dir> [--k_max 10]

    # Convert specific 5-year period (only reads those iterations)
    python convert_to_netcdf.py <data_dir> --start-year 1992 --end-year 1996

    # Convert specific datasets only
    python convert_to_netcdf.py <data_dir> --datasets co2 nutrients

    # Combine options
    python convert_to_netcdf.py <data_dir> --start-year 1992 --end-year 1996 \
        --datasets co2 --k_max 10 --skip-existing

Output
------
Creates <data_dir>_netcdf/ and writes one NetCDF file per dataset defined in
DATASETS below.  Variables with a k (depth) dimension are truncated to the
top k_max levels.  Surface-only variables (no k) are written in full.

When year range is specified, output files are named with suffix:
    co2_1992-1996.nc, nutrients_1992-1996.nc, etc.

Extending
---------
To add a new variable group, append one entry to DATASETS and, if the
variables are not in available_diagnostics.log, add a matching _extra_*
dict above it:

    'my_group': {
        'prefixes':        ['Prefix1', 'Prefix2'],  # MDS file prefixes
        'extra_variables': _extra_mygroup,           # {} if in available_diagnostics.log
        'output_file':     'my_group.nc',
        'rename':          {'OLD': 'NEW'},           # optional post-load rename
    },
"""

import argparse
import glob
import os
import re
import sys

import numpy as np
import xarray as xr
import xmitgcm

# ── Grid directory ────────────────────────────────────────────────────────────
GRID_DIR = '/home5/ksuselj1/nobackup/OIF/ED_experiments/model_setup'

# ── Extra-variable definitions ────────────────────────────────────────────────

# PFT limitation variables — one extra-variables dict per PFT
_pft_scalar_vars = {
    'fnut': ('Total Nutrient Limitation Factor',  '0-1'),
    'fIph': ('Light Limitation Factor',           '0-1'),
    'fTph': ('Temperature Limitation Factor',     '0-1'),
    'limN': ('Nitrogen Limitation Factor',        '0-1'),
    'limP': ('Phosphorus Limitation Factor',      '0-1'),
    'limS': ('Silica Limitation Factor',          '0-1'),
    'limF': ('Iron Limitation Factor',            '0-1'),
    'PC':   ('Net Primary Production',            'mmol C/m^3/s'),
    'Mort': ('Mortality Rate',                    'mmol C/m^3/s'),
    'Resp': ('Respiration Rate',                  'mmol C/m^3/s'),
}
_extra_pft = []
for _i in range(1, 6):
    _d = {
        f'TRAC{19 + _i}': {
            'dims':  ['k', 'j', 'i'],
            'attrs': {'long_name': f'PFT{_i} Phytoplankton Quota/Biomass',
                      'units': 'mmol C/m^3'},
        }
    }
    for _key, (_label, _unit) in _pft_scalar_vars.items():
        _d[f'{_key}{_i:04d}'] = {
            'dims':  ['k', 'j', 'i'],
            'attrs': {'long_name': f'PFT{_i} {_label}', 'units': _unit},
        }
    _extra_pft.append(_d)

# Nutrient tracer variables (3D)
_extra_nutrients = {
    'TRAC06': dict(dims=['k', 'j', 'i'],
                   attrs={'long_name': 'Total dissolved iron', 'units': 'mmol Fe m-3'}),
    'TRAC02': dict(dims=['k', 'j', 'i'],
                   attrs={'long_name': 'Nitrate',              'units': 'mmol N m-3'}),
    'TRAC05': dict(dims=['k', 'j', 'i'],
                   attrs={'long_name': 'Phosphate',            'units': 'mmol P m-3'}),
    'TRAC07': dict(dims=['k', 'j', 'i'],
                   attrs={'long_name': 'Silicate',             'units': 'mmol Si m-3'}),
}

# CO2 flux and pCO2 (2D surface fields — no k dimension)
# Variable names within the MDS files depend on the diagnostics configuration;
# adjust the keys below if xmitgcm reports unknown variables.
_extra_co2 = {
    'fluxCO2': dict(dims=['j', 'i'],
                    attrs={'long_name': 'Air-sea CO2 flux', 'units': 'mol C m-2 s-1'}),
    'pCO2':    dict(dims=['k', 'j', 'i'],
                    attrs={'long_name': 'Surface pCO2',     'units': 'uatm'}),
}

# Carbon tracer variables (3D)
_extra_carbon_tracers = {
    'TRAC01': dict(dims=['k', 'j', 'i'],
                   attrs={'long_name': 'Dissolved Inorganic Carbon', 'units': 'mmol C m-3'}),
    'TRAC08': dict(dims=['k', 'j', 'i'],
                   attrs={'long_name': 'Dissolved Organic Carbon',   'units': 'mmol C m-3'}),
    'TRAC18': dict(dims=['k', 'j', 'i'],
                   attrs={'long_name': 'Alkalinity',                 'units': 'meq m-3'}),
}

# Sea ice variables (2D surface fields — no k dimension)
# The MDS .meta fldList pads names to 8 chars ('SIarea  '), but xmitgcm strips the
# padding, so the variable arrives as 'SIarea' and needs no rename.
_extra_sea_ice = {
    'SIarea': dict(dims=['j', 'i'],
                   attrs={'long_name': 'Sea Ice Area Fraction', 'units': 'fraction'}),
}

# ── Dataset definitions ───────────────────────────────────────────────────────
# Each key → one NetCDF output file.
# To add a new group: append an entry here and define _extra_* above if needed.

DATASETS = {
    **{f'pft_lim{_i}': {
        'prefixes':        [f'PFT{_i}_lim'],
        'extra_variables': _extra_pft[_i - 1],
        'output_file':     f'pft_lim{_i}.nc',
        'rename':          {},
    } for _i in range(1, 6)},
    'nutrients': {
        'prefixes':        ['FeT', 'NO3', 'PO4', 'SiO2'],
        'extra_variables': _extra_nutrients,
        'output_file':     'nutrients.nc',
        'rename':          {'TRAC06': 'FeT', 'TRAC02': 'NO3',
                            'TRAC05': 'PO4', 'TRAC07': 'SiO2'},
    },
    'co2': {
        'prefixes':        ['CO2_flux', 'pCO2'],
        'extra_variables': _extra_co2,
        'output_file':     'co2.nc',
        'rename':          {'fluxCO2': 'CO2_flux'},
    },
    'carbon_tracers': {
        'prefixes':        ['DIC', 'DOC', 'ALK'],
        'extra_variables': _extra_carbon_tracers,
        'output_file':     'carbon_tracers.nc',
        'rename':          {'TRAC01': 'DIC', 'TRAC08': 'DOC', 'TRAC18': 'ALK'},
    },
    'sea_ice': {
        'prefixes':        ['SIarea'],
        'extra_variables': _extra_sea_ice,
        'output_file':     'sea_ice.nc',
        'rename':          {},
    },
    # ── Add new groups below ──────────────────────────────────────────────────
    # 'example': {
    #     'prefixes':        ['MyPrefix'],
    #     'extra_variables': {},
    #     'output_file':     'example.nc',
    #     'rename':          {},
    # },
}

# ── NetCDF encoding ───────────────────────────────────────────────────────────
_ENCODING_DEFAULTS = dict(zlib=True, complevel=4)


def _build_encoding(ds):
    return {v: _ENCODING_DEFAULTS for v in ds.data_vars}


def _truncate_k(ds, k_max):
    """Slice the top k_max levels on every depth-like dimension present."""
    for dim in ('k', 'k_l', 'k_u', 'k_p1'):
        if dim in ds.dims and k_max < len(ds[dim]):
            ds = ds.isel({dim: slice(0, k_max)})
    return ds


def _add_time_coordinate(ds, start_date='1992-01-01', delta_t=3600):
    """
    Replace iteration-based time coordinate with proper datetime values.

    Parameters:
    -----------
    ds : xr.Dataset
        Dataset with 'time' dimension (iteration numbers from xmitgcm)
    start_date : str
        Start date for iter=2 in 'YYYY-MM-DD' format (default: '1992-01-01')
    delta_t : float
        Time step in seconds (default: 3600 = 1 hour)

    Returns:
    --------
    xr.Dataset : Dataset with proper datetime coordinate
    """
    if 'time' not in ds.dims:
        return ds

    # Get iteration numbers from the time coordinate
    # xmitgcm loads these as the 'time' coordinate values
    iterations = ds.time.values

    # Reference: iter 2 corresponds to start_date
    # Each iteration is delta_t seconds apart
    reference_iter = 2

    # Compute datetime for each iteration
    # seconds from reference = (iter - reference_iter) * delta_t
    start_datetime = np.datetime64(start_date)

    # Create datetime array
    datetime_values = []
    for iter_num in iterations:
        seconds_from_start = (iter_num - reference_iter) * delta_t
        dt = start_datetime + np.timedelta64(int(seconds_from_start), 's')
        datetime_values.append(dt)

    datetime_values = np.array(datetime_values, dtype='datetime64[ns]')

    # Replace time coordinate
    ds['time'] = datetime_values
    ds.time.attrs['long_name'] = 'time'
    ds.time.attrs['standard_name'] = 'time'
    # NB: do not set a 'calendar' attribute here -- for datetime64 values xarray
    # manages calendar/units as encoding on write; a 'calendar' key in .attrs makes
    # to_netcdf raise "Key 'calendar' already exists in attrs on variable 'time'".

    return ds


def _calculate_iteration_range(start_year, end_year, start_date='1992-01-01', delta_t=3600):
    """
    Calculate iteration range for a given year range.

    Parameters:
    -----------
    start_year : int
        Start year (inclusive)
    end_year : int
        End year (inclusive)
    start_date : str
        Reference start date for iter=2 (default: '1992-01-01')
    delta_t : float
        Time step in seconds (default: 3600 = 1 hour)

    Returns:
    --------
    tuple : (start_iter, end_iter)
    """
    reference_iter = 2
    reference_date = np.datetime64(start_date)

    # Calculate start iteration (beginning of start_year)
    target_start = np.datetime64(f'{start_year}-01-01')
    seconds_to_start = (target_start - reference_date) / np.timedelta64(1, 's')
    start_iter = int(reference_iter + seconds_to_start / delta_t)

    # Calculate end iteration (end of end_year)
    target_end = np.datetime64(f'{end_year + 1}-01-01')  # exclusive end
    seconds_to_end = (target_end - reference_date) / np.timedelta64(1, 's')
    end_iter = int(reference_iter + seconds_to_end / delta_t)

    return start_iter, end_iter


def _available_iters(data_dir, prefixes, start_iter, end_iter):
    """Iterations that actually exist on disk for ALL given prefixes, restricted to
    [start_iter, end_iter]. MDS output is only written at specific (monthly)
    iterations, so we must select the real ones rather than every integer in the
    range -- xmitgcm errors if asked for an iteration with no file."""
    per_prefix = []
    for p in prefixes:
        found = set()
        pat = re.compile(rf'^{re.escape(p)}\.(\d+)\.data$')
        for f in glob.glob(os.path.join(data_dir, f'{p}.*.data')):
            m = pat.match(os.path.basename(f))
            if m:
                found.add(int(m.group(1)))
        per_prefix.append(found)
    if not per_prefix:
        return []
    common = set.intersection(*per_prefix) if len(per_prefix) > 1 else per_prefix[0]
    return sorted(i for i in common if start_iter <= i <= end_iter)


def _expected_iters(data_dir, prefixes, start_year=None, end_year=None):
    """Iterations the MDS binaries actually hold for this dataset/window."""
    if start_year is not None and end_year is not None:
        start_iter, end_iter = _calculate_iteration_range(start_year, end_year)
    else:
        start_iter, end_iter = -1, 10 ** 18
    return _available_iters(data_dir, prefixes, start_iter, end_iter)


def _validate_output(out_path, n_expected):
    """
    Decide whether an existing NetCDF file is complete and usable.

    A file counts as done only if it opens, its time axis decodes, and it holds
    exactly as many timesteps as there are MDS files on disk.  A job killed
    mid-write leaves a readable HDF5 skeleton whose time axis is all fill-value,
    so an existence check alone is not enough to trust it.

    Returns (ok, reason).
    """
    if not os.path.exists(out_path):
        return False, 'not present'
    try:
        with xr.open_dataset(out_path) as ds:
            if 'time' not in ds.dims:
                return False, 'no time dimension'
            n_found = len(ds.time)
            if np.isnat(np.asarray(ds.time.values)).any():
                return False, 'time axis has NaT (truncated write)'
    except Exception as exc:
        return False, f'unreadable ({type(exc).__name__})'

    if n_found != n_expected:
        return False, f'{n_found} timesteps on file, {n_expected} in MDS binaries'
    return True, f'complete ({n_found} timesteps)'


def _materialize(ds, max_inmem_gb=32.0):
    """
    Pull the dataset into memory before writing.

    Writing straight from xmitgcm's dask arrays is pathologically slow: their
    chunks are (1 time, 1 k, 1 face, 90, 90) = 32 kB, and every one of those tiny
    blocks triggers a separate compressed HDF5 read-modify-write.  Loading first
    turns the write into a few large sequential ones (measured ~167 s vs >8 min
    for one 60-month pft_lim chunk).  Fall back to time-wise chunks if the
    dataset is too big to hold in RAM.
    """
    nbytes = sum(v.nbytes for v in ds.data_vars.values())
    if nbytes <= max_inmem_gb * 1e9:
        print(f'  Loading   : {nbytes / 1e9:.2f} GB into memory')
        return ds.load()
    print(f'  Streaming : {nbytes / 1e9:.2f} GB exceeds {max_inmem_gb:.0f} GB; '
          f'rechunking by time')
    return ds.chunk({'time': 1})


def convert_dataset(name, cfg, data_dir, out_dir, k_max, skip_existing=False,
                    start_year=None, end_year=None):
    """
    Convert a single dataset from MDS binary to NetCDF.

    Parameters:
    -----------
    start_year : int, optional
        If specified, only read data from this year onwards
    end_year : int, optional
        If specified, only read data up to and including this year

    Returns:
    --------
    bool : True if successful, False if skipped or failed
    """
    print(f'[{name}]')
    print(f'  Prefixes  : {cfg["prefixes"]}')

    # Iterations the binaries hold for this window (drives both the read and the
    # completeness check on any pre-existing output).
    avail = _expected_iters(data_dir, cfg['prefixes'], start_year, end_year)

    iters = None
    year_suffix = ''
    if start_year is not None and end_year is not None:
        start_iter, end_iter = _calculate_iteration_range(start_year, end_year)
        iters = avail
        year_suffix = f'_{start_year}-{end_year}'
        print(f'  Year range: {start_year}-{end_year}')
        print(f'  Iterations: window {start_iter} to {end_iter}; '
              f'{len(iters)} monthly file(s) present on disk')
        if not iters:
            print(f'  No data    : no files for {name} in {start_year}-{end_year}; '
                  f'skipping this period\n')
            return True

    # Build output filename with year range suffix if specified
    base_name = cfg['output_file'].replace('.nc', '')
    out_filename = f'{base_name}{year_suffix}.nc'
    out_path = os.path.join(out_dir, out_filename)
    tmp_path = f'{out_path}.tmp'

    # Reuse an existing output only if it is readable AND complete.
    if skip_existing:
        ok, reason = _validate_output(out_path, len(avail))
        if ok:
            print(f'  Skipping  : {reason}\n')
            return True
        if os.path.exists(out_path):
            print(f'  Redoing   : existing file rejected — {reason}')
            os.remove(out_path)

    # A previous kill can leave a partial .tmp behind; it is never reusable.
    if os.path.exists(tmp_path):
        print(f'  Cleaning  : removing stale {os.path.basename(tmp_path)}')
        os.remove(tmp_path)

    try:
        # Open dataset - only read specified iterations if provided
        ds = xmitgcm.open_mdsdataset(
            data_dir=data_dir,
            grid_dir=GRID_DIR,
            geometry='llc',
            prefix=cfg['prefixes'],
            iters=iters,
            extra_variables=cfg.get('extra_variables', {}),
            ignore_unknown_vars=True,
        )
    except (FileNotFoundError, ValueError, OSError) as e:
        print(f'  ERROR     : No data files found for these prefixes/iterations')
        print(f'              {str(e)}')
        print(f'  Skipping  : {name}\n')
        return False

    # Check if dataset is empty
    if 'time' in ds.dims and len(ds.time) == 0:
        print(f'  WARNING   : Dataset is empty (no time steps found)')
        print(f'  Skipping  : {name}\n')
        ds.close()
        return False

    try:
        if cfg.get('rename'):
            ds = ds.rename(cfg['rename'])

        # Drop unwanted levels while the arrays are still lazy, so the deep data
        # is never read off disk.
        k_size = len(ds['k']) if 'k' in ds.dims else 0
        if k_size and k_max < k_size:
            print(f'  k levels  : {k_size} → keeping top {k_max}')
            ds = _truncate_k(ds, k_max)
        elif k_size:
            print(f'  k levels  : {k_size} (all kept, k_max={k_max})')
        else:
            print(f'  k levels  : none (surface field)')

        # Add proper time coordinate (convert from iteration numbers to datetime)
        if 'time' in ds.dims:
            n_times_before = len(ds.time)
            print(f'  Time steps: {n_times_before} (converting iterations to datetime)')
            ds = _add_time_coordinate(ds, start_date='1992-01-01', delta_t=3600)
            print(f'  Time range: {ds.time.values[0]} to {ds.time.values[-1]}')

        ds = _materialize(ds)

        # Write to a temp name and rename only on success, so a walltime kill can
        # never leave a half-written file that later looks "already done".
        print(f'  Writing   : {out_filename}')
        ds.to_netcdf(tmp_path, encoding=_build_encoding(ds))
        ds.close()
        os.replace(tmp_path, out_path)
        print(f'  Done.\n')
        return True

    except Exception as e:
        print(f'  ERROR     : Failed to process dataset')
        print(f'              {str(e)}')
        print(f'  Skipping  : {name}\n')
        if 'ds' in locals():
            ds.close()
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Convert ECCO-Darwin MDS binary output to NetCDF.',
        epilog='Example: python convert_to_netcdf.py exp1/run --start-year 1992 --end-year 1996')
    parser.add_argument(
        'data_dir',
        help='Directory containing ECCO-Darwin binary files')
    parser.add_argument(
        '--k_max', type=int, default=10,
        help='Number of vertical levels to save for 3D variables (default: 10)')
    parser.add_argument(
        '--datasets', nargs='*', default=None,
        metavar='NAME',
        help=f'Subset of dataset names to convert (default: all). '
             f'Available: {list(DATASETS)}')
    parser.add_argument(
        '--skip-existing', action='store_true',
        help='Skip conversion if output file already exists')
    parser.add_argument(
        '--start-year', type=int, default=None,
        help='Start year to extract (inclusive). Only reads iterations for this year range.')
    parser.add_argument(
        '--end-year', type=int, default=None,
        help='End year to extract (inclusive). Must be used with --start-year.')
    args = parser.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    if not os.path.isdir(data_dir):
        sys.exit(f'ERROR: {data_dir} does not exist.')

    # Validate year range arguments
    if (args.start_year is None) != (args.end_year is None):
        sys.exit('ERROR: --start-year and --end-year must be used together.')
    if args.start_year is not None and args.end_year is not None:
        if args.start_year > args.end_year:
            sys.exit(f'ERROR: start_year ({args.start_year}) must be <= end_year ({args.end_year}).')

    out_dir = data_dir + '_netcdf'
    os.makedirs(out_dir, exist_ok=True)

    to_run = args.datasets if args.datasets else list(DATASETS)
    unknown = set(to_run) - set(DATASETS)
    if unknown:
        sys.exit(f'ERROR: unknown dataset(s): {unknown}. '
                 f'Available: {list(DATASETS)}')

    print(f'Data dir  : {data_dir}')
    print(f'Output dir: {out_dir}')
    print(f'k_max     : {args.k_max}')
    print(f'Datasets  : {to_run}')
    print(f'Skip exist: {args.skip_existing}')
    if args.start_year is not None:
        print(f'Year range: {args.start_year}-{args.end_year}')
    print()

    # Track results
    success_count = 0
    skip_count = 0
    fail_count = 0

    for name in to_run:
        result = convert_dataset(name, DATASETS[name], data_dir, out_dir, args.k_max,
                                skip_existing=args.skip_existing,
                                start_year=args.start_year,
                                end_year=args.end_year)
        if result:
            success_count += 1
        else:
            fail_count += 1

    # Print summary
    print('=' * 60)
    print('SUMMARY')
    print('=' * 60)
    print(f'Total datasets  : {len(to_run)}')
    print(f'Successful      : {success_count}')
    print(f'Failed/Skipped  : {fail_count}')
    print('=' * 60)

    if fail_count > 0:
        print(f'\nWARNING: {fail_count} dataset(s) failed or had no data.')
        print('Check messages above for details.')
        sys.exit(1)

    print('\nAll done.')


if __name__ == '__main__':
    main()
