"""Command line interface for the remage runtime tests package."""

import argparse
import sys
from pathlib import Path
import json

from .config import Config
from .simulation import SimulationRunner
from .submission import JobSubmitter
from .plotting import ResultsPlotter


def run_simulation():
    """CLI entry point for running simulations."""
    parser = argparse.ArgumentParser(description='Run REMAGE runtime tests')
    parser.add_argument('config_file', help='Path to the configuration JSON file')
    parser.add_argument('--output-dir', '-o', type=Path, default='results',
                       help='Output directory for results')
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config.from_file(args.config_file)
    
    # Build template path from config
    template_path = Path(config.simulation.template_dir) / config.simulation.macro_template
    runner = SimulationRunner(config, template_path)
    
    # Create project-specific output directory
    project_output_dir = args.output_dir / config.project_name
    project_output_dir.mkdir(parents=True, exist_ok=True)
    
    all_results = {}
    for m_step in config.simulation.m_steps:
        # Use project directory instead of m_step subdirectories
        result = runner.run_m_step_tests(m_step, project_output_dir)
        if result:
            all_results[f"m{m_step}"] = result
    
    # Save overall results using project name in project directory
    overall_file = project_output_dir / f"{config.project_name}_overall_results.json"
    with open(overall_file, 'w') as f:
        json.dump(all_results, f, indent=4)
    
    print(f"All results saved to {overall_file}")


def run_m_step():
    """CLI entry point for running a single m_step (used by SLURM jobs)."""
    parser = argparse.ArgumentParser(description='Run tests for a single m_step')
    parser.add_argument('--config-file', type=Path, required=True,
                       help='Configuration file path')
    parser.add_argument('--m-step', type=int, required=True, help='m_step value to test')
    parser.add_argument('--output-dir', type=Path, required=True,
                       help='Output directory for this m_step')
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config.from_file(args.config_file)
    
    # Build template path from config
    template_path = Path(config.simulation.template_dir) / config.simulation.macro_template
    runner = SimulationRunner(config, template_path)
    
    result = runner.run_m_step_tests(args.m_step, args.output_dir)
    if result:
        print(f"Successfully completed tests for m_step {args.m_step}")
    else:
        print(f"Failed to complete tests for m_step {args.m_step}")
        sys.exit(1)


def submit_jobs():
    """CLI entry point for submitting SLURM jobs."""
    parser = argparse.ArgumentParser(description='Submit SLURM jobs for runtime tests')
    parser.add_argument('config_file', help='Path to the configuration JSON file')
    parser.add_argument('--base-dir', type=Path, default=Path.cwd(),
                       help='Base directory for the project')
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config.from_file(args.config_file)
    
    # Build template path from config
    template_path = Path(config.simulation.template_dir) / config.simulation.macro_template
    submitter = JobSubmitter(config, args.base_dir, args.config_file)
    
    submitted_jobs = submitter.submit_all_jobs(template_path)
    
    if submitted_jobs:
        print(f"Successfully submitted {len(submitted_jobs)} jobs")
    else:
        print("No jobs were submitted")


def collect_results():
    """CLI entry point for collecting individual m_step results into a summary file."""
    parser = argparse.ArgumentParser(description='Collect individual m_step results into a summary file')
    parser.add_argument('config_file', help='Path to the configuration JSON file')
    parser.add_argument('--results-dir', type=Path, 
                       help='Directory containing individual result files (default: results/project_name)')
    parser.add_argument('--output-file', type=Path,
                       help='Output file for combined results (default: project_name_overall_results.json)')
    parser.add_argument('--force', action='store_true',
                       help='Overwrite existing summary file')
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config.from_file(args.config_file)
    
    # Determine results directory
    if args.results_dir:
        results_dir = args.results_dir
    else:
        results_dir = Path('results') / config.project_name
    
    if not results_dir.exists():
        print(f"Error: Results directory not found: {results_dir}")
        return 1
    
    # Determine output file
    if args.output_file:
        output_file = args.output_file
    else:
        output_file = results_dir / f"{config.project_name}_overall_results.json"
    
    # Check if output file already exists
    if output_file.exists() and not args.force:
        print(f"Error: Output file already exists: {output_file}")
        print("Use --force to overwrite")
        return 1
    
    # Collect individual result files
    base_name = config.results_file.replace('_results.json', '')
    collected_results = {}
    missing_files = []
    
    for m_step in config.simulation.m_steps:
        result_filename = f"{base_name}_m{m_step}_results.json"
        result_file = results_dir / result_filename
        
        if result_file.exists():
            try:
                with open(result_file) as f:
                    result_data = json.load(f)
                collected_results[f"m{m_step}"] = result_data
                print(f"✓ Collected results for m_step {m_step}")
            except Exception as e:
                print(f"✗ Error reading {result_file}: {e}")
                missing_files.append(str(result_file))
        else:
            print(f"✗ Missing results file: {result_file}")
            missing_files.append(str(result_file))
    
    if not collected_results:
        print("Error: No valid result files found")
        return 1
    
    if missing_files:
        print(f"\nWarning: {len(missing_files)} result files are missing:")
        for missing in missing_files:
            print(f"  - {missing}")
        print()
    
    # Save combined results
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(collected_results, f, indent=4)
        
        print(f"✓ Combined results saved to: {output_file}")
        print(f"✓ Collected {len(collected_results)} m_step results")
        return 0
        
    except Exception as e:
        print(f"Error saving combined results: {e}")
        return 1


