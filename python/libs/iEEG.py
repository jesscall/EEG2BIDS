import eeglabio
import os
import mne
import pymatreader
from python.libs import EDF
from mne_bids import write_raw_bids, BIDSPath


class ReadError(PermissionError):
    """Raised when a PermissionError is thrown while reading a file"""
    pass


class WriteError(PermissionError):
    """Raised when a PermissionError is thrown while writing a file"""
    pass


metadata = {
    'eeg': [
        'TaskName',
        'InstitutionName',
        'InstitutionAddress',
        'Manufacturer',
        'ManufacturersModelName',
        'SoftwareVersions',
        'TaskDescription',
        'Instructions',
        'CogAtlasID',
        'CogPOID',
        'DeviceSerialNumber',
        'EEGReference',
        'SamplingFrequency',
        'PowerLineFrequency',
        'SoftwareFilters',
        'CapManufacturer',
        'CapManufacturersModelName',
        'EEGChannelCount',
        'EOGChannelCount',
        'ECGChannelCount',
        'EMGChannelCount',
        'MiscChannelCount',
        'TriggerChannelCount',
        'RecordingDuration',
        'RecordingType',
        'EpochLength',
        'EEGGround',
        'HeadCircumference',
        'EEGPlacementScheme',
        'HardwareFilters',
        'SubjectArtefactDescription',
    ],
    'ieeg': [
        'TaskName',
        'InstitutionName',
        'InstitutionAddress',
        'Manufacturer',
        'ManufacturersModelName',
        'SoftwareVersions',
        'TaskDescription',
        'Instructions',
        'CogAtlasID',
        'CogPOID',
        'DeviceSerialNumber',
        'iEEGReference',
        'SamplingFrequency',
        'PowerLineFrequency',
        'SoftwareFilters',
        'DCOffsetCorrection',
        'HardwareFilters',
        'ElectrodeManufacturer',
        'ElectrodeManufacturersModelName',
        'ECOGChannelCount',
        'SEEGChannelCount',
        'EEGChannelCount',
        'EOGChannelCount',
        'ECGChannelCount',
        'EMGChannelCount',
        'MiscChannelCount',
        'TriggerChannelCount',
        'RecordingDuration',
        'RecordingType',
        'EpochLength',
        'iEEGGround',
        'iEEGPlacementScheme',
        'iEEGElectrodeGroups',
        'SubjectArtefactDescription',
        'ElectricalStimulation',
        'ElectricalStimulationParameters',
    ]
}


# TarFile - tarfile the BIDS data.
class TarFile:
    def __init__(self, bids_directory):
        import tarfile
        output_filename = bids_directory + '.tar.gz'
        with tarfile.open(output_filename, "w:gz") as tar:
            tar.add(bids_directory, arcname=os.path.basename(bids_directory))

        #import platform
        #import subprocess
        #if platform.system() == 'Windows':
        #    os.startfile(data['bids_directory'])
        #elif platform.system() == 'Darwin':
        #    subprocess.Popen(['open', data['bids_directory']])
        #else:
        #    subprocess.Popen(['xdg-open', data['bids_directory']])


# Anonymize - scrubs edf header data.
class Anonymize:
    file_path = ''
    header = []

    # data = { file_path: 'path to iEEG file' }
    def __init__(self, file_path):
        self.file_path = file_path

        try:
            # read EDF file from file_path,
            file_in = EDF.EDFReader(fname=self.file_path)
            # read header of EDF file.
            self.header = file_in.readHeader()
            file_in.close()
        except PermissionError as ex:
            raise ReadError(ex)

    def get_header(self):
        return self.header

    def set_header(self, key, value):
        self.header[0][key] = value

    def make_copy(self, new_file):
        header = self.get_header()
        file_in = EDF.EDFReader(fname=self.file_path)
        file_out = EDF.EDFWriter()
        file_out.open(new_file)
        file_out.writeHeader(header)
        meas_info = header[0]
        for i in range(meas_info['n_records']):
            data = file_in.readBlock(i)
            file_out.writeBlock(data)
        file_in.close()
        file_out.close()


