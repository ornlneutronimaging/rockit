import math
import dxchange
import numpy as np
import pandas as pd
import os
import glob
import tomopy
import svmbir
from tqdm import tqdm
import bm3d_streak_removal as bm3d_rmv

# slit_box_corners = np.array([[ None,  None], [ None, None], [None, None], [None,  None]])

def get_deg(fname:str):
    _split = fname.split('_')
    ang = _split[-3] + '.' + _split[-2]
    return ang

def get_fname_df(name_list: list, golden_ratio=False):
	ind = []
	ang_deg = []
	ang_rad = []
	fname_df = pd.DataFrame()
	for e_name in name_list:
		_split = e_name.split('_')
		_index_tiff = _split[-1]
		_index = _index_tiff.split('.')[0]
		if golden_ratio:
    			_ang = _split[-4] + '.' + _split[-3]
		else:
			_ang = _split[-3] + '.' + _split[-2]
		index = int(_index)
		angle = float(_ang)
		ind.append(index)
		ang_deg.append(angle)
		ang_rad.append(math.radians(angle))
	fname_df['fname'] = name_list
	fname_df['ang_deg'] = ang_deg
	fname_df['ang_rad'] = ang_rad
	fname_df['idx'] = ind
	return fname_df

def get_list_by_idx(name_list: list, golden_ratio=False):
	fname_df = get_fname_df(name_list, golden_ratio)
	fname_df.sort_values('idx', inplace=True)
	fname = fname_df['fname'].to_list()
	ang_deg = fname_df['ang_deg'].to_list()
	ang_rad = fname_df['ang_rad'].to_list()
	ind = fname_df['idx'].to_list()
	return fname, ang_deg, ang_rad, ind

def get_list_by_ang(name_list: list, golden_ratio=False):
	fname_df = get_fname_df(name_list, golden_ratio)
	fname_df.sort_values('ang_deg', inplace=True)
	fname = fname_df['fname'].to_list()
	ang_deg = fname_df['ang_deg'].to_list()
	ang_rad = fname_df['ang_rad'].to_list()
	ind = fname_df['idx'].to_list()
	return fname, ang_deg, ang_rad, ind

def get_list(name_list: list):
	ind = []
	ind_dict_random = {}
	ind_dict_sorted = {}
	for e_name in name_list:
		_split = e_name.split('_')
		_index_tiff = _split[-1]
		_index = _index_tiff.split('.')[0]
		index = int(_index)
		ind.append(index)
		ind_dict_random[index] = e_name
	ind = sorted(ind)
	for n, e_ind in enumerate(ind):
		ind_dict_sorted[n] = ind_dict_random[e_ind]

	return list(ind_dict_sorted.values()), ind


def _init_arr_from_stack(fname, number_of_files, slc=None):
	"""
	Initialize numpy array from files in a folder.
	"""
	_arr = dxchange.read_tiff(fname, slc)
	size = (number_of_files, _arr.shape[0], _arr.shape[1])
	return np.empty(size, dtype=_arr.dtype)


def read_tiff_stack(fdir, fname: list):
	arr = _init_arr_from_stack(os.path.join(fdir, fname[0]), len(fname))
	for m, name in tqdm(enumerate(fname)):
		arr[m] = dxchange.read_tiff(os.path.join(fdir, name))
	return arr


def find_proj180_ind(ang_list: list):
	dif = [abs(x - 180) for x in ang_list]
	difmin = min(dif)
	ind180 = dif.index(difmin)
	return (ind180, ang_list[ind180])

def find_idx_by_ang(ang_list: list, ang):
	dif = [abs(x - ang) for x in ang_list]
	difmin = min(dif)
	ind = dif.index(difmin)
	return (ind, ang_list[ind])


def shrink_window(corners, size):
	corners[0][0] = corners[0][0] + size
	corners[0][1] = corners[0][1] + size
	corners[1][0] = corners[1][0] + size
	corners[1][1] = corners[1][1] - size
	corners[2][0] = corners[2][0] - size
	corners[2][1] = corners[2][1] - size
	corners[3][0] = corners[3][0] - size
	corners[3][1] = corners[3][1] + size
	return corners


