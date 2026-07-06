#!/usr/bin/env python3
"""
Convert ECCO-Darwin MDS binary output to NetCDF.

Usage
-----
    python convert_to_netcdf.py <data_dir> [--k_max 10] [--datasets pft_lim1 pft_lim2 nutrients]

Output
------
Creates <data_dir>_netcdf/ and writes one NetCDF file per dataset defined in
DATASETS below.  Variables with a k (depth) dimension are truncated to the
top k_max levels.  Surface-only variables (no k) are written in full.

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
import os
import sys

import numpy as np
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
    ds.time.attrs['calendar'] = 'gregorian'

    return ds


def convert_dataset(name, cfg, data_dir, out_dir, k_max, skip_existing=False):
    out_path = os.path.join(out_dir, cfg['output_file'])

    print(f'[{name}]')
    print(f'  Prefixes  : {cfg["prefixes"]}')
    print(f'  Output    : {out_path}')

    # Check if output file already exists
    if skip_existing and os.path.exists(out_path):
        print(f'  Skipping  : File already exists\n')
        return

    ds = xmitgcm.open_mdsdataset(
        data_dir=data_dir,
        grid_dir=GRID_DIR,
        geometry='llc',
        prefix=cfg['prefixes'],
        extra_variables=cfg.get('extra_variables', {}),
        ignore_unknown_vars=True,
    )

    if cfg.get('rename'):
        ds = ds.rename(cfg['rename'])

    # Add proper time coordinate (convert from iteration numbers to datetime)
    if 'time' in ds.dims:
        n_times_before = len(ds.time)
        print(f'  Time steps: {n_times_before} (converting iterations to datetime)')
        ds = _add_time_coordinate(ds, start_date='1992-01-01', delta_t=3600)
        print(f'  Time range: {ds.time.values[0]} to {ds.time.values[-1]}')

    k_size = len(ds['k']) if 'k' in ds.dims else 0
    if k_size and k_max < k_size:
        print(f'  k levels  : {k_size} → keeping top {k_max}')
        ds = _truncate_k(ds, k_max)
    elif k_size:
        print(f'  k levels  : {k_size} (all kept, k_max={k_max})')
    else:
        print(f'  k levels  : none (surface field)')

    print(f'  Writing ...')
    ds.to_netcdf(out_path, encoding=_build_encoding(ds))
    ds.close()
    print(f'  Done.\n')


def main():
    parser = argparse.ArgumentParser(
        description='Convert ECCO-Darwin MDS binary output to NetCDF.')
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
    args = parser.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    if not os.path.isdir(data_dir):
        sys.exit(f'ERROR: {data_dir} does not exist.')

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
    print()

    for name in to_run:
        convert_dataset(name, DATASETS[name], data_dir, out_dir, args.k_max,
                       skip_existing=args.skip_existing)

    print('All done.')


if __name__ == '__main__':
    main()
