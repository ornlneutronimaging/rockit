import argparse
import logging
import os
import glob
import shutil

import dxchange
from tomopy import find_center_pc, circ_mask, normalize, minus_log
import tomopy.recon as reconstruction
from tomopy.prep.alignment import find_slits_corners_aps_1id, remove_slits_aps_1id
from tomopy.misc.corr import remove_outlier
from tomopy.prep.normalize import normalize_bg
from tomopy.prep.stripe import remove_all_stripe

import numpy as np
# import bm3d_streak_removal as bm3d_rmv
from imars3dv2.filters import tilt
from utilites import get_ind_list, find_proj180_ind, read_tiff_stack, read_tiff_from_full_name_list, set_roi

import warnings
warnings.filterwarnings('ignore')

from samffr.retrieve_matching_ob_dc import RetrieveMatchingOBDC

DEBUG = True

if DEBUG:
	TOP_FOLDER = "/Users/j35/HFIR/CG1D"
else:
	TOP_FOLDER = "/HFIR/CG1D"

LOG_EXTENSION = "_autoreduce.log"


def main(args):

	# parsing arguments
	ipts_number = args.ipts_number
	input_folder = args.input_folder

	ipts_folder = os.path.join(TOP_FOLDER, f"IPTS-{ipts_number}")
	raw_folder = os.path.join(ipts_folder, 'raw')
	reduction_log_folder = os.path.join(ipts_folder, "shared/autoreduce/reduction_log")
	log_file_name = os.path.join(reduction_log_folder, os.path.basename(input_folder) + LOG_EXTENSION)

	roi_xmin = args.roi_xmin if args.roi_xmin else None
	roi_ymin = args.roi_ymin if args.roi_ymin else None
	roi_xmax = args.roi_xmax if args.roi_xmax else None
	roi_ymax = args.roi_ymax if args.roi_ymax else None
	roi = [roi_xmin, roi_ymin, roi_xmax, roi_ymax]

	maximum_number_of_obs_to_use = args.maximum_number_of_obs if args.maximum_number_of_obs else None
	maximum_time_difference_between_sample_and_ob_acquisition = \
		args.maximum_time_difference_between_sample_and_ob_acquisition if \
			args.maximum_time_difference_between_sample_and_ob_acquisition else None

	print(f"LOG_FILE_NAME: {log_file_name}")
	logging.basicConfig(filename=log_file_name,
						filemode='w',
						format='[%(levelname)s] - %(asctime)s - %(message)s',
						level=logging.INFO)
	logger = logging.getLogger("rockit")
	logger.info("*** Starting a new auto-reconstruction ***")
	logger.info(f"IPTS: {ipts_number}")
	logger.info(f"input_folder: {input_folder}")
	logger.info(f"roi_xmin: {roi_xmin}")
	logger.info(f"roi_ymin: {roi_ymin}")
	logger.info(f"roi_xmax: {roi_xmax}")
	logger.info(f"roi_ymax: {roi_ymax}")
	logger.info(f"max_number_of_obs_to_use: {maximum_number_of_obs_to_use}")
	logger.info(f"maximum_time_difference_between_sample_and_ob_acquisition (mn): "
				f"{maximum_time_difference_between_sample_and_ob_acquisition}")

	# checking that input folder exists
	if not os.path.exists(input_folder):
		logger.info(f"ERROR: input folder does not exists!")
		logger.info(f"Exiting rockit!")
		exit(0)

	logger.info(f"Checking if input folder exists .... True!")

	# using input folder name, locate the ob and df that match it
	list_sample_data = glob.glob(os.path.join(input_folder, "*.tif*"))
	nbr_tiff_files = len(list_sample_data)
	logger.info(f"Found {nbr_tiff_files} tiff files in input folder.")

	if nbr_tiff_files == 0:
		logger.info(f"Input folder is empty. Leaving rockit now!")
		exit(0)

	logger.info(f"Looking for matching OB and DC!")
	logger.info(f"- raw_folder: {raw_folder}")
	o_main = RetrieveMatchingOBDC(list_sample_data=list_sample_data,
								  IPTS_folder=raw_folder,
								  maximum_number_of_files_to_use=maximum_number_of_obs_to_use,
								  maximum_time_offset_mn= maximum_time_difference_between_sample_and_ob_acquisition)
	o_main.run()

	list_ob = o_main.get_matching_ob()
	list_dc = o_main.get_matching_dc()

	logger.info(f"- found {len(list_ob)} matching OB!")
	logger.info(f"- found {len(list_dc)} matching DC!")

	# build script to run yuxuan's code

	# projections
	print("loading projections")
	ct_name, ang_deg, theta, ind_list = get_ind_list(os.listdir(input_folder))
	proj180_ind = find_proj180_ind(ang_deg)[0]
	logger.info(f"- Found index of 180 degree projections: {proj180_ind}")
	logger.info(f"Loading projections ....")
	proj = read_tiff_stack(fdir=input_folder, fname=ct_name)
	logger.info(f"Loading CT projections .... Done!")

	# ob
	print("loading ob")
	logger.info(f"Loading OB ....")
	ob = read_tiff_from_full_name_list(list_ob)
	logger.info(f"Loading OB .... Done!")

	# dc
	print("loading dc")
	logger.info(f"Loading DC ...")
	dc = read_tiff_from_full_name_list(list_dc)
	logger.info(f"Loading DC ... Done!")

	# detect and crop the slits
	print("detecting and cropping the slits")
	logger.info(f"Detecting and cropping the slits ....")
	slit_box_corners = find_slits_corners_aps_1id(img=ob[0], method='simple')
	proj = remove_slits_aps_1id(proj, slit_box_corners)
	ob = remove_slits_aps_1id(ob, slit_box_corners)
	dc = remove_slits_aps_1id(dc, slit_box_corners)
	logger.info(f"Detecting and cropping the slits .... Done!")

	# Define the ROI
	print("Cropping sample")
	logger.info(f"cropping data ...")
	if roi == [None, None, None, None]:
		logger.info(f"-> nothing to crop!")
		proj_crop = proj
		ob_crop = ob
		dc_crop = dc
	else:
		[height, width] = np.shape(proj[0])
		xmin = roi[0] if roi[0] else 0
		ymin = roi[1] if roi[1] else 0
		xmax = roi[2] if roi[2] else width-1
		ymax = roi[3] if roi[3] else height-1
		logger.info(f"-> cropping using xmin:{xmin}, ymin:{ymin}, xmax:{xmax}, ymax:{ymax}")
		roi_corners = set_roi(corners=slit_box_corners, xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
		logger.info(f"- corners detected are {roi_corners}")
		proj_crop = remove_slits_aps_1id(proj, roi_corners)
		ob_crop = remove_slits_aps_1id(ob, roi_corners)
		dc_crop = remove_slits_aps_1id(dc, roi_corners)
	logger.info(f"cropping data ... Done!")

	# Remove outliers
	print("remove outliers")
	logger.info(f"removing outliers ...")
	logger.info(f"- parameter used: 50")
	proj_crop = remove_outlier(proj_crop, 50)
	logger.info(f"removing outliers ... Done!")

	# Normalization
	print("normalization")
	logger.info(f"Normalization ...")
	proj_norm = normalize(proj_crop, ob_crop, dc_crop)
	logger.info(f"Normalization ... Done!")

	# beam fluctuation correction
	print(f"beam fluctuation")
	logger.info(f"Beam fluctuation ....")
	logger.info(f"- air: 50")
	proj_norm = normalize_bg(proj_norm, air=50)
	logger.info(f"Beam fluctuation .... Done!")

	# minus log conversion
	print("minus log conversion")
	logger.info(f"minus log conversion ...")
	proj_mlog = minus_log(proj_norm)
	logger.info(f"minus log conversion ... Done!")

	# ring artifact removal
	print("ring artifact removal")
	logger.info(f"ring artifact removal")
	proj_rmv = remove_all_stripe(proj_mlog)
	logger.info(f"ring artifact removal ... Done!")

	# find and correct tilt
	print(f"find and correct tilt")
	logger.info(f"find and correct tilt")
	tilt_ang = tilt.calculate_tilt(image0=proj_rmv[0], image180=proj_rmv[proj180_ind])
	logger.info(f"- tilt angle: {tilt_ang.x}")
	proj_tilt = tilt.apply_tilt_correction(proj_rmv, tilt_ang.x)
	logger.info(f"find and correct tilt ... Done!")

	# find center of rotation
	print(f"center of rotation")
	logger.info(f"center of rotation")
	rot_center = find_center_pc(np.squeeze(proj_tilt[0, :, :]),
					     		np.squeeze(proj_tilt[proj180_ind, :, :]), tol=0.5)
	logger.info(f"center of rotation ... Done!")

	# reconstruction
	print(f"reconstruction")
	logger.info(f"reconstruction")
	recon = reconstruction(proj_tilt, theta, center=rot_center, algorithm='gridrec', sinogram_order=False)
	recon = circ_mask(recon, axis=0, ratio=0.95)
	logger.info(f"reconstruction ... done")

	# exporting the reconstructed slices
	print(f"exporting the reconstructed slices")
	base_input_folder_name = os.path.basename(input_folder)
	output_folder = f"{TOP_FOLDER}/IPTS-{ipts_number}/shared/autoreduce/{base_input_folder_name}/"
	if os.path.exists(output_folder):
		shutil.rmtree(output_folder)
	os.makedirs(output_folder)

	logger.info(f"exporting the slices to {output_folder}")
	dxchange.write_tiff_stack(recon, fname=output_folder + 'reconstruction', overwrite=True)
	logger.info(f"exporting the slices ... Done!")

	# # moving log file to output folder
	# logger.info(f"moving log file to output folder")
	# print(f"moving log from {log_file_name} to {output_folder}")
	# shutil.move(log_file_name, os.path.join(output_folder))


if __name__ == "__main__":

	parser = argparse.ArgumentParser(description="""
	Reconstruct a set of projections from a given folder,

	example:
		python rockit/rockit_cli 27158 input_folder_name -roi_xmin 250 -roi_ymin 600 -roi_xmax 1250 -roi_ymax 1300
	""",
									 formatter_class=argparse.RawDescriptionHelpFormatter,
									 epilog="NB: the input folder name is mandatory")

	parser.add_argument('ipts_number',
						help='IPTS of current experiment')
	parser.add_argument('input_folder',
						help='folder containing the projections')
	parser.add_argument('-roi_xmin',
						type=int,
						help='xmin ROI to crop')
	parser.add_argument('-roi_ymin',
						type=int,
						help='ymin ROI to crop')
	parser.add_argument('-roi_xmax',
						type=int,
						help='xmax ROI to crop')
	parser.add_argument('-roi_ymax',
						type=int,
						help='ymax ROI to crop')
	parser.add_argument('-maximum_number_of_obs',
						type=int,
						help='Maximum number of OBs to use')
	parser.add_argument('-maximum_time_difference_between_sample_and_ob_acquisition',
						type=int,
						help='Maximum time in minutes allowed between a sample and ob acquisition')

	args = parser.parse_args()

	main(args)
