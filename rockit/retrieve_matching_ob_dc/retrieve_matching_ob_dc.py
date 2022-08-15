import os
from retrieve_matching_ob_dc.file_handler import get_list_of_all_files_in_subfolders
from retrieve_matching_ob_dc.metadata_handler import MetadataHandler
from enum import Enum
import numpy as np
import collections

LIST_METADATA_NOT_INSTRUMENT_RELATED = ['filename', 'time_stamp', 'time_stamp_user_format']
METADATA_ERROR_ALLOWED = 1


class MetadataName(Enum):
    EXPOSURE_TIME = 65027
    DETECTOR_MANUFACTURER = 65026
    APERTURE_HR = 65068
    APERTURE_HL = 65070
    APERTURE_VT = 65066
    APERTURE_VB = 65064

    def __str__(self):
        return self.value


METADATA_KEYS = {'ob' : [MetadataName.EXPOSURE_TIME,
                         MetadataName.DETECTOR_MANUFACTURER,
                         MetadataName.APERTURE_HR,
                         MetadataName.APERTURE_HL,
                         MetadataName.APERTURE_VT,
                         MetadataName.APERTURE_VB],
                 'dc' : [MetadataName.EXPOSURE_TIME,
                         MetadataName.DETECTOR_MANUFACTURER],
                 'all': [MetadataName.EXPOSURE_TIME,
                         MetadataName.DETECTOR_MANUFACTURER,
                         MetadataName.APERTURE_HR,
                         MetadataName.APERTURE_HL,
                         MetadataName.APERTURE_VT,
                         MetadataName.APERTURE_VB]}


