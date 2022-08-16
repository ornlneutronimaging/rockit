import argparse
import logging
import os
import glob
import tomopy
# import math
# import dxchange
# import numpy as np
import bm3d_streak_removal as bm3d_rmv
from imars3dv2.filters import tilt
from utilites import get_ind_list, find_proj180_ind, read_tiff_stack, read_tiff_from_full_name_list, set_roi

from samffr.retrieve_matching_ob_dc import RetrieveMatchingOBDC


#LOG_FILE_NAME = "/HFIR/CG1D/shared/autoreduce/rockit.log"
LOG_FILE_NAME = "/Users/j35/Desktop/rockit.log"

# TOP_FOLDER = "/HFIR/CG1D"
TOP_FOLDER = "/Users/j35/IPTS/HFIR/CG1D"

parser = argparse.ArgumentParser(description="""
Reconstruct a set of projections from a given folder,

example:
	python rockit/rockit_cli 27158 input_folder_name --roi=(250, 600, 1250, 1300)
""",
								 formatter_class=argparse.RawDescriptionHelpFormatter,
								 epilog="NB: the input folder name is mandatory")

parser.add_argument('ipts_number',
					help='IPTS of current experiment')
parser.add_argument('input_folder',
					help='folder containing the projections')
parser.add_argument('--roi',
					type=list,
					help='ROI to crop (xmin, ymin, xmax, ymax)')

args = parser.parse_args()

# parsing arguments
ipts_number = args.ipts_number
input_folder = args.input_folder

logging.basicConfig(filename=LOG_FILE_NAME,
					filemode='a',
					format='[%(levelname)s] - %(asctime)s - %(message)s',
					level=logging.INFO)
logger = logging.getLogger("rockit")
logger.info("*** Starting a new auto-reconstruction ***")
logger.info(f"IPTS: {ipts_number}")
logger.info(f"input_folder: {input_folder}")

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
ipts_folder = os.path.join(TOP_FOLDER, f"IPTS-{ipts_number}/raw/")
logger.info(f"- ipts_folder: {ipts_folder}")
o_main = RetrieveMatchingOBDC(list_sample_data=list_sample_data,
             				  IPTS_folder=ipts_folder)
o_main.run()

list_ob = o_main.get_matching_ob()
list_dc = o_main.get_matching_dc()

logger.info(f"- found {len(list_ob)} matching OB!")
logger.info(f"- found {len(list_dc)} matching DC!")

# build script to run yuxuan's code

# # projections
# ct_name, ang_deg, theta, ind_list = get_ind_list(os.listdir(input_folder))
# proj180_ind = find_proj180_ind(ang_deg)[0]
# logger.info(f"- Found index of 180 degree projections: {proj180_ind}")
# logger.info(f"Loading projections ....")
# proj = read_tiff_stack(fdir=input_folder, fname=ct_name)
# logger.info(f"Loading CT projections .... Done!")
#
# # ob
# logger.info(f"Loading OB ....")
# ob = read_tiff_from_full_name_list(list_ob)
# logger.info(f"Loading OB .... Done!")
#
# # dc
# logger.info(f"Loading DC ...")
# dc = read_tiff_from_full_name_list(list_dc)
# logger.info(f"Loading DC ... Done!")
#
# # detect and crop the slits
# logger.info(f"Detecting and cropping the slits ....")
# slit_box_corners = tomopy.prep.alignment.find_slits_corners_aps_1id(img=ob[0], method='simple')
# proj = tomopy.prep.alignment.remove_slits_aps_1id(proj, slit_box_corners)
# ob = tomopy.prep.alignment.remove_slits_aps_1id(ob, slit_box_corners)
# dc = tomopy.prep.alignment.remove_slits_aps_1id(dc, slit_box_corners)
# logger.info(f"Detecting and cropping the slits .... Done!")
#
# # Define the ROI
# roi_corners = set_roi(corners=slit_box_corners, xmin=250, ymin=600, xmax=1250, ymax=1300)
# proj_crop = tomopy.prep.alignment.remove_slits_aps_1id(proj, roi_corners)
# ob_crop = tomopy.prep.alignment.remove_slits_aps_1id(ob, roi_corners)
# dc_crop = tomopy.prep.alignment.remove_slits_aps_1id(dc, roi_corners)