def set_roi(corners, xmin, ymin, xmax, ymax):
	corners[0][0] = xmin
	corners[0][1] = ymin
	corners[1][0] = xmin
	corners[1][1] = ymax
	corners[2][0] = xmax
	corners[2][1] = ymax
	corners[3][0] = xmax
	corners[3][1] = ymin
	return corners

################################################ Added on 8/24/2022

def is_routine_ct(ct_dir):
    re_list = []
    for each in ["raw*", "ct*", "ob*", "OB*", "dc*", "DC*", "df*", "DF*"]:
        re = len(glob.glob(ct_dir + "/" + each)) == 0
        re_list.append(re)
    if False in re_list:
        return False
    else:
        return True


def get_name_and_idx(fdir):
    fname_list = os.listdir(fdir)
    fname, idx_list = get_list(fname_list)
    return fname, idx_list

    
def load_ct(fdir, ang1=0, ang2=360, name="raw*"):
    if is_routine_ct(fdir):
        ct_list = os.listdir(fdir)
        # ct_name, ang_deg, theta, idx_list = get_ind_list(ct_list)
        ct_name, ang_deg, ang_rad, idx_list = get_list_by_ang(ct_list)
    else:
        ct_list = glob.glob(fdir+"/"+name)
        ct_name, idx_list = get_list(ct_list)
        ang_rad = tomopy.angles(len(idx_list), ang1=ang1, ang2=ang2) # Default 360 degree rotation
        ang_deg = np.rad2deg(ang_rad)
    proj180_ind = find_idx_by_ang(ang_deg, 180)
    proj000_ind = find_idx_by_ang(ang_deg, 0)
    print('Found index of 180 degree projections: {} of angle {}'.format(proj180_ind[0], proj180_ind[1]))
    print('Found index of 0 degree projections: {} of angle {}'.format(proj000_ind[0], proj000_ind[1]))
    print('Loading {} CT projections...'.format(len(ct_name)))
    proj = read_tiff_stack(fdir=fdir, fname=ct_name)
    print('{} CT projections loaded!'.format(len(ct_name)))
    print('Shape: {}'.format(proj.shape))
    return proj, ang_deg, ang_rad, proj180_ind[0], proj000_ind[0], ct_name

    
def load_ob(fdir, name="ob*"):
    if is_routine_ct(fdir):
        ob_name, idx_list = get_name_and_idx(fdir)
    else:
        ob_list = glob.glob(fdir+"/"+name)
        ob_name, idx_list = get_list(ob_list)
    print("Loading {} Open Beam (OB) images...".format(len(ob_name)))
    ob = read_tiff_stack(fdir=fdir, fname=ob_name)
    print("{} Open Beam (OB) images loaded!".format(len(ob_name)))
    print('Shape: {}'.format(ob.shape))
    return ob


def load_dc(fdir, name="dc*"):
    if is_routine_ct(fdir):
        dc_name, idx_list = get_name_and_idx(fdir)
    else:
        dc_list = glob.glob(fdir+"/"+name)
        dc_name, idx_list = get_list(dc_list)
    print("Loading {} Dark Current (DC) images...".format(len(dc_name)))
    dc = read_tiff_stack(fdir=fdir, fname=dc_name)
    print("{} Dark Current (DC) images loaded!".format(len(dc_name)))
    print('Shape: {}'.format(dc.shape))
    return dc

##########################

def load_static(fdir, name="dc*", diff="20"):
    if is_routine_ct(fdir):
        dc_name, idx_list = get_name_and_idx(fdir)
    else:
        dc_list = glob.glob(fdir+"/"+name)
        dc_name, idx_list = get_list(dc_list)
    dc = read_tiff_stack(fdir=fdir, fname=dc_name)
    if dc.shape[0] == 1:
    	dc_med = dc[:]
    	print("Only 1 file loaded.")
    else:
    	dc = tomopy.misc.corr.remove_outlier(dc, diff)
    	dc_med = np.median(dc, axis=0).astype(np.ushort)
    return dc_med

