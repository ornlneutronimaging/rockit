import os
import yaml
import logging
import glob
import json
import subprocess
import time
from PIL import Image

DEBUG = False
LOG_FILE_MAX_LINES_NUMBER = 1000

if DEBUG:
	HOME_FOLDER = "/Users/j35/HFIR/CG1D/shared/autoreduce/"
else:
	HOME_FOLDER = "/HFIR/CG1D/shared/autoreduce/"

if DEBUG:
	IPTS_FOLDER = "/Users/j35/HFIR/CG1D/"
else:
	IPTS_FOLDER = "/HFIR/CG1D/"

if DEBUG:
	CMD_FOLDER = "/Users/j35/git/rockit/rockit/"
else:
	CMD_FOLDER = "/SNS/users/j35/git/rockit/rockit/"

CONFIG_FILE = os.path.join(HOME_FOLDER, "autoreduce_cg1d_config.yaml")
JSON_BASENAME = "ct_scans_folder_processed.json"
LOG_FILE = os.path.join(HOME_FOLDER, "reduce_cg1d.log")

CMD = "source /opt/anaconda/etc/profile.d/conda.sh; conda activate /SNS/users/j35/.conda/envs/imars3d_jean; python " + os.path.join(CMD_FOLDER, "rockit_imars3d_cli.py")


def main():

	# clean up log file
	with open(LOG_FILE, 'r') as log_file:
		log_file_content = log_file.readlines()

	if len(log_file_content) > LOG_FILE_MAX_LINES_NUMBER:
		log_file_content = log_file_content[-LOG_FILE_MAX_LINES_NUMBER:]

	with open(LOG_FILE, 'w') as log_file:
		log_file.writelines(log_file_content)

	logging.info(f"HOME_FOLDER: {HOME_FOLDER}")
	logging.info(f"IPTS_FOLDER: {IPTS_FOLDER}")
	logging.info(f"CMD_FOLDER: {CMD_FOLDER}")

	if not os.path.exists(CONFIG_FILE):
		logging.info(f"config file {CONFIG_FILE} does not exist!")
		logging.info(f"... Exiting auto-reconstruction!")
		return False

	with open(CONFIG_FILE, 'r') as stream:
		yml_file = yaml.safe_load(stream)

	autoreduce_flag = yml_file['autoreduction']
	if autoreduce_flag is False:
		logging.info(f"autoreduction is off!")
		logging.info(f"... Exiting auto-reconstruction!")
		return False

	ipts = yml_file['DataPath']['ipts']
	logging.info(f"> IPTS: {ipts}")

	ipts_folder = f"{IPTS_FOLDER}IPTS-{ipts}"
	logging.info(f"ipts_folder: {ipts_folder}")
	if not os.path.exists(ipts_folder):
		logging.info(f"-> IPTS folder does not exist!")
		logging.info(f"... Exiting auto-reconstruction!")
		return False

	logging.info(f"-> IPTS folder has been located!")

	ct_scans_folder = f"{ipts_folder}/raw/ct_scans/"
	if not os.path.exists(ct_scans_folder):
		logging.info(f"-> ct_scans folder does not exist!")
		logging.info(f"... Exiting auto-reconstruction!")
		return False

	# check the input_folder and list all the folders there
	logging.info(f"> Retrieving the list of folders within {ct_scans_folder}!")
	list_file_dir = glob.glob(os.path.join(ct_scans_folder, "*"))
	list_dir = []
	logging.info(f"-> {len(list_file_dir)} files/folders were located")
	for _file_dir in list_file_dir:
		if os.path.isdir(_file_dir):
			list_dir.append(_file_dir)
	for _dir in list_dir:
		logging.info(f"--> {os.path.basename(_dir)}")

	json_file = ipts_folder + "/shared/autoreduce/" + JSON_BASENAME
	logging.info(f"json_file: {json_file}")

	if len(list_dir) == 0:
		logging.info(f"-> 0 folder found. clearing json_file. exit now!")
		if os.path.exists(json_file):
			os.remove(json_file)
		logging.info(f"... Exiting auto-reconstruction!")
		return

	if not os.path.exists(json_file):
		# if first time retrieving folders
		logging.info(f"> First time retrieving folders!")
		list_folders_previously_loaded = []
	else:
		# loading list of folders previously recorded
		with open(json_file) as f:
			config = json.load(f)

		# checking that if we have the same number of folders, we are done here
		list_folders_previously_loaded = config['list_folders']
		if len(list_folders_previously_loaded) == len(list_dir):
			logging.info(f"-> We still have the same number of folders, exit now!")
			logging.info(f"... Exiting auto-reconstruction!")
			return

	# we have at least 1 new folder at this point
	logging.info(f"> We have at least 1 new folder in the output dir!")

	# retrieving the list of new folders
	list_new_folders = []
	acquisition_time_coefficient = yml_file['acquisition_time_coefficient']
	for _folder in list_dir:
		if not (_folder in list_folders_previously_loaded):
			logging.info(f"{_folder} is a new folder")
			if is_folder_incomplete(_folder, acquisition_time_coefficient=acquisition_time_coefficient):
				logging.info(f"-> this folder is not complete! Exit now!")
				logging.info(f"... Exiting auto-reconstruction!")
				continue
			list_new_folders.append(_folder)

	# update tmp file with new list of folders
	config = {'list_folders': list_dir}
	with open(json_file, 'w') as f:
		json.dump(config, f)

	logging.info("Building the command line:")

	# roi
	roi_mode = yml_file['ROI']['mode']
	cmd_roi = ""
	if roi_mode:

		roi_xmax = yml_file['ROI']['xmax']
		if roi_xmax:
			cmd_roi += f" -roi_xmax {roi_xmax}"

		roi_xmin = yml_file['ROI']['xmin']
		if roi_xmin:
			cmd_roi += f" -roi_xmin {roi_xmin}"

		roi_ymin = yml_file['ROI']['ymin']
		if roi_ymin:
			cmd_roi += f" -roi_ymin {roi_ymin}"

		roi_ymax = yml_file['ROI']['ymax']
		if roi_ymax:
			cmd_roi += f" -roi_ymax {roi_ymax}"
	logging.info(f" {cmd_roi =}")

	# ob auto selection
	ob_auto_selection_mode = yml_file['ob_auto_selection']['mode']
	logging.info(f"Debugging ob auto selection!")
	if not ob_auto_selection_mode:
		cmd_ob = ""
		logging.info(f" - without ob_auto_selection_mode !")
	else:
		logging.info(f" - with ob_auto_selection_mode !")
		use_max_number_of_files = yml_file['ob_auto_selection']['use_max_number_of_files']
		logging.info(f"  {use_max_number_of_files =}")
		if use_max_number_of_files:
			max_number_of_ob_files = yml_file['ob_auto_selection']['max_number_of_files']
			cmd_ob = f"-maximum_number_of_obs {max_number_of_ob_files}"
		else:
			ob_days = yml_file['ob_auto_selection']['days']
			ob_minutes = yml_file['ob_auto_selection']['minutes']
			ob_hours = yml_file['ob_auto_selection']['hours']
			ob_minutes = (ob_days * 24 * 60) + ob_minutes + (ob_hours * 60)
			cmd_ob = f"-maximum_time_difference_between_sample_and_ob_acquisition {ob_minutes}"
	logging.info(f" {cmd_ob =}")

	# # retrieve the list of tiff files in the new folders and for each, launch a reconstruction
	for _folder in list_new_folders:
		cmd = f"{CMD} {cmd_ob} {cmd_roi} {ipts} {_folder}"
		logging.info(f"> running {cmd}")
		proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, universal_newlines=True)
		proc.communicate()


