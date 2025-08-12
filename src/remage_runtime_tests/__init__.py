"""REMAGE Runtime Testing Suite

A package for systematic runtime testing of REMAGE simulations.
"""

__version__ = "0.1.0"

from .simulation import SimulationRunner
from .submission import JobSubmitter
from .plotting import ResultsPlotter
from .config import Config

__all__ = ["SimulationRunner", "JobSubmitter", "ResultsPlotter", "Config"]