##########################

def remove_ring(proj, algorithm="Vo"):
    if algorithm == "Vo":
        proj_rmv = tomopy.prep.stripe.remove_all_stripe(proj)
    elif algorithm == "bm3d":
        proj_norm = bm3d_rmv.extreme_streak_attenuation(proj)
        proj_rmv = bm3d_rmv.multiscale_streak_removal(proj_norm)
    return proj_rmv


def recon(proj, theta, rot_center, algorithm="gridrec"):
    if algorithm == "svMBIR":
        # T, P, sharpness, snr_db: parameters of reconstruction, usually keep fixed. (Can be played with)
        T = 2.0
        p = 1.2
        sharpness = 0.0
        snr_db = 30.0
        center_offset= -(proj.shape[2]/2 - rot_center)
        recon = svmbir.recon(proj, angles=theta, weight_type='transmission',
                             center_offset=center_offset, 
                             snr_db=snr_db, p=p, T=T, sharpness=sharpness, 
                             positivity=False, max_iterations=100, 
                             num_threads= 112, verbose=0) # verbose: display of reconstruction: 0 is minimum, 1 is regular
    else:
        recon = tomopy.recon(proj, theta, center=rot_center, algorithm=algorithm, sinogram_order=False)
    recon = tomopy.circ_mask(recon, axis=0, ratio=1)
    return recon

################################################ Added on 11/01/2022

def add_idx_to_front(old:str, index_min=0):
    old_index = get_index_num(old)
    end_num = int(old_index)
    new_num = end_num - index_min
    new_index = f'{index:04}'
    new = new_index + "_" + old
    return old
    
def get_last_str(fname:str):
    _split = fname.split('_')
    idx_tiff = _split[-1]
    _idx_tiff_split = idx_tiff.split('.')
    idx = _idx_tiff_split[0]
    return idx
    
def remove_1st_str(fname:str):
    _split = fname.split('_')
    _split.pop(0)
    new_fname = "_".join(_split)
    return new_fname

def remove_last_str(fname:str):
    _split = fname.split('_')
    last_ext = _split[-1]
    _last_ext_split = last_ext.split('.')
    ext = _last_ext_split[-1]
    _split.pop(-1)
    new_fname = "_".join(_split) + '.' + ext
    return new_fname

def normalize(proj, ob, dc):
#    assert len(proj.shape) == 2
#    assert len(ob.shape) == 3
#    assert len(dc.shape) == 3
    if len(ob.shape) == 2:
        ob_med = ob[:]
        print("Only 1 OB loaded.")
    elif len(ob.shape) == 3:
        ob_med = np.median(ob, axis=0).astype(np.ushort)
        print("OB stack combined by median.")
    if len(dc.shape) == 2:
        dc_med = dc[:]
        print("Only 1 DC loaded.")
    elif len(dc.shape) == 3:
        dc_med = np.median(dc, axis=0).astype(np.ushort)
        print("DC stack combined by median.")
    print("Normalizing...")
#    if len(proj.shape) == 2:
#        proj = proj[:]
#    elif len(proj.shape) == 3:
#        proj = np.median(proj, axis=0).astype(np.ushort)
#        print("Projection stack combined by median.")
    _ob = ob_med - dc_med
    _proj = proj - dc_med
    proj_norm = np.true_divide(_proj, _ob, dtype=np.float32)
    print("Normalization Done!")
    return proj_norm, ob_med, dc_med

def crop(stack, crop_left, crop_right, crop_top, crop_bottom, crop=True):
    if len(stack.shape) == 3:
    	if crop:
    		new_stack = stack[:, crop_top:crop_bottom, crop_left:crop_right]
    	else:
    		new_stack = stack[:]
    elif len(stack.shape) == 2:
    	if crop:
    		new_stack = stack[crop_top:crop_bottom, crop_left:crop_right]
    	else:
    		new_stack = stack[:]
    else:
    	print("Not a image, no cropping is done")
    	new_stack = None
    return new_stack

def log(history:dict, event:str, info):
    history[event] = info
    return history
        
