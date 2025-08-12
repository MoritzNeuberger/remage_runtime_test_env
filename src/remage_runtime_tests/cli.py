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


def plot_results():
    """CLI entry point for plotting results."""
    parser = argparse.ArgumentParser(description='Plot runtime test results')
    parser.add_argument('results_dir', help='Directory containing results')
    parser.add_argument('--output-dir', '-o', type=Path, default='plots',
                       help='Output directory for plots')
    parser.add_argument('--particle-types', nargs='+', default=['electron', 'gamma'],
                       help='Particle types to plot')
    parser.add_argument('--plot-types', nargs='+', 
                       choices=['speedup', 'runtime', 'efficiency', 'all'],
                       default=['all'], help='Types of plots to generate')
    
    args = parser.parse_args()
    
    # Create plotter
    plotter = ResultsPlotter(Path(args.results_dir))
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    plot_types = args.plot_types
    if 'all' in plot_types:
        plot_types = ['speedup', 'runtime', 'efficiency']
    
    # Generate plots
    for particle in args.particle_types:
        if 'speedup' in plot_types:
            fig = plotter.plot_speedup(
                particle_type=particle,
                output_path=args.output_dir / f"speedup_{particle}.png"
            )
            if fig:
                print(f"Speedup plot saved for {particle}")
        
        if 'runtime' in plot_types:
            fig = plotter.plot_runtime_comparison(
                particle_types=[particle],
                output_path=args.output_dir / f"runtime_{particle}.png"
            )
            if fig:
                print(f"Runtime plot saved for {particle}")
        
        if 'efficiency' in plot_types:
            fig = plotter.plot_efficiency(
                particle_type=particle,
                output_path=args.output_dir / f"efficiency_{particle}.png"
            )
            if fig:
                print(f"Efficiency plot saved for {particle}")
    
    # Generate summary report
    plotter.generate_summary_report(args.output_dir / "summary_report.json")


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
