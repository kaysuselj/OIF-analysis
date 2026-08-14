#!/usr/bin/env python3
"""
Create analysis-ready NetCDF subsets for OIF efficiency analysis.

This script adds dataset definitions for ALL diagnostics needed for the
complete efficiency decomposition analysis:
  - η_upt = C_fixed / Fe_added
  - η_exp = C_exported / C_fixed
  - η_dur = C_seq / C_exported
  - η_as = CO2_atm / C_seq

Plus community composition metrics (opal:POC), Fe budget, and ballast correction.

Usage
-----
Add this to your existing convert_to_netcdf.py DATASETS dict, or run standalone:

    python data_subset_for_analysis.py <data_dir> --k_max 30 \
        --start-year 1992 --end-year 2001 --datasets efficiency_core

Output
------
Creates NetCDF files optimized for laptop analysis:
  - efficiency_core.nc: All core efficiency diagnostics (PP, fluxCO2, DIC, POC, POSi, etc.)
  - fe_budget.nc: Iron budget diagnostics (C_Fe, S_Fe, sedFe, etc.)
  - pft_biomass.nc: PFT biomass (c01-c05) for community composition
  - physical.nc: MXLDEPTH, THETA (from baseline only, copy to all experiments)

File sizes (10 years, k_max=30, LLC90):
  - efficiency_core.nc: ~40-50 GB (most important)
  - fe_budget.nc: ~20-25 GB
  - pft_biomass.nc: ~15-20 GB
  - physical.nc: ~6-8 GB (baseline only)

Total: ~80-100 GB per experiment (vs ~300-400 GB for full depth k_max=50)

Note: k_max=30 covers 0-1100m including mesopelagic (100-1000m) needed for O2 analysis
"""

# ══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL DATASET DEFINITIONS FOR EFFICIENCY ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

# ── Core Efficiency Diagnostics ──────────────────────────────────────────────
# Everything needed for η_upt, η_exp, η_dur, η_as, plus opal:POC ratio

_extra_efficiency_core = {
    # DIC (for C_seq)
    'TRAC01': {
        'dims': ['k', 'j', 'i'],
        'attrs': {'long_name': 'Dissolved Inorganic Carbon', 'units': 'mmol C m-3'}
    },
    # POC (for C_exported)
    'TRAC12': {
        'dims': ['k', 'j', 'i'],
        'attrs': {'long_name': 'Particulate Organic Carbon', 'units': 'mmol C m-3'}
    },
    # POSi / opal (for opal:POC ratio, ballast correction)
    'TRAC16': {
        'dims': ['k', 'j', 'i'],
        'attrs': {'long_name': 'Particulate Organic Silica (opal)', 'units': 'mmol Si m-3'}
    },
    # POFe (for Fe export)
    'TRAC15': {
        'dims': ['k', 'j', 'i'],
        'attrs': {'long_name': 'Particulate Organic Iron', 'units': 'mmol Fe m-3'}
    },
    # PIC / calcite (for ballast correction, optional)
    'TRAC17': {
        'dims': ['k', 'j', 'i'],
        'attrs': {'long_name': 'Particulate Inorganic Carbon (calcite)', 'units': 'mmol C m-3'}
    },
    # Nutrients (for macronutrient ceiling)
    'TRAC02': {
        'dims': ['k', 'j', 'i'],
        'attrs': {'long_name': 'Nitrate', 'units': 'mmol N m-3'}
    },
    'TRAC05': {
        'dims': ['k', 'j', 'i'],
        'attrs': {'long_name': 'Phosphate', 'units': 'mmol P m-3'}
    },
    'TRAC06': {
        'dims': ['k', 'j', 'i'],
        'attrs': {'long_name': 'Total dissolved iron', 'units': 'mmol Fe m-3'}
    },
    'TRAC07': {
        'dims': ['k', 'j', 'i'],
        'attrs': {'long_name': 'Silicate', 'units': 'mmol Si m-3'}
    },
    # DOC (for budget closure)
    'TRAC08': {
        'dims': ['k', 'j', 'i'],
        'attrs': {'long_name': 'Dissolved Organic Carbon', 'units': 'mmol C m-3'}
    },
}

