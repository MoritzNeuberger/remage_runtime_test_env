import subprocess
import tempfile
import os
import re
import argparse
import multiprocessing
import numpy as np
import json

class SimulationRunner:
    def __init__(self, folder, start_index, end_index, num_muons, musun_folder, dry_run, additional_arguments, overwrite):
        self.folder = folder
        self.template_file = os.path.join(folder, 'temp.mac')
        self.output_file_pattern = os.path.abspath(os.path.join(folder, 'musun_output_INDEX.dat'))
        self.output_hdf5_pattern = os.path.abspath(os.path.join(folder, 'output_INDEX.hdf5'))
        self.musun_folder = musun_folder
        self.musun_file_pattern = os.path.join(self.musun_folder, 'musun_output_INDEX.dat')
        self.start_index = start_index
        self.end_index = end_index
        self.num_muons = num_muons
        self.dry_run = dry_run
        self.additional_arguments = additional_arguments
        self.overwrite = overwrite

    def generate_run_mac_file(self, index):
        with open(self.template_file, 'r') as f:
            template_content = f.read()

        output_file = self.output_file_pattern.replace('INDEX', str(index))
        output_hdf5_file = self.output_hdf5_pattern.replace('INDEX', str(index))
        if os.path.exists(output_hdf5_file):
            os.remove(output_hdf5_file)
        musun_file = self.musun_file_pattern.replace('INDEX', str(index))
        run_mac_content = template_content.replace('OUTPUT_FILE_PLACEHOLDER', musun_file)
        run_mac_content = run_mac_content.replace('OUTPUT_HDF5_PLACEHOLDER', output_hdf5_file)
        run_mac_content = run_mac_content.replace('MUSUN_FILE_PLACEHOLDER', musun_file)
        
        # New line: Replace placeholder for number of muons
        run_mac_content = run_mac_content.replace('NUMBER_MUONS_PLACEHOLDER', str(self.num_muons))

        if self.dry_run:
            print(f'Generated run.mac file for index {index} in folder {self.folder}:')
            print(run_mac_content)
            return None
        else:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
                tmp_file.write(run_mac_content)
                return tmp_file.name

    def run_simulation(self, run_mac_file):
        if self.dry_run:
            print(f'Dry run: would run simulation with {run_mac_file} in folder {self.folder}')
            return ''
        else:
            command = (
                f"apptainer run /mnt/atlas01/users/neuberger/L1K_simulations/mage/cosm_sims_mage/container/remage_latest.sif "
                f"remage {run_mac_file} {self.additional_arguments}"
            )
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            output, error = process.communicate()
            output = output.decode('utf-8')
            return output

    def extract_runtime(self, output):
        lines = output.split('\n')
        # Attempt to get the relevant lines at the end of the output
        last_lines = lines[-4:]
        for line in last_lines:
            match = re.search(r'run time was (\d+)\s+days,\s+(\d+)\s+hours,\s+(\d+)\s+minutes and (\d+)\s+seconds', line)
            if match:
                days, hours, minutes, seconds = match.groups()
                total_seconds = int(days) * 24 * 60 * 60 + int(hours) * 60 * 60 + int(minutes) * 60 + int(seconds)
                return total_seconds
        return None

    def run_index(self, index):
        run_mac_file = self.generate_run_mac_file(index)
        if run_mac_file is None and not self.dry_run:
            return None
        output = self.run_simulation(run_mac_file)
        if not self.dry_run and run_mac_file is not None:
            os.remove(run_mac_file)
        runtime = self.extract_runtime(output)
        return runtime

    def estimate_average_runtime(self, num_processes=1):
        json_output_path = os.path.abspath(os.path.join(self.folder, 'runtime_estimates.json'))
        
        # Check if the file exists and handle accordingly
        if os.path.exists(json_output_path):
            if not self.overwrite:
                print(f"Skipping folder {self.folder}: runtime_estimates.json already exists and overwrite is not allowed.")
            #    return None
            #else:
                with open(json_output_path, 'r') as f:
                    existing_data = json.load(f)
                #existing_runtimes = existing_data.get("raw", {}).get("runtimes", [])
                return existing_data
        
        existing_runtimes = []

        with multiprocessing.Pool(processes=num_processes) as pool:
            runtimes = pool.map(self.run_index, range(self.start_index, self.end_index))

        runtimes = [runtime for runtime in runtimes if runtime is not None]
        runtimes.extend(existing_runtimes)  # Append existing runtimes

        if not runtimes:
            return None

        if self.dry_run:
            print('Dry run: skipping average runtime calculation')
            return None

        average_runtime = sum(runtimes) / len(runtimes)
        variance = sum((x - average_runtime) ** 2 for x in runtimes) / len(runtimes)
        standard_deviation = variance ** 0.5
        events_per_sec = self.num_muons / average_runtime
        events_per_sec_list = self.num_muons / np.array(runtimes)
        std_events_per_sec = float(np.std(events_per_sec_list))

        outputs = {
            "folder": self.folder,
            "runtime": { 
               "val": average_runtime,
               "std": standard_deviation
            },
            "event_rate": {
               "val": events_per_sec,
               "std": std_events_per_sec
            },
            "raw": {
               "runtimes": runtimes
            }
        }

        with open(json_output_path, 'w') as f:
            json.dump(outputs, f, indent=4)

        return outputs


