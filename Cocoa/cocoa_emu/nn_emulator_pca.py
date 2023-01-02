import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import MultivariateNormal
from tqdm import tqdm
import numpy as np
import h5py as h5
from torchvision import models
from torchinfo import summary


class Affine(nn.Module):
    def __init__(self):
        super(Affine, self).__init__()

        self.gain = nn.Parameter(torch.ones(1))
        self.bias = nn.Parameter(torch.zeros(1))

    def forward(self, x):
        return x * self.gain + self.bias

class ResBlock(nn.Module):
    def __init__(self, in_size, out_size):
        super(ResBlock, self).__init__()
        
        if in_size != out_size:
            self.skip = nn.Linear(in_size, out_size, bias=False)
        else:
            self.skip = nn.Identity()

        self.layer1 = nn.Linear(in_size, out_size)
        self.layer2 = nn.Linear(out_size, out_size)

        self.norm1 = Affine()
        self.norm2 = Affine()

        # self.act1 = nn.PReLU()
        # self.act2 = nn.PReLU()
        self.act1 = nn.Tanh()
        self.act2 = nn.Tanh()

    def forward(self, x):
        xskip = self.skip(x)

        o1 = self.layer1(self.act1(self.norm1(x))) / np.sqrt(10)
        o2 = self.layer2(self.act2(self.norm2(o1))) / np.sqrt(10) + xskip

        return o2

