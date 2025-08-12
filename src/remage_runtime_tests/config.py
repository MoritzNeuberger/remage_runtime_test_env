"""Configuration management for runtime tests."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field


@dataclass
class SimulationConfig:
    """Configuration for simulation parameters."""
    macro_template: str
    m_steps: List[int]
    n_primaries: int
    execution_mode: str  # "multithreaded_fix", "multithreaded_scaled", "multiprocessed_fix", "multiprocessed_scaled"
    physics_list: str = "FTFP_BERT"
    additional_args: List[str] = field(default_factory=list)
    output_dir: str = "/var/tmp"
    template_dir: str = "templates"
    container: str = "legendexp/remage:latest"
    executable: str = "remage"
    
    def __post_init__(self):
        if self.additional_args is None:
            self.additional_args = []
        
        # Validate execution_mode
        valid_modes = ["multithreaded_fix", "multithreaded_scaled", "multiprocessed_fix", "multiprocessed_scaled"]
        if self.execution_mode not in valid_modes:
            raise ValueError(f"execution_mode must be one of {valid_modes}")
    
    def is_multithreaded(self) -> bool:
        """Check if execution mode uses multithreading."""
        return self.execution_mode.startswith("multithreaded")
    
    def is_scaled(self) -> bool:
        """Check if execution mode scales primaries with thread/process count."""
        return self.execution_mode.endswith("_scaled")
    
    def get_thread_count(self, m_step: int) -> int:
        """Get the number of threads for a given m_step."""
        return m_step if self.is_multithreaded() else 1
    
    def get_process_count(self, m_step: int) -> int:
        """Get the number of processes for a given m_step."""
        return m_step if not self.is_multithreaded() else 1


@dataclass
class ClusterConfig:
    """Configuration for SLURM job submission."""
    partition: str = "regular"
    time_limit: str = "00:15:00"
    memory: str = "4GB"
    nodes: int = 1
    tasks_per_node: int = 1
    cpus_per_task: int = 1
    constraint: str = "cpu"
    mail_user: str = "moritz.neuberger@tum.de"
    additional_sbatch_args: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.additional_sbatch_args is None:
            self.additional_sbatch_args = []


@dataclass
class TestConfig:
    """Configuration for test execution."""
    repetitions: int = 1  # How many times to repeat each test
    dry_run: bool = False
    overwrite: bool = False
    skip_existing: bool = True


@dataclass
class Config:
    """Main configuration class."""
    simulation: SimulationConfig
    cluster: ClusterConfig
    test: TestConfig
    project_name: str = "runtime_test"
    results_file: str = "runtime_estimates.json"
    
    @classmethod
    def from_file(cls, config_path: Path) -> "Config":
        """Load configuration from JSON file."""
        with open(config_path) as f:
            data = json.load(f)
        
        # Auto-generate results_file name based on project_name if not specified
        project_name = data.get("project_name", "runtime_test")
        if "results_file" not in data:
            results_file = f"{project_name}_results.json"
        else:
            results_file = data["results_file"]
        
        sim_config = SimulationConfig(**data["simulation"])
        cluster_config = ClusterConfig(**data["cluster"])
        test_config = TestConfig(**data["test"])
        
        return cls(
            simulation=sim_config,
            cluster=cluster_config,
            test=test_config,
            project_name=project_name,
            results_file=results_file
        )
    
    def to_file(self, config_path: Path) -> None:
        """Save configuration to JSON file."""
        with open(config_path, "w") as f:
            json.dump(asdict(self), f, indent=2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def create_default(cls) -> "Config":
        """Create a default configuration."""
        sim_config = SimulationConfig(
            m_steps=[1, 2, 4, 8, 16, 32],
            n_primaries=10000,
            execution_mode="multithreaded_fix",
            additional_args=[]
        )
        
        cluster_config = ClusterConfig()
        test_config = TestConfig()
        
        return cls(
            simulation=sim_config,
            cluster=cluster_config,
            test=test_config
        )
