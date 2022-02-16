#!/usr/bin/env python
#
# This file is part of AstroHOG
#
# CONTACT: soler[AT]mpia.de
# Copyright (C) 2013-2021 Juan Diego Soler
#   
#------------------------------------------------------------------------------;

import sys
import numpy as np
from astropy.convolution import convolve_fft
from astropy.convolution import Gaussian2DKernel
from congrid import *
from scipy import ndimage
from scipy import stats

import matplotlib.pyplot as plt

import pycircstat as circ
from nose.tools import assert_equal, assert_true

from statests import * 

from tqdm import tqdm

#  -------------------------------------------------------------------------------------------------------------------------------
def mse(x, y):
    return np.linalg.norm(x - y)

# --------------------------------------------------------------------------------------------------------------------------------
def imablockaverage(corrframe, nbx=7, nby=7, weight=1.):

   sz=np.shape(corrframe)
   limsx=np.linspace(0,sz[0]-1,nbx+1,dtype=int)
   limsy=np.linspace(0,sz[1]-1,nby+1,dtype=int)

   maxvblocks=np.zeros([nbx,nby])
   sigvblocks=np.zeros([nbx,nby])
   vblocks=np.zeros([nbx,nby])

   for i in range(0, np.size(limsx)-1):
      for k in range(0, np.size(limsy)-1):
         phi=corrframe[limsx[i]:limsx[i+1],limsy[k]:limsy[k+1]]
         tempphi=phi.ravel()
         wghts=0.*tempphi[np.isfinite(tempphi).nonzero()]+weight
         pz, Zx = circ.tests.vtest(2.*tempphi[np.isfinite(tempphi).nonzero()],0.,w=wghts)
         vblocks[i,k] = Zx

   imaxb, jmaxb = (vblocks==np.max(vblocks)).nonzero()

   return vblocks

# --------------------------------------------------------------------------------------------------------------------------------
def HOGcorr_ima(ima1, ima2, s_ima1=0., s_ima2=0., pxsz=1., ksz=1., res=1., nruns=10, mask1=None, mask2=None, gradthres1=0., gradthres2=0., weights=None):
   """ Calculates the spatial correlation between im1 and im2 using the HOG method and its confidence interval using Montecarlo sampling 

   Parameters
   ----------   
   ima1 : array corresponding to the first image to be compared 
   ima2 : array corresponding to the second image to be compared
   s_ima1 : 
   s_ima2 : 
   pxsz :
   ksz : Size of the derivative kernel in the pixel size units
   
   Returns
   -------
    hogcorr :  
    corrframe :

   Examples
   --------

   """

   sz1=np.shape(ima1)
   sz2=np.shape(ima2)

   mruns1=nruns
   if np.all(s_ima1 == 0.):
      print('Warning: ima1 standard deviation not provided')
      mruns1=1

   mruns2=nruns
   if np.all(s_ima2 == 0.):
      print('Warning: ima2 standard deviation not provided')
      mruns2=1

   rvec=np.zeros(mruns1*mruns2)
   zvec=np.zeros(mruns1*mruns2)
   vvec=np.zeros(mruns1*mruns2)
   amvec=np.zeros(mruns1*mruns2) 

   if (nruns > 0):
      print("Running astroHOG Montecarlo ========================================")
      pbar = tqdm(total=mruns1*mruns2)

      for i in range(0,mruns1):
         if (s_ima1 > 0.):
            rand1=np.random.normal(loc=ima1, scale=s_ima1+0.*ima1)
         else:
            rand1=ima1                
         for k in range(0,mruns2):
            if (s_ima1 > 0.):
               rand2=np.random.normal(loc=ima2, scale=s_ima2+0.*ima2)
            else:           
               rand2=ima2
            circstats, corrframe, sima1, sima2=HOGcorr_imaLITE(rand1, rand2, pxsz=pxsz, ksz=ksz, res=res, gradthres1=gradthres1, gradthres2=gradthres2, mask1=mask1, mask2=mask2, weights=weights)
            rvec[np.ravel_multi_index((i, k), dims=(mruns1,mruns2))] =circstats['RVL'] #circstats[0]
            zvec[np.ravel_multi_index((i, k), dims=(mruns1,mruns2))] =circstats['Z']   #circstats[1]
            vvec[np.ravel_multi_index((i, k), dims=(mruns1,mruns2))] =circstats['V']   #circstats[2]
            amvec[np.ravel_multi_index((i, k), dims=(mruns1,mruns2))]=circstats['AM']  #circstats[8]

            pbar.update()

      pbar.close()  

      outr=circstats['RVL'] #circstats[0] 
      outv=circstats['V']   #circstats[2]

      meanr=np.mean(rvec)
      meanz=np.mean(zvec)
      meanv=np.mean(vvec)
      am=np.mean(amvec)
      pear=circstats['pearsonr']     
      s_r  =np.std(rvec)
      s_z  =np.std(zvec)
      s_v  =np.std(vvec)
      s_am =np.std(amvec)

      ngood=circstats['ngood'] #circstats[10]

   else:
      
      print('Montecarlo iterations disabled =============================')
      print('Warning: uncertainties on the correlation parameters will not be provided')
      circstats, corrframe, sima1, sima2=HOGcorr_imaLITE(ima1, ima2, pxsz=pxsz, ksz=ksz, res=res, gradthres1=gradthres1, gradthres2=gradthres2, mask1=mask1, mask2=mask2, weights=weights)

      meanr=circstats['MRV']   
      meanz=circstats['Z'] 
      meanv=circstats['V']  
      am=   circstats['AM']
      pear= circstats['pearsonr']
      s_r  =np.nan
      s_z  =np.nan
      s_v  =np.nan
      s_am =np.nan
      ngood=circstats['ngood']    

   circstats={'RVL': rvl, 'Z': Z, 'V': V, 'AM': am, 'meanphi': meanphi, 'pearsonr': pear, 'ngood': ngood, 's_RVL': s_r, 's_Z': s_z, 's_V': s_v, 's_AM': s_am}
   #circstats=[meanr, meanz, meanv, s_r, s_z, s_v, outr, outv, am, s_am, pear, ngood, ssimv, msev]

   return circstats, corrframe, sima1, sima2