DATASETS_EFFICIENCY = {
    'efficiency_core': {
        'prefixes': [
            'primProd',      # PP - total NPP
            'CO2_flux',      # fluxCO2 - air-sea CO2 flux
            'pCO2',          # pCO2 - surface ocean pCO2
            'DIC',           # TRAC01 - DIC
            'POC',           # TRAC12 - POC
            'POSi',          # TRAC16 - opal
            'POFe',          # TRAC15 - POFe
            'PIC',           # TRAC17 - calcite
            'FeT',           # TRAC06 - dissolved Fe
            'NO3',           # TRAC02 - nitrate
            'PO4',           # TRAC05 - phosphate
            'SiO2',          # TRAC07 - silicate
            'DOC',           # TRAC08 - DOC
        ],
        'extra_variables': _extra_efficiency_core,
        'output_file': 'efficiency_core.nc',
        'rename': {
            'TRAC01': 'DIC',
            'TRAC02': 'NO3',
            'TRAC05': 'PO4',
            'TRAC06': 'FeT',
            'TRAC07': 'SiO2',
            'TRAC08': 'DOC',
            'TRAC12': 'POC',
            'TRAC15': 'POFe',
            'TRAC16': 'POSi',
            'TRAC17': 'PIC',
            'fluxCO2': 'CO2_flux',
            'PP': 'NPP',
        },
    },

    # ── Fe Budget Diagnostics ─────────────────────────────────────────────────
    'fe_budget': {
        'prefixes': [
            'average_Fe_3d',         # Contains: C_Fe, S_Fe, sedFe, freeFeLs
            'average_Fe_darwin_2d',  # Contains: sfcSolFe (dust input)
        ],
        'extra_variables': {},  # These are in available_diagnostics.log
        'output_file': 'fe_budget.nc',
        'rename': {},
    },

    # ── PFT Biomass (Community Composition) ───────────────────────────────────
    'pft_biomass': {
        'prefixes': [
            'c1',    # TRAC20 - c01 (diatom)
            'c2',    # TRAC21 - c02
            'c3',    # TRAC22 - c03 (small phyto)
            'c4',    # TRAC23 - c04
            'c5',    # TRAC24 - c05
            'Chl1',  # TRAC27 - chlorophyll (optional, for diagnostics)
            'Chl2',  # TRAC28
            'Chl3',  # TRAC29
            'Chl4',  # TRAC30
            'Chl5',  # TRAC31
        ],
        'extra_variables': {
            'TRAC20': {'dims': ['k','j','i'], 'attrs': {'long_name': 'PFT1 (diatom) biomass', 'units': 'mmol C m-3'}},
            'TRAC21': {'dims': ['k','j','i'], 'attrs': {'long_name': 'PFT2 biomass', 'units': 'mmol C m-3'}},
            'TRAC22': {'dims': ['k','j','i'], 'attrs': {'long_name': 'PFT3 (small phyto) biomass', 'units': 'mmol C m-3'}},
            'TRAC23': {'dims': ['k','j','i'], 'attrs': {'long_name': 'PFT4 biomass', 'units': 'mmol C m-3'}},
            'TRAC24': {'dims': ['k','j','i'], 'attrs': {'long_name': 'PFT5 biomass', 'units': 'mmol C m-3'}},
            'TRAC27': {'dims': ['k','j','i'], 'attrs': {'long_name': 'PFT1 chlorophyll', 'units': 'mg Chl m-3'}},
            'TRAC28': {'dims': ['k','j','i'], 'attrs': {'long_name': 'PFT2 chlorophyll', 'units': 'mg Chl m-3'}},
            'TRAC29': {'dims': ['k','j','i'], 'attrs': {'long_name': 'PFT3 chlorophyll', 'units': 'mg Chl m-3'}},
            'TRAC30': {'dims': ['k','j','i'], 'attrs': {'long_name': 'PFT4 chlorophyll', 'units': 'mg Chl m-3'}},
            'TRAC31': {'dims': ['k','j','i'], 'attrs': {'long_name': 'PFT5 chlorophyll', 'units': 'mg Chl m-3'}},
        },
        'output_file': 'pft_biomass.nc',
        'rename': {
            'TRAC20': 'c01',
            'TRAC21': 'c02',
            'TRAC22': 'c03',
            'TRAC23': 'c04',
            'TRAC24': 'c05',
            'TRAC27': 'Chl01',
            'TRAC28': 'Chl02',
            'TRAC29': 'Chl03',
            'TRAC30': 'Chl04',
            'TRAC31': 'Chl05',
        },
    },

    # ── Physical Fields (baseline only - copy to all experiments) ────────────
    'physical': {
        'prefixes': [
            'mldDepth',   # MXLDEPTH - mixed layer depth (CRITICAL for C_seq)
            'THETA',      # Temperature (for physical context)
        ],
        'extra_variables': {},
        'output_file': 'physical.nc',
        'rename': {},
    },

    # ── DIC Budget (for closure validation) ──────────────────────────────────
    'dic_budget': {
        'prefixes': [
            'average_DIC_3d',   # Contains: C_DIC, respDIC, rDIC_DOC, rDIC_POC, etc.
        ],
        'extra_variables': {},
        'output_file': 'dic_budget.nc',
        'rename': {},
    },

    # ── Tendency Terms (for NPP reconstruction if needed) ────────────────────
    'tendencies': {
        'prefixes': [
            # These are output from your budget diagnostics configuration
            # Can use to reconstruct per-PFT NPP if needed (but opal:POC is better)
        ],
        'extra_variables': {
            'gDAR20': {'dims': ['k','j','i'], 'attrs': {'long_name': 'c01 tendency from Darwin', 'units': 'mmol C m-3 s-1'}},
            'gDAR21': {'dims': ['k','j','i'], 'attrs': {'long_name': 'c02 tendency from Darwin', 'units': 'mmol C m-3 s-1'}},
            'gDAR22': {'dims': ['k','j','i'], 'attrs': {'long_name': 'c03 tendency from Darwin', 'units': 'mmol C m-3 s-1'}},
            'gDAR23': {'dims': ['k','j','i'], 'attrs': {'long_name': 'c04 tendency from Darwin', 'units': 'mmol C m-3 s-1'}},
            'gDAR24': {'dims': ['k','j','i'], 'attrs': {'long_name': 'c05 tendency from Darwin', 'units': 'mmol C m-3 s-1'}},
        },
        'output_file': 'tendencies.nc',
        'rename': {},
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# INSTRUCTIONS FOR ADDING TO convert_to_netcdf.py
# ══════════════════════════════════════════════════════════════════════════════

INSTRUCTIONS = """
To add these datasets to your existing convert_to_netcdf.py:

1. Copy the _extra_efficiency_core and DATASETS_EFFICIENCY definitions above

2. In convert_to_netcdf.py, add to the DATASETS dict (around line 127):

   DATASETS = {
       **{f'pft_lim{_i}': ...},  # existing
       'nutrients': {...},        # existing
       'co2': {...},              # existing
       'carbon_tracers': {...},   # existing
       'sea_ice': {...},          # existing

       # ── ADD THESE: ───────────────────────────────────────────────────
       **DATASETS_EFFICIENCY,  # Add all efficiency datasets at once
       # ─────────────────────────────────────────────────────────────────
   }

3. Or merge individually if you want to customize:

   DATASETS = {
       ...
       'efficiency_core': DATASETS_EFFICIENCY['efficiency_core'],
       'fe_budget': DATASETS_EFFICIENCY['fe_budget'],
       # etc.
   }

4. Run the conversion on Pleiades:

   # For ALL efficiency datasets:
   python convert_to_netcdf.py <data_dir> --k_max 30 \\
       --datasets efficiency_core fe_budget pft_biomass physical

   # Or one at a time:
   qsub -v EXP_NAME=baseline,DATASET=efficiency_core submit_convert_experiment.pbs
   qsub -v EXP_NAME=baseline,DATASET=physical submit_convert_experiment.pbs
   qsub -v EXP_NAME=exp1,DATASET=efficiency_core submit_convert_experiment.pbs
   qsub -v EXP_NAME=exp1,DATASET=fe_budget submit_convert_experiment.pbs

5. Copy to laptop:

   # On Pleiades:
   cd /home5/ksuselj1/nobackup/OIF/ED_experiments/baseline/run/diags/monthly_netcdf
   tar -czf efficiency_data_baseline.tar.gz efficiency_core.nc pft_biomass.nc physical.nc

   # On laptop:
   scp pleiades:/path/to/efficiency_data_baseline.tar.gz ~/Desktop/Projects/OIF/data/
   cd ~/Desktop/Projects/OIF/data/
   tar -xzf efficiency_data_baseline.tar.gz

6. File sizes (10 years, k_max=30):
   - efficiency_core.nc: ~40-50 GB (MUST HAVE)
   - fe_budget.nc: ~20-25 GB (optional, for Fe recycling analysis)
   - pft_biomass.nc: ~15-20 GB (optional, biomass fractions)
   - physical.nc: ~6-8 GB (baseline only, copy to all experiments)

7. Storage optimization:
   - Default k_max=30 (top 30 layers = 0-1100m, includes mesopelagic for O2 analysis)
   - Compress: tar -czf saves ~30-50% space
   - Only copy efficiency_core.nc if storage is tight (~50 GB per experiment)
   - For surface-only analysis (no O2), can use --k_max 10 (~20 GB per experiment)

8. For physical fields (MXLDEPTH, THETA):
   - Run ONCE on baseline: --datasets physical
   - Copy the same physical.nc to all experiment directories
   - No need to regenerate for perturbed runs (doesn't change with Fe addition)
"""

if __name__ == '__main__':
    print(__doc__)
    print(INSTRUCTIONS)
    print("\n" + "="*80)
    print("DATASETS_EFFICIENCY definitions copied to clipboard-ready format:")
    print("="*80)

    # Print ready-to-copy code
    import pprint
    print("\n# Paste this into convert_to_netcdf.py:\n")
    print("_extra_efficiency_core = ")
    pprint.pprint(_extra_efficiency_core, width=100)
    print("\nDATASETS_EFFICIENCY = ")
    pprint.pprint(DATASETS_EFFICIENCY, width=100)
