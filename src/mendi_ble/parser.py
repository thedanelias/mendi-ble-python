"""Mendi BLE packet parser for protobuf-encoded data."""

from typing import Optional
import logging
from datetime import datetime

from .models import MendiSample


logger = logging.getLogger(__name__)


class MendiProtobufParser:
    """Parser for Mendi device protobuf packets.
    
    The Mendi device sends data in two formats:
    - FC3EABB5: 9-byte protobuf messages (primary data stream)
    - FC3EABB4: 3-byte simplified messages (secondary stream)
    
    Both contain the same sensor data at different update rates.
    """
    
    # Expected packet headers
    FC3EABB5_HEADER = b'\x0a\x03\x08'
    FC3EABB5_TAIL = b'\x1d\x10\x01\x18\x01'
    FC3EABB4_HEADER = b'\x08'
    FC3EABB4_TAIL = b'\x20'
    
    def __init__(self):
        """Initialize the parser."""
        self._packet_count = 0
        self._error_count = 0
    
    def parse_fc3eabb5(self, data: bytes) -> Optional[MendiSample]:
        """Parse 9-byte FC3EABB5 protobuf packet.
        
        Packet structure:
        - Bytes 0-2: Header (0x0a 0x03 0x08)
        - Byte 3: Sensor data value
        - Byte 4: Varies (part of protobuf encoding)
        - Bytes 5-8: Tail (0x10 0x01 0x18 0x01)
        
        Args:
            data: Raw packet bytes
            
        Returns:
            MendiSample if parsing successful, None otherwise
        """
        if len(data) != 9:
            logger.debug(f"FC3EABB5: Invalid packet length {len(data)}")
            self._error_count += 1
            return None
        
        # Verify header
        if data[:3] != self.FC3EABB5_HEADER:
            logger.debug(f"FC3EABB5: Invalid header {data[:3].hex()}")
            self._error_count += 1
            return None
        
        # Extract sensor value
        sensor_value = data[3]
        
        # Convert to HbO/HbR approximation (simplified conversion)
        # The actual conversion would need calibration data
        # For now, treat lower values as higher oxygenation
        baseline = 195  # Approximate baseline from device observations
        delta = baseline - sensor_value
        
        # Create sample with approximated values
        # HbO typically ranges 80-120 µM, HbR 40-60 µM
        hbo = 100.0 + delta * 2.0    # Simplified conversion
        hbr = 50.0 - delta * 0.5     # Inverse relationship
        
        self._packet_count += 1
        
        return MendiSample(
            timestamp=datetime.now(),
            hbo=hbo,
            hbr=hbr,
            quality=1.0,
            raw_value=sensor_value,
            characteristic='fc3eabb5'
        )
    
    def parse_fc3eabb4(self, data: bytes) -> Optional[MendiSample]:
        """Parse 3-byte FC3EABB4 packet.
        
        Packet structure:
        - Byte 0: Header (0x08)
        - Byte 1: Sensor data value
        - Byte 2: Tail (0x20)
        
        Args:
            data: Raw packet bytes
            
        Returns:
            MendiSample if parsing successful, None otherwise
        """
        if len(data) != 3:
            logger.debug(f"FC3EABB4: Invalid packet length {len(data)}")
            self._error_count += 1
            return None
        
        # Verify header and tail
        if data[0] != 0x08 or data[2] != 0x20:
            logger.debug(f"FC3EABB4: Invalid format {data.hex()}")
            self._error_count += 1
            return None
        
        # Extract sensor value
        sensor_value = data[1]
        
        # Convert to HbO/HbR approximation (same logic as FC3EABB5)
        baseline = 195  # Approximate baseline from device observations
        delta = baseline - sensor_value
        
        # Create sample with approximated values
        hbo = 100.0 + delta * 2.0    # Simplified conversion
        hbr = 50.0 - delta * 0.5     # Inverse relationship
        
        self._packet_count += 1
        
        return MendiSample(
            timestamp=datetime.now(),
            hbo=hbo,
            hbr=hbr,
            quality=1.0,
            raw_value=sensor_value,
            characteristic='fc3eabb4'
        )
    
    def parse(self, data: bytes, characteristic: str) -> Optional[MendiSample]:
        """Parse packet based on characteristic UUID.
        
        Args:
            data: Raw packet bytes
            characteristic: BLE characteristic UUID or short name
            
        Returns:
            MendiSample if parsing successful, None otherwise
        """
        # Handle full UUIDs or short names
        if 'abb5' in characteristic.lower():
            return self.parse_fc3eabb5(data)
        elif 'abb4' in characteristic.lower():
            return self.parse_fc3eabb4(data)
        else:
            logger.warning(f"Unknown characteristic: {characteristic}")
            return None
    
    @property
    def stats(self) -> dict:
        """Get parser statistics."""
        return {
            'packets_parsed': self._packet_count,
            'errors': self._error_count,
            'success_rate': self._packet_count / (self._packet_count + self._error_count) 
                           if (self._packet_count + self._error_count) > 0 else 0
        }