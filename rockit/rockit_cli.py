import argparse
import logging
import os
import glob

from samffr.retrieve_matching_ob_dc import RetrieveMatchingOBDC


#LOG_FILE_NAME = "/HFIR/CG1D/shared/autoreduce/rockit.log"
LOG_FILE_NAME = "/Users/j35/Desktop/rockit.log"

# TOP_FOLDER = "/HFIR/CG1D"
TOP_FOLDER = "/Users/j35/IPTS/HFIR/CG1D"

parser = argparse.ArgumentParser(description="""
Reconstruct a set of projections from a given folder,

example:
	python rockit/rockit_cli 27158 input_folder_name	
""",
								 formatter_class=argparse.RawDescriptionHelpFormatter,
								 epilog="NB: the input folder name is mandatory")

parser.add_argument('ipts_number',
					help='IPTS of current experiment')
parser.add_argument('input_folder',
					help='folder containing the projections')

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
list_sample_data = glob.glob(input_folder + "*.tif*")
nbr_tiff_files = len(list_sample_data)
logger.info(f"Found {nbr_tiff_files} tiff files in input folder.")

if nbr_tiff_files == 0:
	logger.info(f"Input folder is empty. Leaving rockit now!")
	exit(0)

ipts_folder = os.path.join(TOP_FOLDER, f"IPTS-{ipts_number}")
o_main = RetrieveMatchingOBDC(list_sample_data=list_sample_data,
             				  IPTS_folder=ipts_folder)
o_main.run()

# build script to run yuxuan's code





