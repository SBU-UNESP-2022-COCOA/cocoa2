import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import MultivariateNormal
from tqdm import tqdm
import numpy as np
import h5py as h5

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

        self.act1 = nn.PReLU()
        self.act2 = nn.PReLU()

    def forward(self, x):
        xskip = self.skip(x)

        o1 = self.layer1(self.act1(self.norm1(x))) / np.sqrt(10)
        o2 = self.layer2(self.act2(self.norm2(o1))) / np.sqrt(10) + xskip

        return o2

    
class NNEmulator:
    def __init__(self, N_DIM, OUTPUT_DIM, dv_fid, dv_std, cov_inv, dv_max, model='resnet', optim=None, device='cpu'):
        self.N_DIM = N_DIM
        self.model = model
        self.optim = optim
        self.device = device
        self.trained = False
        self.dv_fid = torch.Tensor(dv_fid)
        self.dv_std = torch.Tensor(dv_std)
        self.cov_inv    = torch.Tensor(cov_inv)
        self.dv_max = torch.Tensor(dv_max)
        self.output_dim = OUTPUT_DIM
        
        if model is None:
            print("Using simply connected NN...")
            # self.model = nn.Sequential(
            #                     nn.Linear(N_DIM, 1024),
            #                     nn.ReLU(),
            #                     nn.Dropout(0.3),
            #                     nn.Linear(1024, 1024),
            #                     nn.ReLU(),
            #                     nn.Dropout(0.3),
            #                     nn.Linear(1024, 1024),
            #                     nn.ReLU(),
            #                     nn.Dropout(0.3),
            #                     nn.Linear(1024, 1024),
            #                     nn.ReLU(),
            #                     nn.Dropout(0.3),
            #                     nn.Linear(1024, OUTPUT_DIM),
            #                     Affine()
            #                     )
            self.model = nn.Sequential(
                                nn.Linear(N_DIM, 512),
                                nn.ReLU(),
                                nn.Dropout(0.3),
                                nn.Linear(512, 512),
                                nn.ReLU(),
                                nn.Dropout(0.3),
                                nn.Linear(512, 512),
                                nn.ReLU(),
                                nn.Dropout(0.3),
                                nn.Linear(512, 512),
                                nn.ReLU(),
                                nn.Dropout(0.3),
                                nn.Linear(512, 512), #additional laryer
                                nn.ReLU(), #additional laryer
                                nn.Dropout(0.3), #additional laryer
                                nn.Linear(512, OUTPUT_DIM),
                                Affine()
                                )            
        elif(model=='resnet'):
            print("Using resnet model...")
            self.model = nn.Sequential(
                    nn.Linear(N_DIM, 128),
                    ResBlock(128, 256),
                    nn.Dropout(0.3),
                    ResBlock(256, 256),
                    nn.Dropout(0.3),
                    ResBlock(256, 256),
                    nn.Dropout(0.3),
                    ResBlock(256, 512),
                    nn.Dropout(0.3),
                    ResBlock(512, 512),
                    nn.Dropout(0.3),
                    ResBlock(512, 512),
                    nn.Dropout(0.3),
                    ResBlock(512, 1024),
                    nn.Dropout(0.3),
                    ResBlock(1024, 1024),
                    nn.Dropout(0.3),
                    ResBlock(1024, 1024),
                    nn.Dropout(0.3),
                    ResBlock(1024, 1024),
                    nn.Dropout(0.3),
                    ResBlock(1024, 1024),
                    Affine(),
                    nn.PReLU(),
                    nn.Linear(1024, OUTPUT_DIM),
                    Affine()
                )


        device = "cuda" if torch.cuda.is_available() else "cpu" #KZ
        print(device)
        self.model.to(device)
        

        if self.optim is None:
            # self.optim = torch.optim.Adam(self.model.parameters(), weight_decay=1e-4)
            #self.optim = torch.optim.Adam(self.model.parameters(), lr=1e-3, weight_decay=1e-4)
            self.optim = torch.optim.Adam(self.model.parameters(), lr=5e-4)

    def do_pca(self, data_vector, N_PCA):
        self.N_PCA = N_PCA
        pca = PCA(self.N_PCA)
        pca.fit(data_vector)
        self.pca = pca
        pca_coeff = pca.transform(data_vector)
        return pca_coeff
    
    def do_inverse_pca(self, pca_coeff):
        return self.pca.inverse_transform(pca_coeff)
    
    def train(self, X, y, X_validation, y_validation, test_split=None, batch_size=32, n_epochs=100):
        if not self.trained:
            self.X_mean = torch.Tensor(X.mean(axis=0, keepdims=True))
            self.X_std  = torch.Tensor(X.std(axis=0, keepdims=True))
            self.y_mean = self.dv_fid
            self.y_std  = self.dv_std

        X_train = (X - self.X_mean) / self.X_std
        y_train = y

        trainset = torch.utils.data.TensorDataset(X_train, y_train)
        trainloader = torch.utils.data.DataLoader(trainset, batch_size=batch_size, shuffle=True, drop_last=True, num_workers=1)
        epoch_range = tqdm(range(n_epochs))


        X_validation = (X_validation - self.X_mean) /self.X_std #normalize the same way as training set

        losses = []
        losses_vali = []
        loss = 100.
        for _ in epoch_range:
            loss_epoch = 0
            count = 0
            for i, data in enumerate(trainloader):
                X_batch = data[0]
                y_batch = data[1]

                y_pred = self.model(X_batch)
                delta_y = (y_batch - y_pred) * self.dv_max
                loss = torch.mean(torch.abs((delta_y @ self.cov_inv) @ torch.t(delta_y) ))
                #loss = 2*torch.mean(torch.abs((delta_y @ self.cov_inv) @ torch.t(delta_y)))
                # if loss > 100:
                #     print("Unreasonable Loss = ", loss)
                #     quit()
                loss_epoch += loss.detach().numpy()
                count += 1
                self.optim.zero_grad()
                loss.backward()
                self.optim.step()

            losses.append(loss_epoch / count)
            ###Test loss

            y_vali_pred = self.model(X_validation) * self.dv_max
            # print("y_test_pred:", y_test_pred)
            # print("y_test: ", y_test)
            # quit()
            delta_y = (y_validation - y_vali_pred) 
            loss_vali = torch.mean(torch.abs((delta_y @ self.cov_inv) @ torch.t(delta_y) ))
            losses_vali.append(loss_vali.detach().numpy())


                
            epoch_range.set_description('Loss: {0}, Loss_validation: {1}'.format(loss,loss_vali))
        
        np.savetxt("losses.txt", np.array([losses,losses_vali]), fmt='%s')
        np.savetxt("test_dv.txt", np.array( [y_validation.detach().numpy()[-1], y_vali_pred.detach().numpy()[-1]] ), fmt='%s')
        self.trained = True

    def predict(self, X):
        assert self.trained, "The emulator needs to be trained first before predicting"

        with torch.no_grad():
            X_mean = self.X_mean.clone().detach()
            X_std  = self.X_std.clone().detach()

            X_norm = (X - X_mean) / X_std
            y_pred = self.model.eval()(X_norm).cpu()
            
        y_pred = y_pred* self.dv_max

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
            f['dv_max'] = self.dv_max
        
    def load(self, filename):
        self.trained = True
        self.model = torch.load(filename)
        with h5.File(filename + '.h5', 'r') as f:
            self.X_mean = torch.Tensor(f['X_mean'][:])
            self.X_std  = torch.Tensor(f['X_std'][:])
            self.y_mean = torch.Tensor(f['Y_mean'][:])
            self.y_std  = torch.Tensor(f['Y_std'][:])
            self.dv_fid = torch.Tensor(f['dv_fid'][:])
            self.dv_std = torch.Tensor(f['dv_std'][:])
            self.dv_max = torch.Tensor(f['dv_max'][:])