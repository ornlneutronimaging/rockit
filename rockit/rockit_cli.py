import argparse
import json
import logging
import os
import glob
import shutil
from datetime import datetime
import pathlib

import dxchange
from tomopy import find_center_pc, circ_mask, normalize, minus_log
import tomopy.recon as reconstruction
from tomopy.prep.alignment import find_slits_corners_aps_1id, remove_slits_aps_1id
from tomopy.misc.corr import remove_outlier
from tomopy.prep.normalize import normalize_bg
from tomopy.prep.stripe import remove_all_stripe

import numpy as np
import bm3d_streak_removal as bm3d_rmv
from imars3d.backend.diagnostics import tilt
from utilites import get_ind_list, find_proj180_ind, read_tiff_stack, read_tiff_from_full_name_list, set_roi

import warnings

warnings.filterwarnings('ignore')

from samffr.retrieve_matching_ob_dc import RetrieveMatchingOBDC

DEBUG = False
SUCCESSFUL_MESSAGE = "RECONSTRUCTION WAS SUCCESSFUL!"


if DEBUG:
    TOP_FOLDER = "/Users/j35/HFIR/CG1D"
else:
    TOP_FOLDER = "/HFIR/CG1D"

LOG_EXTENSION = "_autoreduce.log"
METADATA_JSON = "_sample_ob_dc_metadata.json"


