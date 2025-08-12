"""Job submission module for SLURM clusters."""

import subprocess
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
import os

from .config import Config


class JobSubmitter:
    """Handles SLURM job submission for runtime tests."""
    
    def __init__(self, config: Config, base_dir: Path, config_file_path: Path):
        self.config = config
        self.base_dir = base_dir
        self.config_file_path = config_file_path
        self.slurm_dir = base_dir / ".slurm"
        self.output_dir = base_dir / ".output"
        
        # Create directories
        self.slurm_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
    
    def create_slurm_script(self, template_path: Path, m_step: int, job_name: str) -> str:
        """Create a SLURM script for a specific test configuration."""
        
        # Calculate resource requirements   
        nodes_needed = 1
        
        # Build script content
        script_content = f"""#!/bin/bash

#SBATCH -q {self.config.cluster.partition}
#SBATCH --constraint={self.config.cluster.constraint}
#SBATCH -N {nodes_needed}
#SBATCH -t {self.config.cluster.time_limit}
#SBATCH -J {job_name}
#SBATCH -o {self.output_dir}/output_{job_name}.o%j
#SBATCH --mail-type=begin,end,fail
#SBATCH --mail-user={self.config.cluster.mail_user}
"""
        
        # Add additional SBATCH arguments
        for arg in self.config.cluster.additional_sbatch_args:
            script_content += f"#SBATCH {arg}\n"
        
        script_content += f"""
# Unload any conflicting modules
module unload mpich 2>/dev/null || true

# Set library path
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

# Change to base directory
cd {self.base_dir}

# Run the test
srun python -c "
import sys
sys.path.insert(0, '{self.base_dir}/src')
from remage_runtime_tests.cli import run_m_step
sys.argv = ['run_m_step', '--config-file', '{self.config_file_path}', '--m-step', '{m_step}', '--output-dir', 'results/{self.config.project_name}']
run_m_step()
"
"""
        
        return script_content
    
    def submit_job(self, script_content: str, job_name: str) -> Optional[str]:
        """Submit a SLURM job and return job ID."""
        script_path = self.slurm_dir / f"slurm_{job_name}.sh"
        
        # Write script
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make executable
        os.chmod(script_path, 0o755)
        
        if self.config.test.dry_run:
            print(f"Dry run: would submit {script_path}")
            return None
        
        # Submit job
        try:
            result = subprocess.run(
                ['sbatch', str(script_path)],
                capture_output=True, text=True, check=True
            )
            
            job_id_match = re.search(r'Submitted batch job (\d+)', result.stdout)
            if job_id_match:
                job_id = job_id_match.group(1)
                print(f"Submitted job {job_id} for {job_name}")
                return job_id
            else:
                print(f"Job submitted for {job_name}, but couldn't extract job ID")
                return None
                
        except subprocess.CalledProcessError as e:
            print(f"Error submitting job for {job_name}: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            return None
    
    def submit_all_jobs(self, template_path: Path) -> Dict[str, Dict]:
        """Submit jobs for all m_steps in the configuration."""
        template_name = template_path.stem
        submitted_jobs = {}
        skipped_jobs = []
        
        for m_step in self.config.simulation.m_steps:
            job_name = f"{template_name}_m{m_step}"
            
            # Check if results already exist in project-specific directory
            results_dir = self.base_dir / "results" / self.config.project_name
            base_name = self.config.results_file.replace('_results.json', '')
            results_filename = f"{base_name}_m{m_step}_results.json"
            results_file = results_dir / results_filename
            
            if results_file.exists() and self.config.test.skip_existing and not self.config.test.overwrite:
                print(f"Skipping {job_name}: results already exist")
                skipped_jobs.append(job_name)
                continue
            
            # Respect max jobs if there are too many m_steps (optional safety)
            if len(submitted_jobs) >= 100:  # Hard limit for safety
                print(f"Reached safety limit of 100 jobs")
                break
            
            # Calculate cores needed for this job
            cores_for_job = 256
            # Create and submit job
            script_content = self.create_slurm_script(template_path, m_step, job_name)
            
            if self.config.test.dry_run:
                print(f"\\n--- SLURM script for {job_name} ---")
                print(script_content)
                print("--- End of script ---\\n")
            else:
                job_id = self.submit_job(script_content, job_name)
                if job_id:
                    submitted_jobs[job_name] = {
                        'job_id': job_id,
                        'template': str(template_path),
                        'm_step': m_step,
                        'execution_mode': self.config.simulation.execution_mode,
                        'cores': cores_for_job
                    }
        
        # Save job information
        if not self.config.test.dry_run and submitted_jobs:
            jobs_file = self.base_dir / "submitted_jobs.json"
            
            # Load existing jobs if file exists
            existing_jobs = {}
            if jobs_file.exists():
                with open(jobs_file) as f:
                    existing_jobs = json.load(f)
            
            # Merge with new jobs
            existing_jobs.update(submitted_jobs)
            
            with open(jobs_file, 'w') as f:
                json.dump(existing_jobs, f, indent=2)
            
            print(f"\\nSubmitted {len(submitted_jobs)} jobs")
            print(f"Skipped {len(skipped_jobs)} jobs (already completed)")
            print(f"Job information saved to {jobs_file}")
            print("\\nTo monitor jobs: squeue -u $USER")
            print("To cancel all jobs: scancel -u $USER")
        
        elif self.config.test.dry_run:
            base_name = self.config.results_file.replace('_results.json', '')
            results_dir = self.base_dir / "results" / self.config.project_name
            total_would_submit = len([m for m in self.config.simulation.m_steps 
                                    if not (results_dir / f"{base_name}_m{m}_results.json").exists() 
                                    or not self.config.test.skip_existing or self.config.test.overwrite])
            print(f"\\nDry run summary:")
            print(f"Would submit: {total_would_submit} jobs")
            print(f"Would skip: {len(skipped_jobs)} jobs")
        
        return submitted_jobs
    
    def check_job_status(self, job_ids: List[str]) -> Dict[str, str]:
        """Check the status of submitted jobs."""
        try:
            result = subprocess.run(
                ['squeue', '-j', ','.join(job_ids), '--format=%i,%T'],
                capture_output=True, text=True, check=True
            )
            
            status_dict = {}
            for line in result.stdout.strip().split('\\n')[1:]:  # Skip header
                if line:
                    job_id, status = line.split(',')
                    status_dict[job_id] = status
            
            return status_dict
            
        except subprocess.CalledProcessError as e:
            print(f"Error checking job status: {e}")
            return {}
    
    def cancel_jobs(self, job_ids: List[str]) -> bool:
        """Cancel submitted jobs."""
        try:
            subprocess.run(
                ['scancel'] + job_ids,
                check=True
            )
            print(f"Cancelled {len(job_ids)} jobs")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"Error cancelling jobs: {e}")
            return False
