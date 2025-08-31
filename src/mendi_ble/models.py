"""Data models for Mendi BLE communication."""

from dataclasses import dataclass
from typing import Optional, Literal, List
from datetime import datetime
from enum import Enum
import time


class ConnectionState(Enum):
    """Connection state enumeration for detailed status tracking."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    PHANTOM_CONNECTION = "phantom_connection"
    FAILED = "failed"


@dataclass
class MendiSample:
    """A single data sample from the Mendi device.
    
    Attributes:
        timestamp: When sample was received
        hbo: Oxygenated hemoglobin value
        hbr: Deoxygenated hemoglobin value
        quality: Signal quality (0-1)
        raw_value: Raw sensor value (for backward compatibility)
        characteristic: Which BLE characteristic provided this data
    """
    timestamp: datetime
    hbo: float
    hbr: float
    quality: float = 1.0
    raw_value: Optional[int] = None
    characteristic: Optional[Literal['fc3eabb5', 'fc3eabb4']] = None
    
    @property
    def activity_level(self) -> float:
        """Convert raw value to activity level.
        
        Lower raw values indicate higher mental activity.
        Returns a value where higher = more activity.
        """
        if self.raw_value is not None:
            return 200 - self.raw_value
        # Use HbO for activity if no raw value
        return abs(self.hbo)
    
    @property
    def normalized_activity(self) -> float:
        """Get activity level normalized to 0-1 range.
        
        Based on observed range of 187-199:
        - 0.0 = lowest activity (raw value 199)
        - 1.0 = highest activity (raw value 187)
        """
        if self.raw_value is not None:
            min_raw = 187
            max_raw = 199
            clamped = max(min_raw, min(max_raw, self.raw_value))
            return (max_raw - clamped) / (max_raw - min_raw)
        # Use normalized HbO if no raw value
        return min(1.0, abs(self.hbo) / 200.0)


@dataclass
class MendiSession:
    """Represents a complete Mendi session with scoring.
    
    Attributes:
        samples: List of all samples collected
        baseline: Baseline value for score calculation
        start_time: Session start timestamp
        end_time: Session end timestamp (if ended)
    """
    samples: list[MendiSample]
    baseline: Optional[float] = None
    start_time: float = 0
    end_time: Optional[float] = None
    
    def __post_init__(self):
        if self.start_time == 0:
            self.start_time = time.time()
    
    @property
    def duration(self) -> float:
        """Session duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time
    
    @property
    def cumulative_score(self) -> float:
        """Calculate raw cumulative score (before scaling)."""
        if not self.baseline or not self.samples:
            return 0.0
        
        score = 0.0
        for sample in self.samples:
            change = self.baseline - sample.raw_value
            if change > 0:  # Only count improvements
                score += change
        return score
    
    @property
    def points(self) -> int:
        """Calculate session points (as shown in Mendi app)."""
        return int(self.cumulative_score * 1.05)
    
    def add_sample(self, sample: MendiSample) -> None:
        """Add a new sample to the session."""
        self.samples.append(sample)
        
        # Set baseline from first few samples
        if self.baseline is None and len(self.samples) >= 5:
            # Use average of first 5 samples as baseline
            avg = sum(s.raw_value for s in self.samples[:5]) / 5
            self.baseline = avg
    
    def end_session(self) -> None:
        """Mark the session as ended."""
        self.end_time = time.time()


@dataclass 
class DeviceInfo:
    """Information about a discovered Mendi device.
    
    Attributes:
        address: BLE MAC address
        name: Device name (usually "Mendi")
        rssi: Signal strength
        firmware_version: Firmware version if available
        model: Device model if available
    """
    address: str
    name: str
    rssi: int
    firmware_version: Optional[str] = None
    model: Optional[str] = None


@dataclass
class Session:
    """Session data for scoring calculations.
    
    Attributes:
        device_address: BLE device address
        start_time: Session start time
        baseline: Baseline sample for calculations
        samples: List of all samples
        sample_rate: Sampling rate in Hz
    """
    device_address: str
    start_time: Optional[datetime]
    baseline: Optional[MendiSample]
    samples: List[MendiSample]
    sample_rate: float = 20.0