def main(args):

    full_process_start_time = datetime.now()

    # parsing arguments
    ipts_number = args.ipts_number
    input_folder = args.input_folder

    ipts_folder = os.path.join(TOP_FOLDER, f"IPTS-{ipts_number}")
    raw_folder = os.path.join(ipts_folder, 'raw')
    reduction_log_folder = os.path.join(ipts_folder, "shared/autoreduce/reduction_log")
    log_file_name = os.path.join(reduction_log_folder, str(pathlib.Path(input_folder).name) + LOG_EXTENSION)
    sample_ob_dc_metadata_json = os.path.join(reduction_log_folder, str(pathlib.Path(input_folder).name) + METADATA_JSON)

    roi_xmin = args.roi_xmin if args.roi_xmin else None
    roi_ymin = args.roi_ymin if args.roi_ymin else None
    roi_xmax = args.roi_xmax if args.roi_xmax else None
    roi_ymax = args.roi_ymax if args.roi_ymax else None
    roi = [roi_xmin, roi_ymin, roi_xmax, roi_ymax]
    ring_removal = args.ring_removal
    if ring_removal is None:
        ring_removal = True
    automatic_edge_cropping = args.automatic_edge_cropping
    if automatic_edge_cropping is None:
        automatic_edge_cropping = True

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
    logger.info(f"ring_removal: {ring_removal}")
    logger.info(f"automatic_edge_cropping: {automatic_edge_cropping}")

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

    matching_files_start = datetime.now()
    logger.info(f"Looking for matching OB and DC!")
    logger.info(f"- raw_folder: {raw_folder}")
    o_main = RetrieveMatchingOBDC(list_sample_data=list_sample_data,
                                  IPTS_folder=raw_folder,
                                  maximum_number_of_files_to_use=maximum_number_of_obs_to_use,
                                  maximum_time_offset_mn=maximum_time_difference_between_sample_and_ob_acquisition)
    o_main.run()

    list_ob = o_main.get_matching_ob()
    list_dc = o_main.get_matching_dc()

    logger.info(f"- found {len(list_ob)} matching OB!")
    logger.info(f"- found {len(list_dc)} matching DC!")
    matching_files_end = datetime.now()
    logger.info(f"Looking for matching OB and DC took {matching_files_end - matching_files_start}")

    # if no ob or dc found, stop here
    if (len(list_ob) == 0) or (len(list_dc) == 0):
        logger.info(f"Some OB and DC are missing, the reconstruction will stop now!")
        logger.info(f"Consult the sample, ob and dc metadata json file for more information!"
                    f"(found in the same output folder) or by clicking the button >Preview metadata of files ...<")

        # export a sample_ob_dc_metadata.json file that will show the not matching parameters
        sample_metadata_dict = o_main.sample_metadata_dict
        list_key = list(sample_metadata_dict.keys())
        first_sample_metadata_dict = sample_metadata_dict[list_key[0]]

        ob_metadata_dict = o_main.ob_metadata_dict
        dc_metadata_dict = o_main.dc_metadata_dict

        metadata_dict = {'sample': first_sample_metadata_dict,
                         'ob': ob_metadata_dict,
                         'dc': dc_metadata_dict}

        import json
        with open(sample_ob_dc_metadata_json, 'w') as outfile:
            json.dump(metadata_dict, outfile)

        return

    # build script to run yuxuan's code

    # projections
    loading_projections_start = datetime.now()
    print("loading projections")
    ct_name, ang_deg, theta, ind_list = get_ind_list(os.listdir(input_folder))
    proj180_ind = find_proj180_ind(ang_deg)[0]
    logger.info(f"- Found index of 180 degree projections: {proj180_ind}")
    logger.info(f"Loading projections ....")
    proj = read_tiff_stack(fdir=input_folder, fname=ct_name)
    loading_projections_end = datetime.now()
    logger.info(f"Loading CT projections .... Done in {loading_projections_end - loading_projections_start}")

    # ob
    loading_ob_start = datetime.now()
    print("loading ob")
    logger.info(f"Loading OB ({len(list_ob)} files) ....")
    ob = read_tiff_from_full_name_list(list_ob)
    loading_ob_end = datetime.now()
    logger.info(f"Loading OB .... Done in {loading_ob_end - loading_ob_start}!")

    # dc
    loading_dc_start = datetime.now()
    print("loading dc")
    logger.info(f"Loading DC ({len(list_dc)} files) ...")
    dc = read_tiff_from_full_name_list(list_dc)
    loading_dc_end = datetime.now()
    logger.info(f"Loading DC ... Done in {loading_dc_end - loading_dc_start}!")

    # detect and crop the slits
    if automatic_edge_cropping:
        detect_start = datetime.now()
        print("detecting and cropping the slits")
        logger.info(f"Detecting and cropping the slits ....")
        slit_box_corners = find_slits_corners_aps_1id(img=ob[0], method='simple')
        logger.info(f"-> slit_box_corners: {slit_box_corners}")
        proj = remove_slits_aps_1id(proj, slit_box_corners)
        ob = remove_slits_aps_1id(ob, slit_box_corners)
        dc = remove_slits_aps_1id(dc, slit_box_corners)
        detect_end = datetime.now()
        logger.info(f"Detecting and cropping the slits .... Done in {detect_end - detect_start}!")
    else:
        print("detecting and cropping - SKIPPED")
        logger.info(f"Detecting and cropping the slits is OFF")

    # Define the ROI
    roi_start = datetime.now()
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
        xmax = roi[2] if roi[2] else width - 1
        ymax = roi[3] if roi[3] else height - 1
        logger.info(f"-> cropping using xmin:{xmin}, ymin:{ymin}, xmax:{xmax}, ymax:{ymax}")
        roi_corners = set_roi(corners=slit_box_corners, xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
        logger.info(f"- corners detected are {roi_corners}")
        proj_crop = remove_slits_aps_1id(proj, roi_corners)
        ob_crop = remove_slits_aps_1id(ob, roi_corners)
        dc_crop = remove_slits_aps_1id(dc, roi_corners)
    roi_end = datetime.now()
    logger.info(f"cropping data ... Done in {roi_end - roi_start}!")

    # Remove outliers
    outliers_start = datetime.now()
    print("remove outliers")
    logger.info(f"removing outliers ...")
    logger.info(f"- parameter used: 50")
    proj_crop = remove_outlier(proj_crop, 50)
    outliers_end = datetime.now()
    logger.info(f"removing outliers ... Done in {outliers_end - outliers_start}!")

    # Normalization
    normalization_start = datetime.now()
    print("normalization")
    logger.info(f"Normalization ...")
    proj_norm = normalize(proj_crop, ob_crop, dc_crop)
    normalization_end = datetime.now()
    logger.info(f"Normalization ... Done in {normalization_end - normalization_start}!")

    # beam fluctuation correction
    beam_start = datetime.now()
    print(f"beam fluctuation")
    logger.info(f"Beam fluctuation ....")
    logger.info(f"- air: 50")
    proj_norm = normalize_bg(proj_norm, air=50)
    beam_end = datetime.now()
    logger.info(f"Beam fluctuation .... Done in {beam_end - beam_start}!")

    # minus log conversion
    minus_start = datetime.now()
    print("minus log conversion")
    logger.info(f"minus log conversion ...")
    proj_mlog = minus_log(proj_norm)
    minus_end = datetime.now()
    logger.info(f"minus log conversion ... Done in {minus_end - minus_start}!")

    # ring artifact removal
    ring_start = datetime.now()
    if ring_removal:
        print("ring artifact removal")
        logger.info(f"ring artifact removal using bm3d!")
        proj_bm3d_norm = bm3d_rmv.extreme_streak_attenuation(proj_mlog)
        proj_rmv = bm3d_rmv.multiscale_streak_removal(proj_bm3d_norm)
        # proj_rmv = remove_all_stripe(proj_mlog)
        ring_end = datetime.now()
        logger.info(f"ring artifact removal ... Done in {ring_end - ring_start}!")
    else:
        proj_rmv = proj_mlog
        print("ring artifact removal - SKIPPED")
        logger.info(f"ring artifact removal skipped by user!")

    # find and correct tilt
    tilt_start = datetime.now()
    print(f"find and correct tilt")
    logger.info(f"find and correct tilt")
    tilt_ang = tilt.calculate_tilt(image0=proj_rmv[0], image180=proj_rmv[proj180_ind])
    logger.info(f"- tilt angle: {tilt_ang.x}")
    proj_tilt = tilt.apply_tilt_correction(proj_rmv, tilt_ang.x)
    tilt_end = datetime.now()
    logger.info(f"find and correct tilt ... Done in {tilt_end - tilt_start}!")

    # find center of rotation
    center_start = datetime.now()
    print(f"center of rotation")
    logger.info(f"center of rotation")
    rot_center = find_center_pc(np.squeeze(proj_tilt[0, :, :]),
                                np.squeeze(proj_tilt[proj180_ind, :, :]), tol=0.5)
    center_end = datetime.now()
    logger.info(f"center of rotation ... Done in {center_end - center_start}!")

    # reconstruction
    reconstruction_start = datetime.now()
    print(f"reconstruction")
    logger.info(f"reconstruction")
    recon = reconstruction(proj_tilt, theta, center=rot_center, algorithm='gridrec', sinogram_order=False)
    recon = circ_mask(recon, axis=0, ratio=0.95)
    reconstruction_end = datetime.now()
    logger.info(f"reconstruction ... done in {reconstruction_end - reconstruction_start}!")

    # exporting the reconstructed slices
    export_start = datetime.now()
    print(f"exporting the reconstructed slices")
    base_input_folder_name = os.path.basename(input_folder)
    output_folder = f"{TOP_FOLDER}/IPTS-{ipts_number}/shared/autoreduce/{base_input_folder_name}/"
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder)
    logger.info(f"exporting the slices to {output_folder}")
    dxchange.write_tiff_stack(recon, fname=output_folder + 'reconstruction', overwrite=True)
    export_end = datetime.now()
    logger.info(f"exporting the slices ... Done in {export_end - export_start}!")

    full_process_end_time = datetime.now()
    full_process_delta_time = full_process_end_time - full_process_start_time
    logger.info(f"Full CT reconstruction took {full_process_delta_time}")

    logger.info(f"{SUCCESSFUL_MESSAGE}")


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
    parser.add_argument('--automatic_edge_cropping',
                        # action=argparse.BooleanOptionalAction,
                        action="store_true",
                        help="activate or not the automatic edge cropping ")
    parser.add_argument('--ring_removal',
                        action="store_true",
                        # action=argparse.BooleanOptionalAction,
                        help="Activate or not the ring removal algorithm")
    parser.add_argument('-ring_removal_algorithm',
                        type=str,
                        help="Name of the ring removal algorithm [Vos, bm3d] (default being Vos)")

    args = parser.parse_args()

    main(args)
