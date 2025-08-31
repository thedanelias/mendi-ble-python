"""
Mendi BLE Python Library

A Python library for interfacing with Mendi fNIRS devices via Bluetooth Low Energy.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

# Core imports
from .stream import MendiStream, mendi_stream
from .models import MendiSample, MendiSession, DeviceInfo, Session, ConnectionState
from .parser import MendiProtobufParser
from .scanner import MendiScanner
from .client import MendiClient
from .visualization_plotly import MendiPlotlyVisualizer, PlotlyVisualizationConfig
from .scoring import AdvancedScoringEngine, ScoringWeights
from .exceptions import (
    MendiConnectionError,
    DeviceNotFoundError,
    PhantomConnectionError,
    ReconnectionFailedError,
    ConnectionTimeoutError
)

__all__ = [
    "__version__",
    # Main streaming interface
    "MendiStream",
    "mendi_stream",
    # Scanner and Client
    "MendiScanner",
    "MendiClient",
    # Data models
    "MendiSample",
    "MendiSession", 
    "DeviceInfo",
    "Session",
    "ConnectionState",
    # Parser (advanced usage)
    "MendiProtobufParser",
    # Visualization
    "MendiPlotlyVisualizer", 
    "PlotlyVisualizationConfig",
    # Scoring
    "AdvancedScoringEngine",
    "ScoringWeights",
    # Exceptions
    "MendiConnectionError",
    "DeviceNotFoundError",
    "PhantomConnectionError",
    "ReconnectionFailedError",
    "ConnectionTimeoutError",
]