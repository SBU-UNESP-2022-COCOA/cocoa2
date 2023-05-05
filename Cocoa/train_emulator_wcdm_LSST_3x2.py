import sys,os
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(".."))

from cocoa_emu import Config
from cocoa_emu import NNEmulator

debug=False

configfile =  "./projects/lsst_y1/train_emulator_wcdm_3x2.yaml"
config = Config(configfile)
nn_model = "Transformer"
#nn_model = "resnet"

# # Training set 2000k
# file1                = "./projects/lsst_y1/emulator_output_3x2_wcdm/lhs/dvs_for_training_2000k/train_1"
# file2                = "./projects/lsst_y1/emulator_output_3x2_wcdm/lhs/dvs_for_training_2000k/train_2"
# file3                = "./projects/lsst_y1/emulator_output_3x2_wcdm/lhs/dvs_for_training_2000k/train_3"
# file4                = "./projects/lsst_y1/emulator_output_3x2_wcdm/lhs/dvs_for_training_2000k/train_4"
# train_samples        = np.load(file1+'_samples.npy')#.append(np.load(file+'_samples_0.npy'))
# train_data_vectors   = np.load(file1+'_data_vectors.npy')#.append(np.load(file+'_data_vectors_0.npy'))
# train_samples_2      = np.load(file2+'_samples.npy')#.append(np.load(file+'_samples_0.npy'))
# train_data_vectors_2 = np.load(file2+'_data_vectors.npy')#.append(np.load(file+'_data_vectors_0.npy'))
# train_samples_3      = np.load(file3+'_samples.npy')#.append(np.load(file+'_samples_0.npy'))
# train_data_vectors_3 = np.load(file3+'_data_vectors.npy')#.append(np.load(file+'_data_vectors_0.npy'))
# train_samples_4      = np.load(file4+'_samples.npy')#.append(np.load(file+'_samples_0.npy'))
# train_data_vectors_4 = np.load(file4+'_data_vectors.npy')#.append(np.load(file+'_data_vectors_0.npy'))
# train_samples        = np.vstack((train_samples, train_samples_2,train_samples_3,train_samples_4))
# train_data_vectors   = np.vstack((train_data_vectors, train_data_vectors_2,train_data_vectors_3,train_data_vectors_4))

# Training set 1000k
file1                = "./projects/lsst_y1/emulator_output_3x2_wcdm/lhs/dvs_for_training_1000k/train_1"
file2                = "./projects/lsst_y1/emulator_output_3x2_wcdm/lhs/dvs_for_training_1000k/train_2"
train_samples        = np.load(file1+'_samples.npy')#.append(np.load(file+'_samples_0.npy'))
train_data_vectors   = np.load(file1+'_data_vectors.npy')#.append(np.load(file+'_data_vectors_0.npy'))
train_samples_2      = np.load(file2+'_samples.npy')#.append(np.load(file+'_samples_0.npy'))
train_data_vectors_2 = np.load(file2+'_data_vectors.npy')#.append(np.load(file+'_data_vectors_0.npy'))
train_samples        = np.vstack((train_samples, train_samples_2))
train_data_vectors   = np.vstack((train_data_vectors, train_data_vectors_2))


print("testing", np.shape(train_samples), np.shape(train_data_vectors))

##3x2 setting; Not separate cosmic shear and 2x2pt
BIN_SIZE   = 1560 # number of angular bins in each z-bin
BIN_NUMBER = 1 # number of z-bins

vali_path = "./projects/lsst_y1/emulator_output_3x2_wcdm/lhs/dvs_for_validation_10k/validation"

### CONCATENATE TRAINING DATA
#train_samples = []
#train_data_vectors = []

#for file in train_samples_files:

if debug:
    print('(debug)')
    print('lhs')
    #print(train_samples[0])
    #print(train_data_vectors[0])
    print('(end debug)')

#train_samples = np.array([subsubarr for subarr in train_samples for subsubarr in subarr])#train_samples_file1
#train_data_vectors = np.array([subsubarr for subarr in train_data_vectors for subsubarr in subarr])#train_data_vectors_file1
###

# this script do the same thing for as train_emulator.py, but instead calculate the data_vactors for training, a set of

print("length of samples from LHS: ", train_samples.shape)

if config.probe=='cosmic_shear':
    print("training for cosmic shear only")
    OUTPUT_DIM = 780
    train_data_vectors = train_data_vectors[:,:OUTPUT_DIM]
    cov     = config.cov[0:OUTPUT_DIM, 0:OUTPUT_DIM]
    cov_inv = np.linalg.inv(cov) #NO mask here for cov_inv enters training
    mask_cs = config.mask[0:OUTPUT_DIM]
    dv_fid =config.dv_fid[0:OUTPUT_DIM]
    dv_std = config.dv_std[0:OUTPUT_DIM]
