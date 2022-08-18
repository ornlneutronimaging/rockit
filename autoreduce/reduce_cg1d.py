import os
import yaml
import logging
import glob
import json
import subprocess

DEBUG = False

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

CMD = "python " + os.path.join(CMD_FOLDER, "rockit_cli.py")


def main():

	logging.info(f"HOME_FOLDER: {HOME_FOLDER}")
	logging.info(f"IPTS_FOLDER: {IPTS_FOLDER}")
	logging.info(f"CMD_FOLDER: {CMD_FOLDER}")

	if not os.path.exists(CONFIG_FILE):
		logging.info(f"config file {CONFIG_FILE} does not exist!")
		logging.info(f"... Exiting auto-reconstruction!")
		return False

	with open(CONFIG_FILE, 'r') as stream:
		yml_file = yaml.safe_load(stream)

	ipts = yml_file['DataPath']['ipts']
	logging.info(f"> IPTS: {ipts}")

	ipts_folder = f"{IPTS_FOLDER}IPTS-{ipts}"
	logging.info(f"input_folder: {ipts_folder}")
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
	logging.info(f"-> {len(list_dir)} files/folders were located")
	for _file_dir in list_file_dir:
		if os.path.isdir(_file_dir):
			list_dir.append(_file_dir)
	for _dir in list_dir:
		logging.info(f"--> {os.path.basename(_dir)}")

	json_file = os.path.join(ipts_folder, "/shared/autoreduce/")
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
	for _folder in list_dir:
		if not (_folder in list_folders_previously_loaded):
			logging.info(f"{_folder} is a new folder")
			if is_folder_incomplete(_folder):
				logging.info(f"-> this folder is not complete! Exit now!")
				logging.info(f"... Exiting auto-reconstruction!")
				return
			list_new_folders.append(_folder)

	# update tmp file with new list of folders
	config = {'list_folders': list_dir}
	with open(json_file, 'w') as f:
		json.dump(config, f)

	# # retrieve the list of tiff files in the new folders and for each, launch a reconstruction
	for _folder in list_new_folders:
		cmd = f"{CMD} {ipts} {_folder}"
		logging.info(f"> running {cmd}")
		print(f"{cmd}")
		proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, universal_newlines=True)
		proc.communicate()


def is_folder_incomplete(folder):
	return False    # for now, let's consider the folder always complete!


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
