# REMAGE Runtime Tests

A refactored package for systematic runtime testing of REMAGE simulations with project-based organization and automatic file naming.

## Installation

Install the package using pip in a virtual environment:

```bash
cd remage_runtime_tests
pip install -e .
```

## Package Structure

```
remage_runtime_tests/
├── src/remage_runtime_tests/
│   ├── __init__.py          # Package initialization
│   ├── config.py            # Configuration management with auto-naming
│   ├── simulation.py        # Individual simulation runner
│   ├── submission.py        # SLURM job submission
│   ├── plotting.py          # Results plotting and analysis
│   └── cli.py              # Command line interface
├── templates/               # Macro templates (optional)
├── pyproject.toml          # Package configuration
└── README.md               # This file
```

## Key Features

### Project-Based Organization
- **Single project directory**: All results for a test are organized in one folder named after the `project_name`
- **M-step in filename**: Each result file includes the m_step in its name (e.g., `project_name_m4_results.json`)
- **No subdirectories**: No more separate `m1/`, `m2/`, etc. folders
- **Automatic file naming**: Results files automatically named based on `project_name`

### Template System
- **Macro template specification**: Configuration specifies which macro template to use
- **Template directory**: Templates can be stored anywhere and referenced by path
- **Placeholder substitution**: Automatic replacement of placeholders in macro files

### Command Line Tools

After installation, four CLI tools are available:

1. **`rrt-run`**: Run simulations locally
2. **`rrt-submit`**: Submit SLURM jobs  
3. **`rrt-collect`**: Collect individual results into summary file (necessary when using SLURM, automatic when running locally)
4. **`rrt-plot`**: Generate plots from results

### Configuration-Driven

All test parameters are controlled by a single JSON configuration file:

```json
{
  "simulation": {
    "macro_template": "test.mac",
    "m_steps": [1, 2, 4, 8, 16, 32],
    "n_primaries": 1500,
    "execution_mode": "multithreaded_scaled",
    "physics_list": "FTFP_BERT",
    "additional_args": [],
    "output_dir": "/var/tmp",
    "template_dir": "/path/to/templates",
    "container": "legendexp/remage:latest",
    "executable": "/path/to/remage-cpp"
  },
  "cluster": {
    "partition": "regular", 
    "time_limit": "00:10:00",
    "nodes": 1,
    "tasks_per_node": 1,
    "cpus_per_task": 1,
    "constraint": "cpu",
    "mail_user": "user@example.com",
    "additional_sbatch_args": []
  },
  "test": {
    "repetitions": 1,
    "dry_run": false,
    "overwrite": false,
    "skip_existing": true
  },
  "project_name": "my_runtime_test",
  "_description": "Description of this test configuration"
}
```

### Execution Modes

The package supports four execution modes:

- **`multithreaded_fix`**: Fixed number of primaries regardless of m_step
- **`multithreaded_scaled`**: Number of primaries scales with m_step
- **`multiprocessed_fix`**: Fixed number of primaries regardless of m_step  
- **`multiprocessed_scaled`**: Number of primaries scales with m_step

### Automatic File Naming

- **Results files**: Automatically named `{project_name}_results.json` if not specified
- **Individual results**: `{project_name}_m{step}_results.json` (e.g., `my_test_m4_results.json`)
- **Overall results**: `{project_name}_overall_results.json`

## Usage Examples

### 1. Run Tests Locally

```bash
# Run tests using a configuration file
rrt-run /path/to/my_config.json --output-dir results/

# Results saved to: results/{project_name}/{project_name}_m*_results.json
```

### 2. Submit to SLURM

```bash
# Submit jobs for all m_steps defined in config
rrt-submit /path/to/my_config.json --base-dir /path/to/project

# Monitor jobs
squeue -u $USER
```

### 3. Collect Results

```bash
# Collect individual m_step results into summary file
rrt-collect /path/to/my_config.json --results-dir results/my_project

# Force overwrite existing summary file
rrt-collect /path/to/my_config.json --force
```

### 4. Generate Plots

