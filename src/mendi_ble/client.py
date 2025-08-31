"""BLE client for communicating with Mendi devices."""

import asyncio
from typing import Optional, Callable, List
from bleak import BleakClient, BLEDevice
import logging

logger = logging.getLogger(__name__)


class MendiClient:
    """Client for communicating with Mendi devices."""
    
    # Mendi Custom Service UUIDs
    SERVICE_UUID = "fc3eabb0-c6c4-49e6-922a-6e551c455af5"
    CHAR_STATUS = "fc3eabb1-c6c4-49e6-922a-6e551c455af5"     # Read, Notify - 89-byte status
    CHAR_CMD1 = "fc3eabb2-c6c4-49e6-922a-6e551c455af5"       # Write, Notify - Commands
    CHAR_CMD2 = "fc3eabb3-c6c4-49e6-922a-6e551c455af5"       # Write, Notify - Commands
    CHAR_BASELINE = "fc3eabb4-c6c4-49e6-922a-6e551c455af5"   # Read, Notify - 3-byte @ 2Hz
    CHAR_DATA = "fc3eabb5-c6c4-49e6-922a-6e551c455af5"       # Notify - DATA STREAM (9-byte)
    CHAR_CONFIG = "fc3eabb6-c6c4-49e6-922a-6e551c455af5"     # Read, Write - Configuration
    
    CCCD_HANDLE = 29  # fc3eabb5's CCCD descriptor for triggering data
    
    def __init__(self, device: BLEDevice):
        """Initialize client.
        
        Args:
            device: BLE device to connect to
        """
        self.device = device
        self.client: Optional[BleakClient] = None
        self._notification_handler: Optional[Callable] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        
    async def connect(self):
        """Connect to the device."""
        logger.info(f"Connecting to {self.device.name} ({self.device.address})")
        self.client = BleakClient(self.device)
        await self.client.connect()
        logger.info("Connected successfully")
        
    async def disconnect(self):
        """Disconnect from the device."""
        if self.client and self.client.is_connected:
            logger.info("Disconnecting...")
            await self.client.disconnect()
            logger.info("Disconnected")
            
    async def start_notifications(self, handler: Callable[[int, bytes], None]):
        """Start receiving notifications.
        
        Args:
            handler: Callback function for notifications
        """
        if not self.client or not self.client.is_connected:
            raise RuntimeError("Not connected")
            
        self._notification_handler = handler
        await self.client.start_notify(self.NUS_RX_CHAR_UUID, handler)
        logger.info("Notifications started")
        
    async def stop_notifications(self):
        """Stop receiving notifications."""
        if self.client and self.client.is_connected:
            await self.client.stop_notify(self.NUS_RX_CHAR_UUID)
            logger.info("Notifications stopped")
            
    async def write_command(self, data: bytes):
        """Write command to device.
        
        Args:
            data: Command bytes to send
        """
        if not self.client or not self.client.is_connected:
            raise RuntimeError("Not connected")
            
        await self.client.write_gatt_char(self.NUS_TX_CHAR_UUID, data)
        logger.debug(f"Sent command: {data.hex()}")
        
    async def get_services(self) -> List:
        """Get all available services."""
        if not self.client or not self.client.is_connected:
            raise RuntimeError("Not connected")
            
        return await self.client.get_services()