import math
import dxchange
import numpy as np
import os


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