class nn_pca_emulator:
    def __init__(self, 
                  N_DIM, OUTPUT_DIM, 
                  dv_fid, dv_std, cov_inv_pc, cov_inv_npc,
                  pca_idxs, idxs_C, full_cov,
                  device, 
                  optim=None, reduce_lr=True, scheduler=None):
        print('input dimension = {}'.format(N_DIM))
        print('output dimension = {}'.format(OUTPUT_DIM))

        self.N_DIM = N_DIM
        self.OUTPUT_DIM = OUTPUT_DIM
        
        self.dv_fid  = torch.Tensor(dv_fid)
        self.dv_std  = torch.Tensor(dv_std)
        self.cov_inv_pc = torch.Tensor(cov_inv_pc)  
        self.cov_inv_npc = torch.Tensor(cov_inv_npc)

        self.optim = optim
        self.device = device 
        self.reduce_lr = reduce_lr

        self.pca_idxs = pca_idxs
        self.idxs_C = idxs_C
        self.full_cov = full_cov

        self.trained = False     
        print("Using resnet+PCA model...")
        #self.PCA_vecs = torch.Tensor(PCA_vecs)
        
        self.model = nn.Sequential(
                nn.Linear(N_DIM, 512),
                ResBlock(512, 1024),
                nn.Dropout(0.3),
                nn.PReLU(),
                nn.Linear(1024, OUTPUT_DIM),
                Affine()
                )

        self.model.to(self.device)
        
        if self.optim is None:
            self.optim = torch.optim.Adam(self.model.parameters(), lr=1e-4)
        if self.reduce_lr == True:
            print('Reduce LR on plateu: ',self.reduce_lr)
            self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(self.optim, 'min')

    def train(self, X, y, X_validation, y_validation, test_split=None, batch_size=1000, n_epochs=250):
        print('Batch size = ',batch_size)
        print('N_epochs = ',n_epochs)
        print('Begin training...')

        epoch_range = tqdm(range(n_epochs))

        # ge normalization factors
        if not self.trained:
            self.X_mean = torch.Tensor(X.mean(axis=0, keepdims=True))
            self.X_std  = torch.Tensor(X.std(axis=0, keepdims=True))
            self.y_mean = self.dv_fid
            self.y_std  = self.dv_std

        # initialize arrays
        losses_train = []
        losses_vali = []
        loss = 100.

        # send everything to device
        tmp_y_std        = self.y_std.to(self.device)
        tmp_cov_inv_pc   = self.cov_inv_pc.to(self.device)
        tmp_cov_inv_npc  = self.cov_inv_npc.to(self.device)
        tmp_X_mean       = self.X_mean.to(self.device)
        tmp_X_std        = self.X_std.to(self.device)
        tmp_X_validation = (X_validation.to(self.device) - tmp_X_mean)/tmp_X_std
        tmp_Y_validation = y_validation.to(self.device)

        # Here is the input normalization
        X_train     = ((X - self.X_mean)/self.X_std) # Note that this can mean inputs are <0 !!! Should not use non-symmetric activations
        y_train     = y#((y - self.y_mean)/self.y_std) 
        trainset    = torch.utils.data.TensorDataset(X_train, y_train)
        trainloader = torch.utils.data.DataLoader(trainset, batch_size=batch_size, shuffle=True, drop_last=True, num_workers=1)
    
        for e in epoch_range:
            self.model.train()
            losses = []
            for i, data in enumerate(trainloader):    
                X       = data[0].to(self.device)
                Y_batch = data[1].to(self.device)
                Y_pred  = self.model(X) * tmp_y_std[self.pca_idxs]

                # PCA part
                diff = Y_batch[:,self.pca_idxs] - Y_pred
                loss1 = (diff \
                        @ tmp_cov_inv_pc) \
                        @ torch.t(diff)
                # non-PCA part
                loss2 = (Y_batch[:,self.idxs_C] \
                        @ tmp_cov_inv_npc) \
                        @ torch.t(Y_batch[:,self.idxs_C])

                loss = torch.mean(torch.diag(loss1+loss2))
                losses.append(loss.cpu().detach().numpy())
                #print('[ debug ] mean batch diff =',torch.mean(Y_batch-Y_pred).cpu().detach().numpy(),file=sys.stderr)
                self.optim.zero_grad()
                loss.backward()
                self.optim.step()
            
            ###validation loss
            with torch.no_grad():
                self.model.eval()
                Y_v_pred = self.model(tmp_X_validation) * tmp_y_std[self.pca_idxs]
                v_diff = tmp_Y_validation[:,self.pca_idxs] - Y_v_pred
                loss_vali1 = (v_diff \
                                @ tmp_cov_inv_pc) @ \
                                torch.t(v_diff)
                loss_vali2 = ((tmp_Y_validation[:,self.idxs_C]) \
                                @ tmp_cov_inv_npc) @ \
                                torch.t(tmp_Y_validation[:,self.idxs_C])
                loss_vali = torch.mean(torch.diag(loss_vali1+loss_vali2))
 
                losses_vali.append(np.float(loss_vali.cpu().detach().numpy()))
                losses_train.append(np.mean(losses))
                if self.reduce_lr:
                    self.scheduler.step(loss_vali)

            #print('epoch {}, loss={}, validation loss={}'.format(e,losses_train[-1],losses_vali[-1]))
            epoch_range.set_description('Loss: {0}, Loss_validation: {1}'.format(loss, loss_vali))
        
        np.savetxt("losses.txt", np.array([losses_train,losses_vali],dtype=np.float64))
        #np.savetxt("test_dv.txt", np.array( [y_validation.detach().numpy()[-1], y_vali_pred.detach().numpy()[-1]] ), fmt='%s')
        self.trained = True

    def predict(self, X):
        assert self.trained, "The emulator needs to be trained first before predicting"
        with torch.no_grad():
            X_mean = self.X_mean.clone().detach().to(self.device).float()
            X_std  = self.X_std.clone().detach().to(self.device).float()
            y_pred = self.model.eval()((X.to(self.device) - X_mean) / X_std).float().cpu() * tmp_y_std[self.pca_idxs] # normalization
            
        evecs = np.linalg.eig(self.full_cov[0:OUTPUT_DIM,0:OUTPUT_DIM])[1]
        y_pred = evecs @ y_pred + self.dv_fid #change of basis

        return y_pred.numpy()

    def save(self, filename):
        torch.save(self.model, filename)
        with h5.File(filename + '.h5', 'w') as f:
            f['X_mean'] = self.X_mean
            f['X_std']  = self.X_std
            f['Y_mean'] = self.y_mean
            f['Y_std']  = self.y_std
            f['dv_fid'] = self.dv_fid
            f['dv_std'] = self.dv_std
            f['full_cov'] = self.full_cov
        
    def load(self, filename):
        self.trained = True
        self.model = torch.load(filename)
        with h5.File(filename + '.h5', 'r') as f:
            self.X_mean = torch.Tensor(f['X_mean'][:]).float()
            self.X_std  = torch.Tensor(f['X_std'][:]).float()
            self.y_mean = torch.Tensor(f['Y_mean'][:]).float()
            self.y_std  = torch.Tensor(f['Y_std'][:]).float()
            self.dv_fid = torch.Tensor(f['dv_fid'][:]).float()
            self.dv_std = torch.Tensor(f['dv_std'][:]).float()
            self.full_cov = torch.Tensor(f['full_cov'][:]).float()