class RetrieveMatchingOBDC:

    def __init__(self, list_sample_data=None, IPTS_folder=None):
        self.list_sample_data = list_sample_data
        self.IPTS_folder = IPTS_folder

    def run(self):
        self.retrieve_sample_metadata()
        self.retrieve_ob_metadata()
        self.retrieve_dc_metadata()
        self.create_master_sample_dict()
        self.match_ob()
        self.match_dc()

    def get_matching_ob(self):
        return self.get_matching_data_file(data_type='ob')

    def get_matching_dc(self):
        return self.get_matching_data_file(data_type='dc')

    def retrieve_sample_metadata(self):
        self.sample_metadata_dict = MetadataHandler.retrieve_metadata(list_of_files=self.list_sample_data,
                                                                      display_infos=False,
                                                                      label='sample')

    def retrieve_ob_metadata(self):
        self.ob_metadata_dict = RetrieveMatchingOBDC.auto_retrieve_metadata(self.IPTS_folder,
                                                                            data_type='ob')

    def retrieve_dc_metadata(self):
        self.dc_metadata_dict = RetrieveMatchingOBDC.auto_retrieve_metadata(self.IPTS_folder,
                                                                            data_type=['df', 'dc'])

    def auto_retrieve_metadata(working_dir, data_type='ob'):
        if type(data_type) is list:
            folder = [os.path.join(working_dir, _data_type) for _data_type in data_type]
        else:
            folder = os.path.join(working_dir, data_type)
        list_of_ob_files = get_list_of_all_files_in_subfolders(folder=folder,
                                                               extensions=['tiff', 'tif'])
        metadata_dict = MetadataHandler.retrieve_metadata(list_of_files=list_of_ob_files,
                                                          label=data_type)
        return metadata_dict

    def match_ob(self):
        """we will go through all the ob and associate them with the right sample based on
        - acquisition time
        - detector type
        - aperture
        """
        list_ob_dict = self.ob_metadata_dict
        final_full_master_dict = self.final_full_master_dict
        list_of_sample_acquisition = final_full_master_dict.keys()

        for _index_ob in list_ob_dict.keys():
            _all_ob_instrument_metadata = RetrieveMatchingOBDC.get_instrument_metadata_only(list_ob_dict[_index_ob])
            _ob_instrument_metadata = RetrieveMatchingOBDC.isolate_instrument_metadata(
                    _all_ob_instrument_metadata)
            _acquisition_time = _all_ob_instrument_metadata[MetadataName.EXPOSURE_TIME.value]['value']
            if _acquisition_time in list_of_sample_acquisition:
                for _config_id in final_full_master_dict[_acquisition_time].keys():
                    _sample_metadata_infos = final_full_master_dict[_acquisition_time][_config_id]['metadata_infos']
                    if RetrieveMatchingOBDC.all_metadata_match(_sample_metadata_infos, _ob_instrument_metadata):
                        final_full_master_dict[_acquisition_time][_config_id]['list_ob'].append(list_ob_dict[_index_ob])

        self.final_full_master_dict = final_full_master_dict

    def match_dc(self):
        """
        we will go through all the dc of the IPTS and will associate the dc with the right samples
        based on:
        - detector type used
        - acquisition time
        """
        list_dc_dict = self.dc_metadata_dict
        final_full_master_dict = self.final_full_master_dict
        list_of_sample_acquisition = final_full_master_dict.keys()

        for _index_dc in list_dc_dict.keys():
            _all_dc_instrument_metadata = RetrieveMatchingOBDC.get_instrument_metadata_only(list_dc_dict[_index_dc])
            _dc_instrument_metadata = RetrieveMatchingOBDC.isolate_instrument_metadata(
                    _all_dc_instrument_metadata)
            _acquisition_time = _all_dc_instrument_metadata[MetadataName.EXPOSURE_TIME.value]['value']

            if _acquisition_time in list_of_sample_acquisition:
                for _config_id in final_full_master_dict[_acquisition_time].keys():
                    _sample_metadata_infos = final_full_master_dict[_acquisition_time][_config_id]['metadata_infos']

                    if RetrieveMatchingOBDC.all_metadata_match(_sample_metadata_infos, _dc_instrument_metadata,
                                                               list_key_to_check=[METADATA_KEYS['dc'][
                                                                           1].value]):
                        final_full_master_dict[_acquisition_time][_config_id]['list_dc'].append(list_dc_dict[
                                                                                                    _index_dc])

        self.final_full_master_dict = final_full_master_dict

    @staticmethod
    def get_instrument_metadata_only(metadata_dict):
        _clean_dict = {}
        for _key in metadata_dict.keys():
            if not _key in LIST_METADATA_NOT_INSTRUMENT_RELATED:
                _clean_dict[_key] = metadata_dict[_key]
        return _clean_dict

    @staticmethod
    def isolate_instrument_metadata(dictionary):
        """create a dictionary of all the instrument metadata without the acquisition time"""
        isolated_dictionary = {}
        for _key in dictionary.keys():
            if _key == MetadataName.EXPOSURE_TIME:
                continue
            isolated_dictionary[_key] = dictionary[_key]
        return isolated_dictionary

    @staticmethod
    def all_metadata_match(metadata_1={}, metadata_2={}, list_key_to_check=None):
        list_key = metadata_1.keys() if list_key_to_check is None else list_key_to_check

        for _key in list_key:
            try:
                if np.abs(np.float(
                        metadata_1[_key]['value']) - np.float(metadata_2[_key]['value'])) > METADATA_ERROR_ALLOWED:
                    return False
            except ValueError:
                if metadata_1[_key]['value'] != metadata_2[_key]['value']:
                    return False
        return True

    def create_master_sample_dict(self):
        final_full_master_dict = collections.OrderedDict()
        sample_metadata_dict = self.sample_metadata_dict

        # we need to keep record of which image was the first one taken and which image was the last one taken
        first_sample_image = sample_metadata_dict[0]
        last_sample_image = sample_metadata_dict[0]

        for _file_index in sample_metadata_dict.keys():

            _dict_file_index = sample_metadata_dict[_file_index]
            _sample_file = _dict_file_index['filename']

            _acquisition_time = _dict_file_index[MetadataName.EXPOSURE_TIME.value]['value']
            _instrument_metadata = RetrieveMatchingOBDC.isolate_instrument_metadata(_dict_file_index)
            _sample_time_stamp = _dict_file_index['time_stamp']

            # find which image was first and which image was last
            if _sample_time_stamp < first_sample_image['time_stamp']:
                first_sample_image = _dict_file_index
            elif _sample_time_stamp > last_sample_image['time_stamp']:
                last_sample_image = _dict_file_index

            # first entry or first time seeing that acquisition time
            if (len(final_full_master_dict) == 0) or not (_acquisition_time in final_full_master_dict.keys()):
                _first_images_dict = {'sample': first_sample_image,
                                      'ob'    : {},
                                      'dc'    : {}}
                _last_images_dict = {'sample': last_sample_image,
                                     'ob'    : {},
                                     'dc'    : {}}
                _temp_dict = {'list_sample'          : [_dict_file_index],
                              'first_images'         : _first_images_dict,
                              'last_images'          : _last_images_dict,
                              'list_ob'              : [],
                              'list_dc'              : [],
                              'time_range_s_selected': {'before': np.NaN,
                                                        'after' : np.NaN},
                              'time_range_s'         : {'before': np.NaN,
                                                        'after' : np.NaN},
                              'metadata_infos'       : RetrieveMatchingOBDC.get_instrument_metadata_only(
                                      _instrument_metadata)}
                final_full_master_dict[_acquisition_time] = {}
                final_full_master_dict[_acquisition_time]['config0'] = _temp_dict
            else:
                # check that all the metadata_infos match for the first group of that acquisition time,
                # otherwise check the next one or create a group
                if _acquisition_time in final_full_master_dict.keys():
                    _dict_for_this_acquisition_time = final_full_master_dict[_acquisition_time]
                    _found_a_match = False
                    for _config_key in _dict_for_this_acquisition_time.keys():
                        _config = _dict_for_this_acquisition_time[_config_key]
                        if (RetrieveMatchingOBDC.all_metadata_match(metadata_1=_config['metadata_infos'],
                                                                    metadata_2=_instrument_metadata)):
                            _config['list_sample'].append(_dict_file_index)

                            _first_images_dict = {'sample': first_sample_image,
                                                  'ob'    : {},
                                                  'dc'    : {}}
                            _last_images_dict = {'sample': last_sample_image,
                                                 'ob'    : {},
                                                 'dc'    : {}}

                            _config['first_images'] = _first_images_dict
                            _config['last_images'] = _last_images_dict
                            _found_a_match = True

                    if not _found_a_match:
                        _first_images_dict = {'sample': first_sample_image,
                                              'ob'    : {},
                                              'dc'    : {}}
                        _last_images_dict = {'sample': last_sample_image,
                                             'ob'    : {},
                                             'dc'    : {}}

                        _temp_dict = {'list_sample'          : [_dict_file_index],
                                      'first_images'         : _first_images_dict,
                                      'last_images'          : _last_images_dict,
                                      'list_ob'              : [],
                                      'list_dc'              : [],
                                      'time_range_s_selected': {'before': np.NaN,
                                                                'after' : np.NaN},
                                      'time_range_s'         : {'before': np.NaN,
                                                                'after' : np.NaN},
                                      'metadata_infos'       : RetrieveMatchingOBDC.get_instrument_metadata_only(
                                              _instrument_metadata)}
                        nbr_config = len(_dict_for_this_acquisition_time.keys())
                        _dict_for_this_acquisition_time['config{}'.format(nbr_config)] = _temp_dict

                else:
                    _first_images_dict = {'sample': first_sample_image,
                                          'ob'    : {},
                                          'dc'    : {}}
                    _last_images_dict = {'sample': last_sample_image,
                                         'ob'    : {},
                                         'dc'    : {}}

                    _temp_dict = {'list_sample'          : [_dict_file_index],
                                  'first_images'         : _first_images_dict,
                                  'last_images'          : _last_images_dict,
                                  'list_ob'              : [],
                                  'list_dc'              : [],
                                  'time_range_s_selected': {'before': np.NAN,
                                                            'after' : np.NaN},
                                  'time_range_s'         : {'before': np.NaN,
                                                            'after' : np.NaN},
                                  'metadata_infos'       : RetrieveMatchingOBDC.get_instrument_metadata_only(
                                          _instrument_metadata)}
                    final_full_master_dict[_acquisition_time] = {}
                    final_full_master_dict[_acquisition_time]['config0'] = _temp_dict

        self.final_full_master_dict = final_full_master_dict

    def get_matching_data_file(self, data_type='ob'):

        key = f"list_{data_type}"

        final_full_master_dict = self.final_full_master_dict

        list_acquisition_time_keys = list(final_full_master_dict.keys())
        first_acquisition_time_key = list_acquisition_time_keys[0]

        list_config = list(final_full_master_dict[first_acquisition_time_key].keys())
        first_config = list_config[0]

        list_data = []
        for _data in final_full_master_dict[first_acquisition_time_key][first_config][key]:
            list_data.append(_data['filename'])

        return list_data