# ---------------------------------------------------------------------------------------------------------------------
def HOGcorr_imaLITE(ima1, ima2, pxsz=1., ksz=1., res=1., mode='nearest', mask1=None, mask2=None, gradthres1=0., gradthres2=0., weights=None):
   """ Calculates the spatial correlation between im1 and im2 using the HOG method 

   Parameters
   ----------   
   ima1 : array corresponding to the first image to be compared 
   ima2 : array corresponding to the second image to be compared
   s_ima1 : 
   s_ima2 : 
   pxsz :
   ksz : Size of the derivative kernel in the pixel size units
   mode: Specify how the input array is extended when the kernel overlaps the border of the map. 
         Default: 'nearest'; The input is extended by replicating the last pixel.   
 
   Returns
   -------
    circstats:  Statistics describing the correlation between the input images.
                RVL      - Resulting vector lenght. 
                Z        - Rayleigh statistic.
                V        - Projected Ratleigh statistic.
                pearsonr - Pearson correlation coefficient.
                ngood    - Number of pixels used for the correlation
 
    corrframe : array containing the angles between the image gradients
    sima1     : ima1 smoothed with a 2D Gaussian with the size of the derivative kernel
    sima2     : ima2 smoothed with a 2D Gaussian with the size of the derivative kernel

   Examples
   --------

   """

   # Check if the images match
   assert ima2.shape == ima1.shape, "Dimensions of ima2 and ima1 must match"
   sz1=np.shape(ima1) 
   # Assign weights if none are specified
   if weights is None:
      weights=np.ones(sz1)
   # Assign weights if the weights are all the same
   if (np.size(weights)==1): 
      uniweights=weights
      weights=uniweights*np.ones(sz1)
   # Check if the provided weights match the image
   assert weights.shape == ima1.shape, "Dimensions of weights and ima1 must match" 

   # Check if the masks match the image shape
   if mask1 is None:
      "Mask 1 not defined by the user"
      mask1=np.ones_like(ima1)
   else:
      assert mask1.shape == ima1.shape, "Dimensions of mask1 and ima1 must match"
   if mask2 is None:
      "Mask 2 not defined by the user"
      mask2=np.ones_like(ima2)
   else:
      assert mask2.shape == ima2.shape, "Dimensions of mask2 and ima2 must match"

   pxksz=(ksz/(2*np.sqrt(2.*np.log(2.))))/pxsz #gaussian_filter takes sigma instead of FWHM as input

   # Calculate gradients
   sima1=ndimage.filters.gaussian_filter(ima1, [pxksz, pxksz], order=[0,0], mode=mode)
   sima2=ndimage.filters.gaussian_filter(ima2, [pxksz, pxksz], order=[0,0], mode=mode)
   dI1dx=ndimage.filters.gaussian_filter(ima1, [pxksz, pxksz], order=[0,1], mode=mode)
   dI1dy=ndimage.filters.gaussian_filter(ima1, [pxksz, pxksz], order=[1,0], mode=mode)
   dI2dx=ndimage.filters.gaussian_filter(ima2, [pxksz, pxksz], order=[0,1], mode=mode)
   dI2dy=ndimage.filters.gaussian_filter(ima2, [pxksz, pxksz], order=[1,0], mode=mode)

   # Calculation of the relative orientation angles
   tempphi=np.arctan2(dI1dx*dI2dy-dI1dy*dI2dx, dI1dx*dI2dx+dI1dy*dI2dy)
   phi=np.arctan(np.tan(tempphi))

   # Excluding null gradients
   normGrad1=np.sqrt(dI1dx**2+dI1dy**2)
   normGrad2=np.sqrt(dI2dx**2+dI2dy**2)
   bad=np.logical_or(normGrad1 <= gradthres1, normGrad2 <= gradthres2).nonzero()
   phi[bad]=np.nan
 
   # Excluding masked gradients
   if (np.size((mask1.ravel() > 0.).nonzero()) > 1):
      m1bad=(mask1 < 1.).nonzero()
      phi[m1bad]=np.nan
   else:
      print("No unmasked elements in ima1")
      phi[:]=np.nan
 
   if (np.size((mask2.ravel() > 0.).nonzero()) > 1):
      m2bad=(mask2 < 1.).nonzero()
      phi[m2bad]=np.nan
   else:
      print("No unmasked elements in ima2")
      phi[:]=np.nan

   if (np.size((mask1.ravel()*mask2.ravel() > 0.).nonzero()) < 1):
      print("No unmasked elements in the joint mask")
      phi[:]=np.nan

   good=np.isfinite(phi).nonzero()
   ngood=np.size(good)

   if (ngood >= 2):
      rvl=circ.descriptive.resultant_vector_length(2.*phi[good], w=weights[good])
      can=circ.descriptive.mean(2.*phi[good], w=weights[good])/2.
      pz, Z = circ.tests.rayleigh(2.*phi[good],  w=weights[good])
      pv, V = circ.tests.vtest(2.*phi[good], 0., w=weights[good])

      output=HOG_PRS(2.*phi[good], weights=weights[good])
      myV=output['Zx'] 
      s_myV=output['s_Zx'] 
      meanphi=output['meanphi']

      am=HOG_AM(phi[good])

      pear, peap = stats.pearsonr(sima1[good], sima2[good])

   else:
      print("WARNING: not enough pixels to compute astroHOG")
      rvl=np.nan
      Z=np.nan; pz=np.nan;
      V=np.nan; pv=np.nan;
      myV=np.nan; s_myV=np.nan;
      meanphi=np.nan;
      am=np.nan; pear=np.nan;  
   
   ssimv=np.nan #ssim(sima1[good], sima2[good])
   msev =np.nan #mse(sima1[good], sima2[good])

   #circstats=[rvl, Z, V, pz, pv, myV, s_myV, meanphi, am, pear, ngood, ssimv, msev]
   circstats={'RVL': rvl, 'Z': Z, 'V': V, 'AM': am, 'meanphi': meanphi, 'pearsonr': pear, 'ngood': ngood}
   corrframe=phi

   return circstats, corrframe, sima1, sima2

   
