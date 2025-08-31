"""BLE device scanner for finding Mendi devices."""

import asyncio
from typing import Optional, List
from bleak import BleakScanner, BLEDevice
from bleak.backends.scanner import AdvertisementData


class MendiScanner:
    """Scanner for finding Mendi devices via BLE."""
    
    MENDI_NAME = "Mendi"
    
    def __init__(self, timeout: float = 10.0):
        """Initialize scanner.
        
        Args:
            timeout: Maximum time to scan in seconds
        """
        self.timeout = timeout
        
    async def find_device(self, address: Optional[str] = None) -> Optional[BLEDevice]:
        """Find a Mendi device.
        
        Args:
            address: Specific device address to find, or None for any Mendi
            
        Returns:
            BLEDevice if found, None otherwise
        """
        if address:
            # Find specific device
            device = await BleakScanner.find_device_by_address(address, timeout=self.timeout)
            return device
        else:
            # Find any Mendi device
            def is_mendi(device: BLEDevice, adv: AdvertisementData) -> bool:
                return device.name is not None and self.MENDI_NAME in device.name
                
            device = await BleakScanner.find_device_by_filter(is_mendi, timeout=self.timeout)
            return device
            
    async def scan_all(self) -> List[BLEDevice]:
        """Scan for all Mendi devices.
        
        Returns:
            List of found Mendi devices
        """
        devices = await BleakScanner.discover(timeout=self.timeout)
        
        # Filter for Mendi devices
        mendi_devices = [
            d for d in devices 
            if d.name and self.MENDI_NAME in d.name
        ]
        
        return mendi_devices