```bash
# Generate plots from summary results
rrt-plot results/my_project_overall_results.json --output-dir plots/

# Generate specific plot types
rrt-plot results/my_project_overall_results.json --plot-type speedup
rrt-plot results/my_project_overall_results.json --plot-type runtime
rrt-plot results/my_project_overall_results.json --plot-type combined
```

## Templates

Templates are macro files with placeholders that get substituted during execution:

### Placeholders

- `{TEMPLATE_DIR}`: Path to template directory
- `{N_PRIMARIES}`: Number of primary particles (calculated based on execution mode)
- `{N_THREADS}`: Number of threads (for multithreaded execution)
- `{N_PROCESSES}`: Number of processes (for multiprocessed execution)
- `{OUTPUT_DIR}`: Output directory for results
- **Legacy placeholders** (still supported):
  - `NUMBER_PIMARY_PLACEHOLDER`: Same as `{N_PRIMARIES}`
  - `OUTPUT_HDF5_PLACEHOLDER`: Same as output file path

### Template Example

```bash
# test.mac
/RMG/Geometry/IncludeGDMLFile {TEMPLATE_DIR}/geometry.gdml
/RMG/Output/FileName {OUTPUT_DIR}/output.h5

/run/initialize

/gps/particle e-
/gps/energy 5 MeV
/run/beamOn {N_PRIMARIES}
```

### Template Directory Structure

Templates can be organized in any directory structure. The `template_dir` in configuration specifies where to find the macro template file:

```
input/
├── l200_hpge_only.mac
├── l200_lar_sensitive.mac
├── l200_full_optical.mac
├── l200_hpge_only_config.json
├── l200_lar_sensitive_config.json
└── l200_full_optical_config.json
```

## Results Structure

Results are organized by project name in a flat structure:

```
results/
└── {project_name}/
    ├── {project_name}_m1_results.json
    ├── {project_name}_m2_results.json
    ├── {project_name}_m4_results.json
    ├── {project_name}_m8_results.json
    ├── {project_name}_m16_results.json
    ├── {project_name}_m32_results.json
    └── {project_name}_overall_results.json
```

### Result File Contents

Each individual result file (`{project_name}_m{step}_results.json`) contains:
- **Runtime statistics**: Mean, std, min, max execution times
- **Event rate measurements**: Events processed per second
- **Process runtime**: Total wall-clock time including overhead
- **Configuration snapshot**: Complete test configuration
- **Raw data**: All individual measurements

The overall results file combines all m_step results into a single file for analysis and plotting.

## Example: L200 Geometry Tests

Here's a complete example for L200 detector runtime testing:

### 1. Configuration File (`l200_test_config.json`)

```json
{
  "simulation": {
    "macro_template": "l200_full_optical.mac",
    "m_steps": [1, 2, 4, 8, 16, 32],
    "n_primaries": 1500,
    "execution_mode": "multithreaded_scaled",
    "physics_list": "FTFP_BERT_LIV",
    "template_dir": "/path/to/input/templates",
    "container": "legendexp/remage:latest",
    "executable": "/opt/remage/bin/remage-cpp"
  },
  "cluster": {
    "partition": "regular",
    "time_limit": "04:00:00",
    "memory": "16GB",
    "constraint": "cpu"
  },
  "test": {
    "dry_run": false,
    "skip_existing": true
  },
  "project_name": "l200_full_optical_runtime_test"
}
```

### 2. Run the Test

```bash
# Local execution
rrt-run l200_test_config.json --output-dir ./results

# SLURM submission
rrt-submit l200_test_config.json --base-dir .

# Collect results after jobs complete
rrt-collect l200_test_config.json

# Generate plots
rrt-plot results/l200_full_optical_runtime_test/l200_full_optical_runtime_test_overall_results.json
```

### 3. Results

```
results/
└── l200_full_optical_runtime_test/
    ├── l200_full_optical_runtime_test_m1_results.json
    ├── l200_full_optical_runtime_test_m2_results.json
    ├── l200_full_optical_runtime_test_m4_results.json
    ├── l200_full_optical_runtime_test_m8_results.json
    ├── l200_full_optical_runtime_test_m16_results.json
    ├── l200_full_optical_runtime_test_m32_results.json
    └── l200_full_optical_runtime_test_overall_results.json
```