elif config.probe=='3x2pt':
    print("trianing for 3x2pt")
    OUTPUT_DIM = 1560
    train_data_vectors = train_data_vectors
    cov     = config.cov[0:OUTPUT_DIM, 0:OUTPUT_DIM]
    cov_inv = np.linalg.inv(cov) #NO mask here for cov_inv enters training
    mask_cs = config.mask[0:OUTPUT_DIM]
    dv_fid =config.dv_fid[0:OUTPUT_DIM]
    dv_std = config.dv_std[0:OUTPUT_DIM]
else:
    print('probe not defnied')
    quit()

def get_chi_sq_cut(train_data_vectors, chi2_cut):
    chi_sq_list = []
    for dv in train_data_vectors:
        if config.probe=='cosmic_shear':
            delta_dv = (dv - config.dv_obs[0:OUTPUT_DIM])[mask_cs] #technically this should be masked(on a fiducial scale cut), but the difference is small
            chi_sq = delta_dv @ cov_inv[mask_cs][:,mask_cs] @ delta_dv
        elif config.probe=='3x2pt':
            delta_dv = (dv - config.dv_obs)[config.mask]
            chi_sq = delta_dv @ config.masked_inv_cov @ delta_dv


        chi_sq_list.append(chi_sq)
    chi_sq_arr = np.array(chi_sq_list)
    select_chi_sq = (chi_sq_arr < chi2_cut)
    return select_chi_sq


# ====================chi2 cut for train dvs===========================
# select_chi_sq = get_chi_sq_cut(train_data_vectors, config.chi_sq_cut)
print("not applying chi2 cut to lhs")
# select_chi_sq = get_chi_sq_cut(train_data_vectors, 1e6)
# selected_obj = np.sum(select_chi_sq)
# total_obj    = len(select_chi_sq)
        
# train_data_vectors = train_data_vectors[select_chi_sq]
# train_samples      = train_samples[select_chi_sq]

print("training LHC samples after chi2 cut: ", len(train_samples))

print("Total samples enter the training: ", len(train_samples))

###============= Setting up validation set ============
validation_samples =      np.load(vali_path + '_samples.npy')
validation_data_vectors = np.load(vali_path + '_data_vectors.npy')[:,:OUTPUT_DIM]

###============= Normalize the data vectors for training; 
###============= used to be based on dv_max; but change to eigen-basis is better##
dv_max = np.abs(train_data_vectors).max(axis=0)
dv_mean = np.mean(train_data_vectors, axis=0)


#====================chi2 cut for test dvs===========================

print("not doing chi2 cut")

#print("Training emulator...")
# cuda or cpu
if torch.cuda.is_available():
    device = 'cuda'
else:
    device = 'cpu'
    torch.set_num_interop_threads(60) # Inter-op parallelism
    torch.set_num_threads(60) # Intra-op parallelism

print('Using device: ',device)

for i in range(BIN_NUMBER):

    start_idx = i*BIN_SIZE
    end_idx   = start_idx + BIN_SIZE

    print("TRAINING 3x2 directly")

    train_data_vectors      = train_data_vectors[:,start_idx:end_idx]
    validation_data_vectors = validation_data_vectors[:,start_idx:end_idx]
    OUTPUT_DIM              = end_idx - start_idx
    cov                     = cov[start_idx:end_idx, start_idx:end_idx]
    dv_fid                  = dv_fid[start_idx:end_idx]
    dv_std                  = dv_std[start_idx:end_idx]
    dv_max                  = dv_max[start_idx:end_idx]
    dv_mean                 = dv_mean[start_idx:end_idx]
    # do diagonalization C = QLQ^(T); Q is now change of basis matrix
    eigensys = np.linalg.eigh(cov)
    evals = eigensys[0]
    evecs = eigensys[1]
    #change of basis
    tmp = np.array([dv_mean for _ in range(len(train_data_vectors))])
    train_data_vectors = np.transpose((np.linalg.inv(evecs) @ np.transpose(train_data_vectors - tmp)))#[pc_idxs])
    tmp = np.array([dv_mean for _ in range(len(validation_data_vectors))])
    validation_data_vectors = np.transpose((np.linalg.inv(evecs) @ np.transpose(validation_data_vectors - tmp)))#[pc_idxs])


    TS = torch.Tensor(train_samples)
    #TS.to(device)
    TDV = torch.Tensor(train_data_vectors)
    #TDV.to(device)
    VS = torch.Tensor(validation_samples)
    #VS.to(device)
    VDV = torch.Tensor(validation_data_vectors)
    #VDV.to(device)

    print("training with the following hyper paraters: batch_size = ", config.batch_size, 'n_epochs = ', config.n_epochs)
    print("Emulator Input Dim =  ", config.n_dim, 'output_dim = ', len(dv_fid))

    emu = NNEmulator(config.n_dim, OUTPUT_DIM, 
                        dv_fid, dv_std, cov, dv_max, dv_mean,config.lhs_minmax,
                        device, model=nn_model)
    emu.train(TS, TDV, VS, VDV, batch_size=config.batch_size, n_epochs=config.n_epochs)
    print("model saved to ",str(config.savedir))
    emu.save(config.savedir + '/model_3x2')

    print("3x2pt training done")
    break

print("DONE!!")   