def is_folder_incomplete(folder, acquisition_time_coefficient=5):
	"""this is where we are checking that
	current_time_stamp > last_image_time_stamp + coeff * images_acquisition_time
	"""

	# list all tiff from this folder
	list_tiff = glob.glob(os.path.join(folder, "*.tif*"))
	if len(list_tiff) == 0:
		return True

	# sort by name and use the last one
	list_tiff.sort()
	last_image = list_tiff[-1]

	# get time_stamp
	last_image_time_stamp = os.path.getatime(last_image)

	# find out acquisition time for that file

	o_image = Image.open(last_image)
	o_dict = dict(o_image.tag_v2)
	acquisition_metadata = o_dict[65027]
	name, value = acquisition_metadata.split(":")
	acquisition_time = float(value)

	# get current time_stamp
	current_time_stamp = time.time()

	# if (current_time_stamp > last_image_time_stamp + acquisition_time_coefficient * image_acquisition_time)
	#     return False
	# else:
	#     return True
	if current_time_stamp > (last_image_time_stamp + acquisition_time_coefficient * acquisition_time):
		return False
	else:
		logging.info(f"-> current_time_stamp: {current_time_stamp}")
		logging.info(f"-> last_image_time_stamp: {last_image_time_stamp}")
		logging.info(f"-> image_acquisition_time: {acquisition_time}")
		logging.info(f"-> acquisition_time_coefficient: {acquisition_time_coefficient}")
		return True


def read_ascii(file_name):
	with open(file_name, 'r') as f:
		text = f.readlines()
	return text


if __name__ == "__main__":
	logging.basicConfig(filename=LOG_FILE,
						filemode='a',  # 'w'
						format="[%(levelname)s] - %(asctime)s - %(message)s",
						level=logging.INFO)
	logging.info("*** Starting checking for new files - version 1.0")
	main()


# python rockit/rockit_cli.py 23788 /Users/j35/IPTS/HFIR/CG1D/IPTS-23788/raw/ct_scans/Aug24_2020
