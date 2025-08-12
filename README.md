# REMAGE Runtime Tests

A refactored package for systematic runtime testing of REMAGE simulations.

## Installation

Install the package using uv:

```bash
cd remage_runtime_tests
uv pip install -e .
```

## Package Structure

```
remage_runtime_tests/
├── src/remage_runtime_tests/
│   ├── __init__.py          # Package initialization
│   ├── config.py            # Configuration management
│   ├── simulation.py        # Individual simulation runner
│   ├── submission.py        # SLURM job submission
│   ├── plotting.py          # Results plotting and analysis
│   └── cli.py              # Command line interface
├── templates/               # Macro templates
│   ├── simple_electron.mac
│   ├── simple_gamma.mac
│   └── l200_electron.mac
├── config_example.json      # Example configuration
├── pyproject.toml          # Package configuration
└── README.md               # This file
```

## Key Features

### Simplified Structure
- Single package with clear module separation
- No complex nested folder structures (no more `m1/`, `m2/`, etc.)
- Template-based macro generation
- Output files written to `/var/tmp` with unique timestamps
- Single configuration file controls all test parameters

### Command Line Tools

After installation, three CLI tools are available:

1. **`rrt-run`**: Run simulations locally
2. **`rrt-submit`**: Submit SLURM jobs  
3. **`rrt-plot`**: Generate plots from results

### Configuration-Driven

All test parameters are controlled by a single `config.json` file:

```json
{
  "simulation": {
    "m_steps": [1, 2, 4, 8, 16, 32],
    "n_primaries": 10000,
    "execution_mode": "multithreaded",
    "multithreaded_option": "fix",
    "additional_args": ["--threads", "1"],
    "container": "legendexp/remage:latest"
  },
  "cluster": {
    "partition": "regular",
    "time_limit": "00:15:00"
  },
  "test": {
    "start_index": 0,
    "end_index": 3,
    "skip_existing": true
  }
}
```

## Usage Examples

### 1. Create Configuration

```bash
# Create a default configuration
rrt-run --help  # Shows template creation options

# Or copy and modify the example
cp config_example.json config.json
```

### 2. Run Tests Locally

```bash
# Run tests for simple electron template
rrt-run templates/simple_electron.mac --config-file config.json

# Results will be saved to results/m*/runtime_estimates.json
```

### 3. Submit to SLURM

```bash
# Submit jobs for all m_steps defined in config
rrt-submit templates/simple_electron.mac --config-file config.json

# Monitor jobs
squeue -u $USER

# Job information saved to submitted_jobs.json
```

### 4. Generate Plots

```bash
# Generate speedup plots from results
rrt-plot results/ --output-dir plots/

# Specific plot types
rrt-plot results/ --plot-types speedup efficiency --particle-types electron
```

## Templates

Templates use placeholders that get substituted:

- `NUMBER_PIMARY_PLACEHOLDER`: Replaced with calculated primary count
- `OUTPUT_HDF5_PLACEHOLDER`: Replaced with unique output file path

### Template Example

```bash
# templates/simple_electron.mac
/run/numberOfThreads 1
/gps/particle e-
/gps/energy 5 MeV
/RMG/Output/HDF5/FileName OUTPUT_HDF5_PLACEHOLDER
/run/beamOn NUMBER_PIMARY_PLACEHOLDER
```

## Results Structure

Results are organized hierarchically:

```
results/
├── m1/runtime_estimates.json
├── m2/runtime_estimates.json
├── m4/runtime_estimates.json
└── overall_runtime_estimates.json
```

Each `runtime_estimates.json` contains:
- Runtime statistics (mean, std)
- Event rate measurements  
- Raw data for all iterations
- Complete configuration snapshot

## Key Improvements

1. **Simplified Workflow**: No manual folder creation or template copying
2. **Unique Output Files**: Timestamp-based naming prevents conflicts
3. **Configuration-Driven**: Single file controls all parameters
4. **Template System**: Easy to add new simulation types
5. **Automatic Cleanup**: Temporary files are cleaned up automatically
6. **Comprehensive Results**: Full configuration saved with each result
7. **Flexible Plotting**: Multiple plot types and particle combinations
8. **Job Management**: Track and manage SLURM submissions

## Migration from Old System

The new package provides the same functionality as the original scripts:

- `sim_runner.py` → `rrt-run` + `SimulationRunner` class
- `submit_individual_jobs.py` → `rrt-submit` + `JobSubmitter` class  
- `misc/` notebooks → `rrt-plot` + `ResultsPlotter` class

Configuration replaces the complex command-line arguments and folder-specific configs.
