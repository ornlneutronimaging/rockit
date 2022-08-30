import math
import dxchange
import numpy as np
import os
import glob
import tomopy
import svmbir
import bm3d_streak_removal as bm3d_rmv

def get_ind_list(name_list: list):
	ind = []
	ang_deg = []
	ang_rad = []
	ind_dict_random = {}
	ind_dict_sorted = {}
	for e_name in name_list:
		_split = e_name.split('_')
		_index_tiff = _split[-1]
		_index = _index_tiff.split('.')[0]
		_ang = _split[-3] + '.' + _split[-2]
		index = int(_index)
		angle = float(_ang)
		ind.append(index)
		ang_deg.append(angle)
		ang_rad.append(math.radians(angle))
		ind_dict_random[index] = e_name
	ind = sorted(ind)
	for n, e_ind in enumerate(ind):
		ind_dict_sorted[n] = ind_dict_random[e_ind]

	return list(ind_dict_sorted.values()), (sorted(ang_deg)), np.array(sorted(ang_rad)), ind


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
	for m, name in enumerate(fname):
		arr[m] = dxchange.read_tiff(os.path.join(fdir, name))
	return arr


def read_tiff_from_full_name_list(list_files: list):
	arr = _init_arr_from_stack(list_files[0], len(list_files))
	for m, _file in enumerate(list_files):
		arr[m] = dxchange.read_tiff(_file)
	return arr


def find_proj180_ind(ang_list: list):
	dif = [abs(x - 180) for x in ang_list]
	difmin = min(dif)
	ind180 = dif.index(difmin)
	return (ind180, ang_list[ind180])


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
        ct_name, ang_deg, theta, idx_list = get_ind_list(ct_list)
    else:
        ct_list = glob.glob(fdir+"/"+name)
        ct_name, idx_list = get_list(ct_list)
        theta = tomopy.angles(len(idx_list), ang1=ang1, ang2=ang2) # Default 360 degree rotation
        ang_deg = np.rad2deg(theta)
    proj180_ind = find_proj180_ind(ang_deg)[0]
    print('Found index of 180 degree projections: ', proj180_ind)
    print('Loading CT projections...')
    proj = read_tiff_stack(fdir=fdir, fname=ct_name)
    print('Loading CT projections...Done!')
    return proj, theta, proj180_ind

    
def load_ob(fdir, name="ob*"):
    if is_routine_ct(fdir):
        ob_name, idx_list = get_name_and_idx(fdir)
    else:
        ob_list = glob.glob(fdir+"/"+name)
        ob_name, idx_list = get_list(ob_list)
    print("Loading Open Beam (OB)...")
    ob = read_tiff_stack(fdir=fdir, fname=ob_name)
    print("Loading Open Beam (OB)...Done!")
    return ob


def load_dc(fdir, name="dc*"):
    if is_routine_ct(fdir):
        dc_name, idx_list = get_name_and_idx(fdir)
    else:
        dc_list = glob.glob(fdir+"/"+name)
        dc_name, idx_list = get_list(dc_list)
    print("Loading Dark Current (DC)...")
    dc = read_tiff_stack(fdir=fdir, fname=dc_name)
    print("Loading Dark Current (DC)...Done!")
    return dc


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
        