# Converter - Creates the BIDS output by edf file.
class Converter:
    m_info = ''

    # data = { file_path: '', bids_directory: '', read_only: false,
    # event_files: '', line_freq: '', site_id: '', project_id: '',
    # sub_project_id: '', session: '', subject_id: ''}
    def __init__(self, data):
        print('- Converter: init started.')
        modality = 'seeg'
        if data['modality'] == 'eeg':
            modality = 'eeg'

        for i, eegRun in enumerate(data['eegRuns']):
            eegRun['eegBIDSBasename'] = self.to_bids(
                fileFormat=data['fileFormat'],
                eeg_run=eegRun,
                ch_type=modality,
                task=data['taskName'],
                bids_directory=data['bids_directory'],
                subject_id=data['participantID'],
                session=data['session'],
                run=((i + 1) if len(data['eegData']['files']) > 1 else None),
                output_time=data['output_time'],
                read_only=data['read_only'],
                line_freq=data['line_freq']
            )

    @staticmethod
    def validate(path):
        if os.path.isfile(path):
            return True
        else:
            print('File not found or is not file: %s', path)
            return False

    @classmethod
    def set_m_info(cls, value):
        cls.m_info = value

    def to_bids(self,
                fileFormat,
                eeg_run,
                bids_directory,
                subject_id,
                session,
                output_time,
                task='test',
                run=None,
                ch_type='seeg',
                read_only=False,
                line_freq='n/a'):
        file = eeg_run['eegFile']

        raw = ''
        if self.validate(file):
            if fileFormat == 'edf':
                try:
                    reader = EDF.EDFReader(fname=file)
                except PermissionError as ex:
                    raise ReadError(ex)

                m_info, c_info = reader.open(fname=file)
                self.set_m_info(m_info)

                raw = mne.io.read_raw_edf(input_fname=file)

                raw._init_kwargs = {
                    'input_fname': file,
                    'eog': None,
                    'misc': None,
                    'stim_channel': 'auto',
                    'exclude': (),
                    'preload': False,
                    'verbose': None
                }
            
            if fileFormat == 'set':
                try:
                    raw = mne.io.read_raw_eeglab(input_fname=file, preload=False, verbose=True)
                except Exception as ex:
                    raise ReadError(ex)

                # anonymize -- 
                # info['meas_date'], will be set to January 1ˢᵗ, 2000
                # birthday will be updated to match age
                # refer to documentation on mne.io.anonymize_info
                raw = raw.anonymize()

                # for set files, the nasion, lpa and rpa landmarks are not properly read from
                # EEGLAB files so manually editing them
                self._populate_back_landmarks(raw, file)

                m_info = raw.info
                self.set_m_info(m_info)

                raw._init_kwargs = {
                    'input_fname': file,
                    'preload': False,
                    'verbose': None
                }

            if read_only:
                return True

            ch_types = {}
            for ch in raw.ch_names:
                ch_name = ch.lower()
                if 'eeg' in ch_name:
                    ch_types[ch] = 'eeg'
                elif 'eog' in ch_name:
                    ch_types[ch] = 'eog'
                elif 'ecg' in ch_name or 'ekg' in ch_name:
                    ch_types[ch] = 'ecg'
                elif 'lflex' in ch_name or 'rflex' in ch_name or 'chin' in ch_name:
                    ch_types[ch] = 'emg'
                elif 'trigger' in ch_name:
                    ch_types[ch] = 'stim'

                else:
                    ch_types[ch] = ch_type

            raw.set_channel_types(ch_types)

            m_info['subject_info'] = {
                'his_id': subject_id
            }
            subject = m_info['subject_info']['his_id'].replace('_', '').replace('-', '').replace(' ', '')

            if line_freq.isnumeric():
                line_freq = int(line_freq)
            else:
                line_freq = None
            raw.info['line_freq'] = line_freq

            try:
                os.makedirs(bids_directory + os.path.sep + output_time, exist_ok=True)
                bids_directory = bids_directory + os.path.sep + output_time
                bids_root = bids_directory

                bids_basename = BIDSPath(subject=subject, task=task, root=bids_root, acquisition=ch_type, run=run)
                bids_basename.update(session=session)

                try:
                    write_raw_bids(raw, bids_basename, allow_preload=False, overwrite=False, verbose=False)
                    with open(bids_basename, 'r+b') as f:
                        f.seek(8)  # id_info field starts 8 bytes in
                        f.write(bytes("X X X X".ljust(80), 'ascii'))

                    if fileFormat == 'set':
                        # SET files generated by write_raw_bids are corrupted and need to be recreated using
                        # the export function of the mne library.
                        # For more information, see https://github.com/mne-tools/mne-bids/issues/991
                        mne.export.export_raw(fname=bids_basename.fpath, raw=raw, fmt='eeglab', overwrite=True)
                        fdt_path = os.path.splitext(bids_basename.fpath)[0] + '.fdt'
                        os.remove(fdt_path)
                except Exception as ex:
                    print('Exception ex:')
                    print(ex)
                    raise WriteError(ex)
                
                print('finished')
                print(bids_basename.basename)
                
                return bids_basename.basename

            except PermissionError as ex:
                raise WriteError(ex)

            except Exception as ex:
                print(ex)
        else:
            print('File not found or is not file: %s', file)

    @staticmethod
    def _populate_back_landmarks(raw, file):
        """
        This function is used to circumvent a bug in the mne.read_raw_eeglab function present across
        all version of mne, including 1.0.0 (latest version tested). For some reason, the landmarks
        (nasion, left periauricular point, right periauricular point) are not being properly read
        from the EEGLAB structure. This function fetches directly those landmark coordinates via
        the pymatreader library and reinsert them into the raw MNE structure.

        See development on https://github.com/mne-tools/mne-python/issues/10474 for more information

        :param raw: MNE-PYTHON raw object
        :param file: path to the EEG.set file
        """

        # read the EEG matlab structure to get the nasion, lpa and rpa locations
        eeg_mat = pymatreader.read_mat(file)
        urchanlocs_dict = None
        if 'EEG' in eeg_mat.keys() and 'urchanlocs' in eeg_mat['EEG'].keys():
            urchanlocs_dict = eeg_mat['EEG']['urchanlocs']
        elif 'urchanlocs' in eeg_mat.keys():
            urchanlocs_dict = eeg_mat['urchanlocs']

        # get the indices that should be used to fetch the coordinates of the different landmarks
        nasion_index = urchanlocs_dict['description'].index('Nasion')
        lpa_index = urchanlocs_dict['description'].index('Left periauricular point')
        rpa_index = urchanlocs_dict['description'].index('Right periauricular point')

        # fetch the coordinates of the different landmarks
        nasion_coord = [
            urchanlocs_dict['X'][nasion_index],
            urchanlocs_dict['Y'][nasion_index],
            urchanlocs_dict['Z'][nasion_index]
        ]
        lpa_coord = [
            urchanlocs_dict['X'][lpa_index],
            urchanlocs_dict['Y'][lpa_index],
            urchanlocs_dict['Z'][lpa_index]
        ]
        rpa_coord = [
            urchanlocs_dict['X'][rpa_index],
            urchanlocs_dict['Y'][rpa_index],
            urchanlocs_dict['Z'][rpa_index]
        ]

        # create the new montage with the channels positions and the landmark coordinates
        new_montage = mne.channels.make_dig_montage(
            ch_pos=raw.get_montage().get_positions()['ch_pos'],
            coord_frame='head',
            nasion=nasion_coord,
            lpa=lpa_coord,
            rpa=rpa_coord
        )
        raw.set_montage(new_montage)  # set the new montage in the raw object


# Time - used for generating BIDS 'output' directory
class Time:
    def __init__(self):
        print('- Time: init started.')
        from datetime import datetime
        now = datetime.now()
        self.latest_output = now.strftime("%Y-%m-%d-%Hh%Mm%Ss")