def plot_results():
    """CLI entry point for plotting results."""
    parser = argparse.ArgumentParser(description='Plot runtime test results')
    parser.add_argument('results_file', type=Path, help='Path to the results JSON file')
    parser.add_argument('--output-dir', type=Path, default=Path.cwd(), 
                       help='Directory to save plots (default: current directory)')
    parser.add_argument('--plot-type', choices=['runtime', 'speedup', 'combined'], 
                       default='speedup', help='Type of plot to generate')
    
    args = parser.parse_args()
    
    if not args.results_file.exists():
        print(f"Error: Results file not found: {args.results_file}")
        return 1
    
    # Create output directory if it doesn't exist
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load and plot results
    try:
        plotter = ResultsPlotter(args.results_file)
        
        base_name = args.results_file.stem
        
        if args.plot_type == 'runtime':
            output_path = args.output_dir / f"{base_name}_runtime.png"
            fig = plotter.plot_runtime(output_path)
            if fig:
                print(f"Runtime plot saved to: {output_path}")
                
        elif args.plot_type == 'speedup':
            output_path = args.output_dir / f"{base_name}_speedup.png"
            fig = plotter.plot_speedup(output_path)
            if fig:
                print(f"Speedup plot saved to: {output_path}")
                
        elif args.plot_type == 'combined':
            output_path = args.output_dir / f"{base_name}_combined.png"
            fig = plotter.plot_combined(output_path)
            if fig:
                print(f"Combined plot saved to: {output_path}")
        
    except Exception as e:
        print(f"Error creating plots: {e}")
        return 1
    
    return 0


def create_config():
    """CLI entry point for creating a configuration file."""
    parser = argparse.ArgumentParser(description='Create a configuration file')
    parser.add_argument('--output', '-o', type=Path, default='config.json',
                       help='Output configuration file path')
    parser.add_argument('--template', action='store_true',
                       help='Create a template configuration with explanations')
    
    args = parser.parse_args()
    
    config = Config.create_default()
    
    if args.template:
        # Add comments and explanations
        config_dict = config.to_dict()
        config_dict['_comments'] = {
            'simulation': {
                'm_steps': 'List of m values (thread counts) to test',
                'n_primaries': 'Number of primary particles per simulation',
                'execution_mode': 'Either "multithreaded" or "multiprocessed"',
                'multithreaded_option': '"fix" keeps primaries constant, "scale" scales with threads',
                'additional_args': 'Additional command line arguments for remage'
            },
            'cluster': {
                'partition': 'SLURM partition to use',
                'time_limit': 'Maximum job runtime',
                'constraint': 'Node constraints (e.g., "cpu" for CPU nodes)'
            },
            'test': {
                'start_index': 'Starting index for test iterations',
                'end_index': 'Ending index for test iterations',
                'skip_existing': 'Skip tests if results already exist'
            }
        }
        
        with open(args.output, 'w') as f:
            json.dump(config_dict, f, indent=2)
    else:
        config.to_file(args.output)
    
    print(f"Configuration file created: {args.output}")


if __name__ == '__main__':
    # This allows the module to be run directly for testing
    create_config()