def find_folders_with_temp_mac(parent_folder):
    """
    Recursively search for directories containing a 'temp.mac' file.
    Returns a list of folder paths.
    """
    matched_folders = []
    for root, dirs, files in os.walk(parent_folder):
        if 'temp.mac' in files:
            matched_folders.append(root)
    return matched_folders

def load_folder_config(folder):
    """
    If a config.json exists in the folder, load it and return the resulting dictionary.
    Otherwise, return an empty dictionary.
    """
    config_path = os.path.join(folder, 'config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            print(f"Loaded config from {config_path}: {config}")
            return config
        except Exception as e:
            print(f"Error loading config.json in {folder}: {e}")
    return {}

def merge_args(default_args, config):
    """
    Merge the default arguments (parsed from the command line) with the config.
    The values in config override the default_args if present.
    Returns a new argparse.Namespace.
    """
    args_dict = vars(default_args).copy()
    # Remove the find-all flag; it is only relevant for scanning parent folder.
    args_dict.pop('find_all', None)
    for key, value in config.items():
        args_dict[key] = value
    return argparse.Namespace(**args_dict)


def main():
    parser = argparse.ArgumentParser(description='Run simulations and estimate average runtime')
    parser.add_argument('folder', help='Folder containing temp.mac file or parent folder to search (if --find-all is used)')
    parser.add_argument('-s', '--start-index', type=int, default=0, help='Start index for output files')
    parser.add_argument('-e', '--end-index', type=int, default=10, help='End index for output files')
    parser.add_argument('-n', '--num-muons', type=int, default=10000, help='Number of muons for estimated runtime')
    parser.add_argument('-d', '--dry-run', action='store_true', help='Dry run: generate run.mac files and print commands, but do not run simulations')
    parser.add_argument('-p', '--num-processes', type=int, default=1, help='Number of processes to use for parallel simulation')
    parser.add_argument('-m', '--musun-folder', type=str, default='/mnt/atlas01/users/neuberger/L1K_simulations/warwick-legend/data/for_remage_around_water_tank', help="Location of musun files.")
    parser.add_argument('-a', '--additional-arguments', type=str, default="", help="Additional command-line arguments for the simulation")
    parser.add_argument('-f', '--find-all', action='store_true', help='Scan the folder recursively to find all sub-folders containing a temp.mac file and run simulations for each one')
    parser.add_argument('-o', '--overwrite', action='store_true', help='Overwrite existing runtime_estimates.json if it exists')
    
    args = parser.parse_args()

    folders_to_run = []
    if args.find_all:
        if not os.path.exists(args.folder):
            print(f'Error: folder {args.folder} does not exist')
            return
        folders_to_run = find_folders_with_temp_mac(args.folder)
        if not folders_to_run:
            print(f'No folders containing temp.mac found in {args.folder}')
            return
        print(f"Found {len(folders_to_run)} folders with temp.mac file.")
    else:
        # Single folder mode:
        if not os.path.exists(args.folder):
            print(f'Error: folder {args.folder} does not exist')
            return
        if not os.path.exists(os.path.join(args.folder, 'temp.mac')):
            print(f'Error: temp.mac file not found in folder {args.folder}')
            return
        folders_to_run = [args.folder]

    overall_results = {}

    # Process each folder:
    for folder in folders_to_run:
        print(f"\nProcessing folder: {folder}")
        # Load configuration from config.json if present, and merge with default args:
        folder_config = load_folder_config(folder)
        merged_args = merge_args(args, folder_config)
        # Provide feedback on the effective parameters for this folder:
        print(f"Using parameters: start_index={merged_args.start_index}, end_index={merged_args.end_index}, "
              f"num_muons={merged_args.num_muons}, musun_folder={merged_args.musun_folder}, "
              f"dry_run={merged_args.dry_run}, additional_arguments=\"{merged_args.additional_arguments}\"")

        runner = SimulationRunner(
            folder,
            merged_args.start_index,
            merged_args.end_index,
            merged_args.num_muons,
            merged_args.musun_folder,
            merged_args.dry_run,
            merged_args.additional_arguments,
            merged_args.overwrite  # Pass the overwrite argument to the runner
        )
        data = runner.estimate_average_runtime(merged_args.num_processes)
        overall_results[folder] = data
        print(f"Results for folder {folder}:\n{data}")

    # Optionally, write an overall summary file if you wish:
    summary_path = os.path.abspath(os.path.join(args.folder, 'overall_runtime_estimates.json'))
    with open(summary_path, 'w') as f:
        json.dump(overall_results, f, indent=4)
    print(f"\nOverall summary saved to {summary_path}")

if __name__ == '__main__':
    main()
