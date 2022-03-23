#!/usr/bin/env python3
# Example script to create fiducial values for mock CMB likelihoods
from cobaya.model import get_model
import numpy as np

# from best fit with fixed massless neutrinos and nuisance-marginalized high-l

#EDE-Planck best fit, get from 2003.07355v3 TABEL 2, from Planck only
fiducial_params = {
    # LambdaCDM parameters
    'H0': 69.13,
    # '100*theta_s': 1.041920539e+00,
    'omegabh2': 0.02250,
    'omegach2': 0.1268,
    'As': np.exp(3.056)*1e-10,
    #'logA': 3.048, 
    #'sigma8':0.813,
    'ns': 0.9769,
    'tau': 0.0539,
    'fde_zc': 0.068,
    'zc': 10**(2.96) 
}

fiducial_params_extra = {
    'AccuracyBoost': 3,
    'dark_energy_model': 'EarlyDarkEnergy',
    'which_potential': 2,
    'n': 3,
    'use_zc': True,
    'nnu': 3.046,  # three massless neutrinos
    'halofit_version': 'mead'
}

fiducial_params_full = fiducial_params.copy()
fiducial_params_full.update(fiducial_params_extra)

info_fiducial = {
    'params': fiducial_params,
    'likelihood': {'cobaya_mock_cmb.MockSO': {'python_path': '.'},
                   'cobaya_mock_cmb.MockSOBaseline': {'python_path': '.'},
                   'cobaya_mock_cmb.MockSOGoal': {'python_path': '.'},
                   'cobaya_mock_cmb.MockCMBS4': {'python_path': '.'},
                   'cobaya_mock_cmb.MockCMBS4sens0': {'python_path': '.'},
                   'cobaya_mock_cmb.MockPlanck': {'python_path': '.'}},
    'theory': {'camb':
                 {
                 "path": "/gpfs/projects/MirandaGroup/kunhao/cocoa_sbu_2/Cocoa/external_modules/code/CAMB-EDE",
                 "extra_args": fiducial_params_extra
                 }
              }}

model_fiducial = get_model(info_fiducial)

model_fiducial.logposterior({})

Cls = model_fiducial.provider.get_Cl(units="muK2")

for likelihood in model_fiducial.likelihood.values():
    likelihood.create_fid_values(Cls, fiducial_params_full, override=True)
