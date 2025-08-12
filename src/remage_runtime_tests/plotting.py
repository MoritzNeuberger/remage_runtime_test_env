"""Results plotting and analysis module."""

import json
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import glob
import re

try:
    import phdthesisplotstyle as phd
    from tol_colors import tol_cset
    plt.style.use(phd.PHDTHESISPLOTSTYLE)
    tolc = tol_cset("bright")
    HAS_STYLE = True
except ImportError:
    HAS_STYLE = False
    tolc = None


class ResultsPlotter:
    """Handles plotting and analysis of runtime test results."""
    
    def __init__(self, results_dir: Path):
        self.results_dir = Path(results_dir)
        self.data = self.load_all_results()
    
    def load_all_results(self) -> Dict:
        """Load all runtime_estimates.json files from results directory."""
        results = {}
        
        # Find all runtime_estimates.json files
        pattern = self.results_dir / "**/runtime_estimates.json"
        result_files = glob.glob(str(pattern), recursive=True)
        
        for file_path in result_files:
            file_path = Path(file_path)
            
            # Extract key from directory structure
            rel_path = file_path.relative_to(self.results_dir)
            key = str(rel_path.parent)  # Use parent directory as key
            
            try:
                with open(file_path) as f:
                    data = json.load(f)
                results[key] = data
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
        
        return results
    
    def filter_results(self, pattern: str) -> Dict:
        """Filter results based on a pattern in the key."""
        return {k: v for k, v in self.data.items() if re.search(pattern, k)}
    
    def extract_m_values(self, keys: List[str]) -> np.ndarray:
        """Extract m values from result keys."""
        m_values = []
        for key in keys:
            # Try to extract m value from key (e.g., "m21" -> 21)
            match = re.search(r'm(\d+)', key)
            if match:
                m_values.append(int(match.group(1)))
            else:
                # Try to get from data
                if key in self.data and 'm_step' in self.data[key]:
                    m_values.append(self.data[key]['m_step'])
        
        return np.array(m_values)
    
    def plot_speedup(self, particle_type: str = "electron", 
                    execution_modes: List[str] = None,
                    output_path: Optional[Path] = None) -> plt.Figure:
        """Plot speedup curves for different execution modes."""
        
        if execution_modes is None:
            execution_modes = ["multithreaded", "multithreaded_scaled_primaries"]
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        colors = [tolc[i] if HAS_STYLE else f"C{i}" for i in range(len(execution_modes))]
        
        for i, mode in enumerate(execution_modes):
            # Filter results for this mode and particle type
            pattern = f"{particle_type}.*{mode}"
            filtered_data = self.filter_results(pattern)
            
            if not filtered_data:
                print(f"No data found for pattern: {pattern}")
                continue
            
            # Sort by m value
            keys = list(filtered_data.keys())
            m_values = self.extract_m_values(keys)
            
            if len(m_values) == 0:
                continue
            
            # Sort by m values
            sorted_indices = np.argsort(m_values)
            sorted_keys = [keys[i] for i in sorted_indices]
            sorted_m_values = m_values[sorted_indices]
            
            # Extract performance data
            runtimes = []
            runtime_errors = []
            threads = []
            
            for key in sorted_keys:
                data = filtered_data[key]
                if 'runtime' in data and 'val' in data['runtime']:
                    runtimes.append(data['runtime']['val'])
                    runtime_errors.append(data['runtime'].get('std', 0))
                    
                    # Try to extract thread count
                    thread_count = 1
                    if 'config' in data:
                        thread_count = data['config'].get('simulation', {}).get('n_threads', 1)
                    elif 'm_step' in data:
                        thread_count = data['m_step']  # Assuming m_step corresponds to thread count
                    
                    threads.append(thread_count)
            
            if not runtimes:
                continue
            
            # Calculate speedup relative to single thread
            runtimes = np.array(runtimes)
            runtime_errors = np.array(runtime_errors)
            threads = np.array(threads)
            
            baseline_runtime = runtimes[0] if len(runtimes) > 0 else 1
            speedup = baseline_runtime / runtimes
            
            # Error propagation for speedup
            speedup_errors = speedup * (runtime_errors / runtimes)
            
            # Plot
            ax.errorbar(threads, speedup, yerr=speedup_errors, 
                       marker='o', linestyle='-', linewidth=2, 
                       markersize=6, color=colors[i], 
                       label=mode.replace('_', ' ').title())
        
        # Ideal speedup line
        max_threads_list = []
        for mode in execution_modes:
            filtered = self.filter_results(f"{particle_type}.*{mode}")
            if filtered:
                m_vals = self.extract_m_values(list(filtered.keys()))
                if len(m_vals) > 0:
                    max_threads_list.append(max(m_vals))
        
        if max_threads_list:
            max_threads = max(max_threads_list)
            ideal_x = np.linspace(1, max_threads, 100)
            ax.plot(ideal_x, ideal_x, '--', color='gray', alpha=0.7, label='Ideal Speedup')
        
        ax.set_xlabel('Number of Threads')
        ax.set_ylabel('Speedup')
        ax.set_title(f'Multithreaded Speedup - {particle_type.title()}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=1)
        ax.set_ylim(bottom=0)
        
        if output_path:
            fig.savefig(output_path, dpi=300, bbox_inches='tight')
        
        return fig
    
    def plot_runtime_comparison(self, particle_types: List[str] = None,
                              execution_mode: str = "multithreaded",
                              output_path: Optional[Path] = None) -> plt.Figure:
        """Plot runtime comparison between particle types."""
        
        if particle_types is None:
            particle_types = ["electron", "gamma"]
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        colors = [tolc[i] if HAS_STYLE else f"C{i}" for i in range(len(particle_types))]
        
        for i, particle in enumerate(particle_types):
            pattern = f"{particle}.*{execution_mode}"
            filtered_data = self.filter_results(pattern)
            
            if not filtered_data:
                continue
            
            keys = list(filtered_data.keys())
            m_values = self.extract_m_values(keys)
            
            # Sort by m values
            sorted_indices = np.argsort(m_values)
            sorted_keys = [keys[i] for i in sorted_indices]
            sorted_m_values = m_values[sorted_indices]
            
            # Extract runtime data
            runtimes = []
            runtime_errors = []
            
            for key in sorted_keys:
                data = filtered_data[key]
                if 'runtime' in data and 'val' in data['runtime']:
                    runtimes.append(data['runtime']['val'])
                    runtime_errors.append(data['runtime'].get('std', 0))
            
            if runtimes:
                ax.errorbar(sorted_m_values, runtimes, yerr=runtime_errors,
                           marker='o', linestyle='-', linewidth=2,
                           markersize=6, color=colors[i],
                           label=particle.title())
        
        ax.set_xlabel('Thread Count (m)')
        ax.set_ylabel('Runtime (seconds)')
        ax.set_title(f'Runtime vs Thread Count - {execution_mode.replace("_", " ").title()}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_yscale('log')
        
        if output_path:
            fig.savefig(output_path, dpi=300, bbox_inches='tight')
        
        return fig
    
    def plot_efficiency(self, particle_type: str = "electron",
                       execution_mode: str = "multithreaded_scaled_primaries",
                       output_path: Optional[Path] = None) -> plt.Figure:
        """Plot parallel efficiency."""
        
        pattern = f"{particle_type}.*{execution_mode}"
        filtered_data = self.filter_results(pattern)
        
        if not filtered_data:
            print(f"No data found for pattern: {pattern}")
            return None
        
        keys = list(filtered_data.keys())
        m_values = self.extract_m_values(keys)
        
        # Sort by m values
        sorted_indices = np.argsort(m_values)
        sorted_keys = [keys[i] for i in sorted_indices]
        sorted_m_values = m_values[sorted_indices]
        
        # Extract data
        event_rates = []
        for key in sorted_keys:
            data = filtered_data[key]
            if 'event_rate' in data and data['event_rate'] and 'val' in data['event_rate']:
                event_rates.append(data['event_rate']['val'])
            else:
                event_rates.append(None)
        
        # Calculate efficiency
        fig, ax = plt.subplots(figsize=(10, 8))
        
        if event_rates and event_rates[0] is not None:
            baseline_rate = event_rates[0]
            efficiencies = []
            threads = []
            
            for i, rate in enumerate(event_rates):
                if rate is not None:
                    thread_count = sorted_m_values[i]
                    efficiency = rate / (baseline_rate * thread_count) * 100
                    efficiencies.append(efficiency)
                    threads.append(thread_count)
            
            ax.plot(threads, efficiencies, 'o-', linewidth=2, markersize=6,
                   color=tolc[0] if HAS_STYLE else 'C0')
            ax.axhline(y=100, linestyle='--', color='gray', alpha=0.7, label='100% Efficiency')
            
            ax.set_xlabel('Number of Threads')
            ax.set_ylabel('Parallel Efficiency (%)')
            ax.set_title(f'Parallel Efficiency - {particle_type.title()}')
            ax.grid(True, alpha=0.3)
            ax.set_ylim(0, 110)
            ax.legend()
        
        if output_path:
            fig.savefig(output_path, dpi=300, bbox_inches='tight')
        
        return fig
    
    def generate_summary_report(self, output_path: Path) -> None:
        """Generate a summary report with key statistics."""
        
        report = {
            "total_tests": len(self.data),
            "particle_types": [],
            "execution_modes": [],
            "thread_ranges": {},
            "best_speedups": {},
            "summary_stats": {}
        }
        
        # Analyze data
        for key, data in self.data.items():
            # Extract particle type
            if "electron" in key:
                particle = "electron"
            elif "gamma" in key:
                particle = "gamma"
            else:
                particle = "unknown"
            
            if particle not in report["particle_types"]:
                report["particle_types"].append(particle)
            
            # Extract execution mode
            if "multithreaded_scaled_primaries" in key:
                mode = "multithreaded_scaled_primaries"
            elif "multithreaded" in key:
                mode = "multithreaded"
            elif "multiprocessed" in key:
                mode = "multiprocessed"
            else:
                mode = "unknown"
            
            if mode not in report["execution_modes"]:
                report["execution_modes"].append(mode)
            
            # Track thread ranges
            if 'm_step' in data:
                m_step = data['m_step']
                if particle not in report["thread_ranges"]:
                    report["thread_ranges"][particle] = {"min": m_step, "max": m_step}
                else:
                    report["thread_ranges"][particle]["min"] = min(report["thread_ranges"][particle]["min"], m_step)
                    report["thread_ranges"][particle]["max"] = max(report["thread_ranges"][particle]["max"], m_step)
        
        # Save report
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Summary report saved to {output_path}")
        return report
