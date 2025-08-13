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
    
    def __init__(self, results_file: Path):
        self.results_file = Path(results_file)
        self.data = self.load_results()
    
    def load_results(self) -> Dict:
        """Load results from a single overall results file."""
        try:
            with open(self.results_file) as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"Error loading {self.results_file}: {e}")
            return {}
    
    def extract_m_step_data(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Extract m_step values, runtimes, runtime errors, and thread counts from data."""
        m_steps = []
        runtimes = []
        runtime_errors = []
        event_rates = []
        event_rate_errors = []
        thread_counts = []
        
        for key, data in self.data.items():
            if key.startswith('m') and isinstance(data, dict):
                # Extract m_step value from key (e.g., "m4" -> 4)
                try:
                    m_step = int(key[1:])
                    m_steps.append(m_step)
                    
                    # Extract runtime data
                    if 'runtime' in data and 'val' in data['runtime']:
                        runtimes.append(data['runtime']['val'])
                        runtime_errors.append(data['runtime'].get('std', 0))
                        
                        # Extract thread count (use m_step if not specified)
                        thread_count = m_step
                        if 'config' in data and 'simulation' in data['config']:
                            # Try to get actual thread count from config
                            sim_config = data['config']['simulation']
                            if 'execution_mode' in sim_config:
                                if 'scaled' in sim_config['execution_mode']:
                                    thread_count = m_step
                                else:
                                    thread_count = 1  # Fixed mode
                        
                        thread_counts.append(thread_count)

                        event_rates.append(data.get('event_rate', {}).get('val', 0))
                        event_rate_errors.append(data.get('event_rate', {}).get('std', 0))
                    else:
                        # Remove this m_step if no runtime data
                        m_steps.pop()

                        
                except ValueError:
                    # Skip if key doesn't match expected format
                    continue
        
        # Sort by m_step values
        if m_steps:
            sorted_indices = np.argsort(m_steps)
            m_steps = np.array(m_steps)[sorted_indices]
            runtimes = np.array(runtimes)[sorted_indices] 
            runtime_errors = np.array(runtime_errors)[sorted_indices]
            thread_counts = np.array(thread_counts)[sorted_indices]
            event_rates = np.array(event_rates)[sorted_indices]
            event_rate_errors = np.array(event_rate_errors)[sorted_indices]
        
        return m_steps, runtimes, runtime_errors, thread_counts, event_rates, event_rate_errors
    
    def calculate_speedup(self, m_steps: np.ndarray, runtimes: np.ndarray, runtime_errors: np.ndarray, 
                         event_rates: np.ndarray, event_rate_errors: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate speedup and its errors, preferring event rate over inverse runtime."""
        
        # Use event rates if available (more accurate for speedup calculation)
        if len(event_rates) > 0 and event_rates[0] > 0:
            baseline_rate = event_rates[0]
            speedup = event_rates / baseline_rate
            # Error propagation for speedup: |speedup * (rate_error / rate)|
            speedup_errors = speedup * (event_rate_errors / event_rates)
        else:
            # Fallback to inverse runtime method
            baseline_runtime = runtimes[0]
            speedup = baseline_runtime / runtimes
            # Error propagation for speedup: |speedup * (runtime_error / runtime)|
            speedup_errors = speedup * (runtime_errors / runtimes)
        
        return speedup, speedup_errors
    
    def plot_runtime(self, output_path: Optional[Path] = None) -> plt.Figure:
        """Plot runtime vs m_step for the loaded results."""

        m_steps, runtimes, runtime_errors, thread_counts, event_rates, event_rate_errors = self.extract_m_step_data()
        
        if len(m_steps) == 0:
            print("No valid runtime data found")
            return None
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Plot runtime vs m_step
        ax.errorbar(m_steps, runtimes, yerr=runtime_errors,
                   marker='o', linestyle='-', linewidth=2,
                   markersize=6, color=tolc[0] if HAS_STYLE else 'C0')
        
        ax.set_xlabel('M Step')
        ax.set_ylabel('Runtime (seconds)')
        ax.set_title('Runtime vs M Step')
        ax.grid(True, alpha=0.3)
        
        if output_path:
            fig.savefig(output_path, dpi=300, bbox_inches='tight')
        
        return fig
    
    def plot_speedup(self, output_path: Optional[Path] = None) -> plt.Figure:
        """Plot speedup vs m_step for the loaded results."""
        
        m_steps, runtimes, runtime_errors, thread_counts, event_rates, event_rate_errors = self.extract_m_step_data()
        
        if len(m_steps) == 0:
            print("No valid runtime data found")
            return None
        
        # Calculate speedup using helper method
        speedup, speedup_errors = self.calculate_speedup(m_steps, runtimes, runtime_errors, 
                                                        event_rates, event_rate_errors)
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Plot speedup vs m_step
        ax.errorbar(m_steps, speedup, yerr=speedup_errors,
                   marker='o', linestyle='-', linewidth=2,
                   markersize=6, color=tolc[1] if HAS_STYLE else 'C1',
                   label='Actual Speedup')
        
        # Add ideal speedup line (if this looks like a scaling test)
        if len(set(thread_counts)) > 1:  # Variable thread counts
            ideal_speedup = thread_counts / thread_counts[0]
            ax.plot(m_steps, ideal_speedup, '--', color='gray', alpha=0.7, 
                   label='Ideal Speedup')
        
        ax.set_xlabel('M Step')
        ax.set_ylabel('Speedup')
        ax.set_title('Speedup vs M Step')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, np.max(m_steps) + 1)
        ax.set_ylim(0, np.max(speedup) * 1.3)
        
        if output_path:
            fig.savefig(output_path, dpi=300, bbox_inches='tight')
        
        return fig
    
    def plot_combined(self, output_path: Optional[Path] = None) -> plt.Figure:
        """Plot both runtime and speedup in subplots."""
        
        m_steps, runtimes, runtime_errors, thread_counts, event_rates, event_rate_errors = self.extract_m_step_data()
        
        if len(m_steps) == 0:
            print("No valid runtime data found")
            return None
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        # Runtime plot
        ax1.errorbar(m_steps, runtimes, yerr=runtime_errors,
                    marker='o', linestyle='-', linewidth=2,
                    markersize=6, color=tolc[0] if HAS_STYLE else 'C0')
        ax1.set_xlabel('M Step')
        ax1.set_ylabel('Runtime (seconds)')
        ax1.set_title('Runtime vs M Step')
        ax1.set_xlim(0, np.max(m_steps) + 1)
        ax1.set_ylim(0, np.max(runtimes) * 1.3)
        ax1.grid(True, alpha=0.3)
        #ax1.set_yscale('log')
        
        # Speedup plot using helper method
        speedup, speedup_errors = self.calculate_speedup(m_steps, runtimes, runtime_errors,
                                                        event_rates, event_rate_errors)
        
        ax2.errorbar(m_steps, speedup, yerr=speedup_errors,
                    marker='o', linestyle='-', linewidth=2,
                    markersize=6, color=tolc[1] if HAS_STYLE else 'C1',
                    label='Actual Speedup')
        
        # Add ideal speedup if variable thread counts
        if len(set(thread_counts)) > 1:
            ideal_speedup = thread_counts / thread_counts[0]
            ax2.plot(m_steps, ideal_speedup, '--', color='gray', alpha=0.7,
                    label='Ideal Speedup')
        
        ax2.set_xlabel('M Step')
        ax2.set_ylabel('Speedup')
        ax2.set_title('Speedup vs M Step')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(0, np.max(m_steps) + 1)
        ax2.set_ylim(0, np.max(speedup) * 1.3)
        
        plt.tight_layout()
        
        if output_path:
            fig.savefig(output_path, dpi=300, bbox_inches='tight')
        
        return fig