# -------------------------------------------------------------------------------------------------------------------------------
def HOGcorr_frameandvec(frame1, vecx, vecy, gradthres=0., vecthres=0., pxsz=1., ksz=1., res=1., mask1=0, mask2=0, wd=1, allow_huge=False, regrid=False):
   # Calculates the spatial correlation between frame1 and the vector field described by vecx and vecy using the HOG methods
   #
   # INPUTS
   # frame1 - input map 
   # vecx   - x-component of the input vector field
   # vecy   - y-component of the input vector field
   #
   # OUTPUTS
   # hogcorr   -   
   # corrframe -

   sf=3. #Number of pixels per kernel FWHM      

   pxksz=(ksz/(2*np.sqrt(2.*np.log(2.))))/pxsz #gaussian_filter takes sigma instead of FWHM as input
   pxres =res/pxsz

   sz1=np.shape(frame1)

   if (ksz > 1):
      if (regrid):
         intframe1=congrid(frame1, [np.int(np.round(sf*sz1[0]/pxres)), np.int(np.round(sf*sz1[1]/pxres))])
         intvecx  =congrid(vecx,   [np.int(np.round(sf*sz1[0]/pxres)), np.int(np.round(sf*sz1[1]/pxres))])
         intvecy  =congrid(vecy,   [np.int(np.round(sf*sz1[0]/pxres)), np.int(np.round(sf*sz1[1]/pxres))])
         if np.array_equal(np.shape(frame1), np.shape(mask1)):
            intmask1=congrid(mask1, [np.int(np.round(sf*sz1[0]/pxres)), np.int(np.round(sf*sz1[1]/pxres))])
            intmask1[(intmask1 > 0.).nonzero()]=1.
            if np.array_equal(np.shape(frame2), np.shape(mask2)):
               intmask2=congrid(mask2, [np.int(np.round(sf*sz1[0]/pxres)), np.int(np.round(sf*sz1[1]/pxres))])
               intmask2[(intmask2 > 0.).nonzero()]=1.
      else:
         intframe1=frame1
         intvecx=vecx
         intvecy=vecy
         intmask1=mask1
         intmask2=mask2
      smoothframe1=ndimage.filters.gaussian_filter(frame1, [pxksz, pxksz], order=[0,0], mode='nearest')
      dI1dx=ndimage.filters.gaussian_filter(frame1, [pxksz, pxksz], order=[0,1], mode='nearest')
      dI1dy=ndimage.filters.gaussian_filter(frame1, [pxksz, pxksz], order=[1,0], mode='nearest')

   else:
      intframe1=frame1
      smoothframe1=frame1
      intvecx=vecx
      intvecy=vecy
      intmask1=mask1
      intmask2=mask2
      #grad1=np.gradient(intframe1)
      dI1dx=ndimage.filters.gaussian_filter(frame1, [1, 1], order=[0,1], mode='nearest')
      dI1dy=ndimage.filters.gaussian_filter(frame1, [1, 1], order=[1,0], mode='nearest')

   # ========================================================================================================================
   normGrad1=np.sqrt(dI1dx*dI1dx+dI1dy*dI1dy) #np.sqrt(grad1[1]**2+grad1[0]**2)
   normVec=np.sqrt(intvecx*intvecx + intvecy*intvecy)
   bad=np.logical_or(normGrad1 <= gradthres, normVec <= vecthres).nonzero()

   normGrad1[bad]=1.; normVec[bad]=1.;
   tempphi=np.arctan2(dI1dx*intvecy-dI1dy*intvecx, dI1dx*intvecx+dI1dy*intvecy)
   tempphi[bad]=np.nan
   phi=np.arctan(np.tan(tempphi))

   corrframe=np.cos(2.*phi)

   if np.array_equal(np.shape(intframe1), np.shape(intmask1)):
      corrframe[(intmask1 == 0.).nonzero()]=np.nan
      if np.array_equal(np.shape(intvecx), np.shape(intmask2)):
         corrframe[(intmask2 == 0.).nonzero()]=np.nan
         good=np.logical_and(np.logical_and(np.isfinite(phi), intmask1 > 0), intmask2 > 0).nonzero()
      else:
         good=np.logical_and(np.isfinite(phi), intmask1 > 0).nonzero()
   else:
         good=np.isfinite(phi).nonzero()
   #Zx, s_Zx, meanPhi = HOG_PRS(phi[good])
   output=HOG_PRS(2.*phi[good], w=weights[good])
   Zx=output['Zx']
   s_Zx=output['s_Zx']
   meanPhi=output['meanphi']

   return Zx, corrframe, smoothframe1



