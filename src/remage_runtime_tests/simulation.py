"""Individual simulation runner module."""

import json
import subprocess
import time
import re
import multiprocessing
from pathlib import Path
from typing import Dict, Any, Optional, List
import tempfile
import os
import numpy as np

from .config import Config


class SimulationRunner:
    """Runs individual REMAGE simulations and measures runtime."""
    
    def __init__(self, config: Config, template_path: Path):
        self.config = config
        self.template_path = template_path
        
    def prepare_macro(self, m_step: int, output_file: Path) -> Path:
        """Prepare a macro file from template by substituting placeholders."""
        with open(self.template_path) as f:
            template_content = f.read()
        
        # Calculate number of primaries based on execution mode
        n_primaries = self.config.simulation.n_primaries
        if self.config.simulation.is_scaled():
            n_primaries = self.config.simulation.n_primaries * m_step
            
        # Get template directory
        template_dir = Path(self.config.simulation.template_dir)
        
        # Calculate thread/process counts
        n_threads = self.config.simulation.get_thread_count(m_step)
        n_processes = self.config.simulation.get_process_count(m_step)
            
        # Substitute new-style placeholders
        macro_content = template_content.replace(
            "{TEMPLATE_DIR}", str(template_dir)
        ).replace(
            "{N_PRIMARIES}", str(n_primaries)
        ).replace(
            "{N_THREADS}", str(n_threads)
        ).replace(
            "{N_PROCESSES}", str(n_processes)
        ).replace(
            "{OUTPUT_DIR}", str(output_file.parent)
        ).replace(
            "{OUTPUT_FILE}", str(output_file.name)
        )
        
        # Substitute legacy placeholders (for backward compatibility)
        macro_content = macro_content.replace(
            "NUMBER_PIMARY_PLACEHOLDER", str(n_primaries)
        ).replace(
            "OUTPUT_HDF5_PLACEHOLDER", str(output_file)
        )
        
        # Create temporary macro file
        temp_macro = tempfile.NamedTemporaryFile(
            mode='w', suffix='.mac', delete=False
        )
        temp_macro.write(macro_content)
        temp_macro.close()
        
        return Path(temp_macro.name)
    
    def run_simulation(self, macro_path: Path, m_step: int) -> str:
        """Run a single simulation and return output."""
        if self.config.test.dry_run:
            return f"Dry run: would run simulation with {macro_path} for m_step {m_step}"
        
        # Build remage command based on execution mode
        cmd = [self.config.simulation.executable, str(macro_path)]
        
        if self.config.simulation.is_multithreaded():
            # Add threading arguments
            thread_count = self.config.simulation.get_thread_count(m_step)
            cmd.extend(["--threads", str(thread_count)])
        else:
            # For multiprocessed, we'll handle this in the job execution
            cmd.extend(["--threads", "1"])
        
        # Add additional arguments
        cmd.extend(self.config.simulation.additional_args)
        # Handle container execution
        if self.config.simulation.container:
            if self.config.simulation.executable == "remage":
                # Use container's built-in remage binary
                command = (
                    f"shifter --image={self.config.simulation.container} bash -c \""
                    "module unload mpich 2>/dev/null || true; "
                    "export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH; "
                    f"/opt/remage/bin/remage {macro_path} {' '.join(cmd[2:])}\""
                )
            else:
                # Use custom executable
                lib_path = Path(self.config.simulation.executable).parent.parent / "lib"
                command = (
                    f"shifter --image={self.config.simulation.container} bash -c \""
                    "module unload mpich 2>/dev/null || true; "
                    "source /opt/geant4/bin/geant4.sh; "
                    f"export LD_LIBRARY_PATH={lib_path}:/usr/lib/x86_64-linux-gnu:/opt/geant4/lib:/opt/root/lib:/opt/bxdecay0/lib; "
                    f"{' '.join(cmd)}\""
                )
        else:
            # Local execution
            if self.config.simulation.executable != "remage":
                lib_path = Path(self.config.simulation.executable).parent.parent / "lib"
                if lib_path.exists():
                    command = (
                        f"export LD_LIBRARY_PATH={lib_path}:$LD_LIBRARY_PATH && "
                        f"{' '.join(cmd)}"
                    )
                else:
                    command = ' '.join(cmd)
            else:
                command = ' '.join(cmd)
        
        # Execute command
        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        output, _ = process.communicate()
        return output.decode('utf-8')
    
    def extract_runtime(self, output: str) -> Optional[float]:
        """Extract runtime in seconds from simulation output."""
        lines = output.split('\n')
        last_lines = lines[-10:]
        
        for line in last_lines:
            match = re.search(
                r'run time was (\d+)\s+days,\s+(\d+)\s+hours,\s+(\d+)\s+minutes and (\d+)\s+seconds',
                line
            )
            if match:
                days, hours, minutes, seconds = match.groups()
                total_seconds = (
                    int(days) * 24 * 60 * 60 + 
                    int(hours) * 60 * 60 + 
                    int(minutes) * 60 + 
                    int(seconds)
                )
                return float(total_seconds)
        return None
    
    def extract_eventrate(self, output: str) -> Optional[float]:
        """Extract event rate from simulation output."""
        lines = output.split('\n')
        last_lines = lines[-10:]
        
        for line in last_lines:
            match = re.search(
                r"(\d+\.\d+(?:e[+-]\d+)?)\s*seconds/event\s*=\s*(\d+\.\d+(?:e[+-]\d+)?|\d+)\s*events/second",
                line
            )
            if match:
                return float(match.group(2))
        return None
    
    def run_single_test(self, index: int, m_step: int) -> Optional[List[float]]:
        """Run a single test iteration."""
        start_time = time.time()
        
        # Create output file path
        timestamp = int(time.time() * 1000)  # milliseconds for uniqueness
        output_file = Path(self.config.simulation.output_dir) / f"runtime_test_m{m_step}_{index}_{timestamp}.hdf5"
        
        # Prepare macro
        try:
            macro_path = self.prepare_macro(m_step, output_file)
            output = self.run_simulation(macro_path, m_step)
            
            # Clean up temporary macro
            if not self.config.test.dry_run:
                os.unlink(macro_path)
            
            # Extract metrics
            runtime = self.extract_runtime(output)
            eventrate = self.extract_eventrate(output)
            
            end_time = time.time()
            process_runtime = end_time - start_time
            
            # Clean up output file (we only care about runtime)
            if output_file.exists():
                os.unlink(output_file)
            
            return [runtime, eventrate, process_runtime]
            
        except Exception as e:
            print(f"Error in test {index} for m_step {m_step}: {e}")
            return None
    
    def run_m_step_tests(self, m_step: int, output_dir: Path) -> Optional[Dict[str, Any]]:
        """Run all tests for a specific m_step value."""
        # Generate m_step-specific filename
        base_name = self.config.results_file.replace('_results.json', '')
        results_filename = f"{base_name}_m{m_step}_results.json"
        results_file = output_dir / results_filename
        
        # Check if results already exist
        if results_file.exists() and not self.config.test.overwrite:
            if self.config.test.skip_existing:
                print(f"Skipping m_step {m_step}: results already exist")
                with open(results_file) as f:
                    return json.load(f)
            
        print(f"Running tests for m_step {m_step}")
        
        # Run tests based on execution mode
        if self.config.simulation.is_multithreaded():
            # Multithreaded execution - run tests in parallel locally
            with multiprocessing.Pool(processes=1) as pool:  # Use single process for consistency
                results = pool.starmap(
                    self.run_single_test,
                    [(i, m_step) for i in range(self.config.test.repetitions)]
                )
        else:
            # Multiprocessed execution - run multiple processes in parallel
            results = []
            process_count = self.config.simulation.get_process_count(m_step)
            
            for rep in range(self.config.test.repetitions):
                # Run multiple processes in parallel and take the maximum runtime (bottleneck)
                with multiprocessing.Pool(processes=process_count) as pool:
                    batch_results = pool.starmap(
                        self.run_single_test,
                        [(proc, m_step) for proc in range(process_count)]
                    )
                
                # Filter valid results and take max runtime, min eventrate
                valid_batch = [r for r in batch_results if r is not None and r[0] is not None]
                if valid_batch:
                    batch_array = np.array(valid_batch)
                    max_runtime = np.max(batch_array[:, 0])
                    min_eventrate = np.min(batch_array[:, 1]) if batch_array.shape[1] > 1 else None
                    max_process_runtime = np.max(batch_array[:, 2])
                    results.append([max_runtime, min_eventrate, max_process_runtime])
        
        # Process results
        valid_results = [r for r in results if r is not None and r[0] is not None]
        
        if not valid_results:
            print(f"No valid results for m_step {m_step}")
            return None
        
        # Calculate statistics
        runtimes = [r[0] for r in valid_results]
        eventrates = [r[1] for r in valid_results if r[1] is not None]
        process_runtimes = [r[2] for r in valid_results]
        
        # Calculate primaries used
        n_primaries = self.config.simulation.n_primaries
        if self.config.simulation.is_scaled():
            n_primaries = self.config.simulation.n_primaries * m_step
            if "electron" in str(self.template_path):
                n_primaries = 2 * n_primaries
        
        result_data = {
            "m_step": m_step,
            "template": str(self.template_path),
            "runtime": {
                "val": float(np.mean(runtimes)),
                "std": float(np.std(runtimes))
            },
            "event_rate": {
                "val": float(np.mean(eventrates)) if eventrates else None,
                "std": float(np.std(eventrates)) if eventrates else None
            },
            "process_runtime": {
                "val": float(np.mean(process_runtimes)),
                "std": float(np.std(process_runtimes))
            },
            "raw": {
                "runtimes": runtimes,
                "eventrates": eventrates,
                "process_runtimes": process_runtimes
            },
            "n_prims": n_primaries,
            "config": self.config.to_dict()
        }
        
        # Save results
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(results_file, 'w') as f:
            json.dump(result_data, f, indent=4)
        
        print(f"Results saved for m_step {m_step}")
        return result_data
