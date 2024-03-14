import argparse
import logging
import os
import glob
import subprocess
from datetime import datetime
import subprocess
from pathlib import Path

from utilites import load_json, save_json, replace_value_of_tags, create_json_config_file_name

import warnings

warnings.filterwarnings('ignore')

from samffr.retrieve_matching_ob_dc import RetrieveMatchingOBDC

DEBUG = False
SUCCESSFUL_MESSAGE = "RECONSTRUCTION LAUNCHED!"


if DEBUG:
    TOP_FOLDER = "/Users/j35/HFIR/CG1D"
else:
    TOP_FOLDER = "/HFIR/CG1D"

LOG_EXTENSION = "_autoreduce.log"
METADATA_JSON = "_sample_ob_dc_metadata.json"
IMARS3D_CONFIG_JSON = "imars3d_config.json"

if DEBUG:
    IMARS3D_JSON_TEMPLATE = "/Users/j35/HFIR/CG1D/shared/autoreduce/imars3d_reconstruction_config.json"
else:
    IMARS3D_JSON_TEMPLATE = "/HFIR/CG1D/shared/autoreduce/imars3d_reconstruction_config.json"


def main(args):

    # parsing arguments
    ipts_number = args.ipts_number
    input_folder = args.input_folder

    ipts_folder = os.path.join(TOP_FOLDER, f"IPTS-{ipts_number}")
    raw_folder = os.path.join(ipts_folder, 'raw')
    reduction_log_folder = os.path.join(ipts_folder, "shared/autoreduce/reduction_log")
    log_file_name = os.path.join(reduction_log_folder, os.path.basename(input_folder) + LOG_EXTENSION)
    sample_ob_dc_metadata_json = os.path.join(reduction_log_folder, os.path.basename(input_folder) + METADATA_JSON)

    roi_xmin = args.roi_xmin if args.roi_xmin else None
    roi_ymin = args.roi_ymin if args.roi_ymin else None
    roi_xmax = args.roi_xmax if args.roi_xmax else None
    roi_ymax = args.roi_ymax if args.roi_ymax else None
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

    # now we need to create the imars3d json config file
    ipts = f"IPTS-{ipts_number}"
    name = os.path.basename(input_folder)
    outputdir = f"{TOP_FOLDER}/IPTS-{ipts_number}/shared/autoreduce/{name}/"
    ct_dir = input_folder
    ob_files = list_ob
    dc_files = list_dc
    crop_limit = [roi_xmin, roi_xmax, roi_ymin, roi_ymax]
    ct_fnmatch = ob_fnmatch = dc_fnmatch = "*.tiff"

    json_template_loaded = load_json(IMARS3D_JSON_TEMPLATE)

    json_template_loaded['ipts'] = ipts
    json_template_loaded['name'] = name
    json_template_loaded['outputdir'] = outputdir
    json_template_loaded['tasks'][0]['inputs'] = {'ct_dir': ct_dir,
                                                  'ob_files': ob_files,
                                                  'dc_files': dc_files,
                                                  'ct_fnmatch': ct_fnmatch,
                                                  'ob_fnmatch': ob_fnmatch,
                                                  'dc_fnmatch': dc_fnmatch}
    json_template_loaded['log_file_name'] = log_file_name

    # put crop limit everywhere there is 'crop_limit'
    replace_value_of_tags(json_template_loaded, 'crop_limit', crop_limit)

    full_process_start_time = datetime.now()
    logger.info(f"Launching the imars3D command line")

    # save the json imars3d config file shared/autoreduce/ folder
    json_config_file_name = create_json_config_file_name(output_folder=outputdir,
                                                         name=name)
    save_json(json_config_file_name, json_template_loaded)

    cmd = f"source /opt/anaconda/etc/profile.d/conda.sh; conda activate imars3d; python -m imarsd3d.backend {json_config_file_name}"
    logger.info(f"About to run {cmd =}")
    cmd += f"; 'Done!' >> {log_file_name}"
    proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, universal_newlines=True)
    proc.communicate()
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
