import getdist.plots as gplot
from getdist import MCSamples
from getdist import loadMCSamples
import os
import numpy as np


# ---- SET LIMITS
omm_min = 0.24
omm_max = 0.40 
omb_min = 0.04 
omb_max = 0.06 
ns_min = 0.92 
ns_max = 1.00 
h_min = 0.61 
h_max = 0.73 
logA_min = 2.84
logA_max = 3.21
w_min = -1.3
w_max = -0.7
LSST_DZ_min = -0.008 # this is 4sigma of the normal distribution
LSST_DZ_max = 0.008
LSST_A1_1_min = -5
LSST_A1_1_max = +5
LSST_A1_2_min = -5
LSST_A1_2_max = +5

root_chains = ('projects/lsst_y1/chains/EXAMPLE_MCMC2',
    )

num_points_thin = 40000

analysissettings={'smooth_scale_1D':0.35,'smooth_scale_2D':0.35,'ignore_rows': u'0.5',
'range_confidence' : u'0.005'}


samples_list = []
logA = []
ns = []
H0 =[]
omegab =[]
omegam = []
omegam_growth = []
LSST_DZ_S1 = []
LSST_DZ_S2 = []
LSST_DZ_S3 = []
LSST_DZ_S4 = []
LSST_DZ_S5 = []
LSST_A1_1  = []
LSST_A1_2  = []


# --------read samples and write them for emulator training-----------
for i in range(len(root_chains)):
    samples=loadMCSamples('./' + root_chains[i],settings=analysissettings)
    samples.thin(factor = int(np.sum(samples.weights)/num_points_thin))
    p = samples.getParams()
    samples.deleteZeros()
    samples.ranges.setRange('logA', [logA_min, logA_max])
    samples.ranges.setRange('ns', [ns_min, ns_max])
    samples.ranges.setRange('omegam', [omm_min, omm_max])
    samples.ranges.setRange('H0', [100*h_min, 100*h_max])
    samples.ranges.setRange('LSST_DZ_S1', [LSST_DZ_min , LSST_DZ_max])
    samples.ranges.setRange('LSST_DZ_S2', [LSST_DZ_min , LSST_DZ_max])
    samples.ranges.setRange('LSST_DZ_S3', [LSST_DZ_min , LSST_DZ_max])
    samples.ranges.setRange('LSST_DZ_S4', [LSST_DZ_min , LSST_DZ_max])
    samples.ranges.setRange('LSST_DZ_S5', [LSST_DZ_min , LSST_DZ_max])
    samples.ranges.setRange('LSST_A1_1', [LSST_A1_1_min , LSST_A1_1_max])
    samples.ranges.setRange('LSST_A1_2', [LSST_A1_2_min , LSST_A1_2_max])
    
    logA = np.append(logA, p.logA)
    ns = np.append(ns, p.ns)
    H0 = np.append(H0, p.H0)
    omegab = np.append(omegab, p.omegab)
    omegam = np.append(omegam, p.omegam)
    LSST_DZ_S1 = np.append(LSST_DZ_S1, p.LSST_DZ_S1)
    LSST_DZ_S2 = np.append(LSST_DZ_S2, p.LSST_DZ_S2)
    LSST_DZ_S3 = np.append(LSST_DZ_S3, p.LSST_DZ_S3)
    LSST_DZ_S4 = np.append(LSST_DZ_S4, p.LSST_DZ_S4)
    LSST_DZ_S5 = np.append(LSST_DZ_S5, p.LSST_DZ_S5)
    LSST_A1_1  = np.append(LSST_A1_1, p.LSST_A1_1)
    LSST_A1_2  = np.append(LSST_A1_2, p.LSST_A1_2)


samples_list = np.transpose([logA, ns, H0, omegab, omegam, LSST_DZ_S1, LSST_DZ_S2, LSST_DZ_S3, LSST_DZ_S4, LSST_DZ_S5, LSST_A1_1, LSST_A1_2])

print("shape of samples plist is: ", np.shape(samples_list))




np.save('projects/lsst_y1/emulator_output/post/samples_from_posterior.npy', samples_list)






