"""High-level streaming interface for Mendi BLE devices."""

import asyncio
import logging
import time
from typing import AsyncIterator, Optional, Callable, List
from contextlib import asynccontextmanager

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

from .models import MendiSample, MendiSession, DeviceInfo, ConnectionState
from .parser import MendiProtobufParser
from .exceptions import (
    DeviceNotFoundError,
    PhantomConnectionError,
    ReconnectionFailedError,
    ConnectionTimeoutError
)


logger = logging.getLogger(__name__)


class MendiStream:
    """High-level interface for streaming data from Mendi devices.
    
    This class handles:
    - Device discovery and connection
    - Automatic streaming via descriptor writes
    - Packet parsing and session management
    - Reconnection on disconnect
    
    Example:
        async with MendiStream() as stream:
            async for sample in stream:
                print(f"Activity level: {sample.activity_level}")
    """
    
    # BLE UUIDs
    DEVICE_NAME = "Mendi"
    SERVICE_UUID = "fc3eabb0-c6c4-49e6-922a-6e551c455af5"
    FC3EABB5_UUID = "fc3eabb5-c6c4-49e6-922a-6e551c455af5"
    FC3EABB4_UUID = "fc3eabb4-c6c4-49e6-922a-6e551c455af5"
    
    # CCCD descriptor handle for FC3EABB5
    CCCD_HANDLE = 29
    CCCD_ENABLE = b'\x01\x00'
    
    # Streaming parameters
    TRIGGER_INTERVAL = 2.0  # seconds between descriptor writes
    RESPONSE_TIMEOUT = 3.0  # max wait for response
    
    def __init__(self, 
                 device_address: Optional[str] = None,
                 auto_reconnect: bool = True,
                 session_callback: Optional[Callable[[MendiSession], None]] = None,
                 reconnect_attempts: int = 5,
                 reconnect_timeout: int = 30,
                 connection_timeout: int = 10,
                 force_scan_on_failure: bool = True,
                 watchdog_enabled: bool = True):
        """Initialize MendiStream with enhanced reconnection capabilities.
        
        Args:
            device_address: Optional BLE MAC address. If not provided, will scan for device.
            auto_reconnect: Whether to automatically reconnect on disconnect
            session_callback: Optional callback when session ends
            reconnect_attempts: Maximum number of reconnection attempts (default: 5)
            reconnect_timeout: Maximum time to spend reconnecting in seconds (default: 30)
            connection_timeout: Time without data before assuming disconnection (default: 10)
            force_scan_on_failure: Scan for any Mendi if specific device not found (default: True)
            watchdog_enabled: Enable connection health monitoring (default: True)
        """
        self.device_address = device_address
        self.auto_reconnect = auto_reconnect
        self.session_callback = session_callback
        
        # Reconnection configuration
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_timeout = reconnect_timeout
        self.connection_timeout = connection_timeout
        self.force_scan_on_failure = force_scan_on_failure
        self.watchdog_enabled = watchdog_enabled
        
        self.client: Optional[BleakClient] = None
        self.parser = MendiProtobufParser()
        self.session = MendiSession(samples=[])
        
        self._connected = False
        self._streaming = False
        self._sample_queue: asyncio.Queue[MendiSample] = asyncio.Queue()
        self._trigger_task: Optional[asyncio.Task] = None
        
        # Enhanced state tracking
        self._connection_state = ConnectionState.DISCONNECTED
        self._last_data_time: Optional[float] = None
        self._reconnect_count = 0
        self._last_error: Optional[str] = None
        self._watchdog_task: Optional[asyncio.Task] = None
    
    async def find_device(self) -> DeviceInfo:
        """Find Mendi device via BLE scan.
        
        Returns:
            DeviceInfo for the discovered device
            
        Raises:
            RuntimeError: If no device found
        """
        logger.info(f"Scanning for {self.DEVICE_NAME} devices...")
        
        device = await BleakScanner.find_device_by_name(self.DEVICE_NAME)
        if not device:
            raise RuntimeError(f"No {self.DEVICE_NAME} device found")
        
        return DeviceInfo(
            address=device.address,
            name=device.name or self.DEVICE_NAME,
            rssi=-100  # RSSI not available from find_device_by_name on Windows
        )
    
    async def connect(self, address: Optional[str] = None) -> None:
        """Connect to Mendi device.
        
        Args:
            address: BLE MAC address. Uses stored address or scans if not provided.
        """
        if self._connected:
            return
        
        # Use provided address or stored one
        if address:
            self.device_address = address
        
        # Scan if no address
        if not self.device_address:
            device_info = await self.find_device()
            self.device_address = device_info.address
            logger.info(f"Found device at {self.device_address}")
        
        # Connect
        logger.info(f"Connecting to {self.device_address}...")
        self._connection_state = ConnectionState.CONNECTING
        self.client = BleakClient(self.device_address)
        await self.client.connect()
        self._connected = True
        self._connection_state = ConnectionState.CONNECTED
        
        # Set up notifications
        await self._setup_notifications()
        
        logger.info("Connected and notifications enabled")
    
    async def _setup_notifications(self) -> None:
        """Set up BLE notifications for data characteristics."""
        if not self.client:
            return
        
        # Enable notifications on FC3EABB5 (primary data)
        await self.client.start_notify(
            self.FC3EABB5_UUID,
            self._handle_fc3eabb5_notification
        )
        
        # Enable notifications on FC3EABB4 (secondary data)
        await self.client.start_notify(
            self.FC3EABB4_UUID,
            self._handle_fc3eabb4_notification
        )
        
        # Small delay to ensure notifications are ready
        await asyncio.sleep(0.5)
    
    def _handle_fc3eabb5_notification(self, sender: BleakGATTCharacteristic, data: bytes) -> None:
        """Handle FC3EABB5 notification."""
        # Update last data time for watchdog
        self._last_data_time = time.time()
        
        sample = self.parser.parse_fc3eabb5(data)
        if sample:
            self.session.add_sample(sample)
            self._sample_queue.put_nowait(sample)
            logger.debug(f"FC3EABB5: {sample.raw_value} (activity: {sample.activity_level})")
    
    def _handle_fc3eabb4_notification(self, sender: BleakGATTCharacteristic, data: bytes) -> None:
        """Handle FC3EABB4 notification."""
        # Update last data time for watchdog
        self._last_data_time = time.time()
        
        sample = self.parser.parse_fc3eabb4(data)
        if sample:
            # FC3EABB4 provides additional data points between FC3EABB5 updates
            self.session.add_sample(sample)
            self._sample_queue.put_nowait(sample)
            logger.debug(f"FC3EABB4: {sample.raw_value} (activity: {sample.activity_level})")
    
    async def _trigger_loop(self) -> None:
        """Background task to trigger data via descriptor writes."""
        while self._streaming and self._connected:
            try:
                # Write to CCCD descriptor to trigger data
                if self.client and self.client.is_connected:
                    await self.client.write_gatt_descriptor(
                        self.CCCD_HANDLE,
                        self.CCCD_ENABLE
                    )
                    logger.debug("Triggered data request via descriptor")
                
                # Wait before next trigger
                await asyncio.sleep(self.TRIGGER_INTERVAL)
                
            except Exception as e:
                logger.error(f"Trigger loop error: {e}")
                if self.auto_reconnect:
                    await self._handle_disconnect()
                break
    
    async def _handle_disconnect(self) -> None:
        """Handle device disconnection with enhanced retry logic."""
        self._connected = False
        self._streaming = False
        
        # Cancel tasks
        if self._trigger_task:
            self._trigger_task.cancel()
            self._trigger_task = None
        
        if self._watchdog_task:
            self._watchdog_task.cancel()
            self._watchdog_task = None
        
        logger.warning("Device disconnected")
        
        if self.auto_reconnect:
            logger.info("Attempting automatic reconnection...")
            success = await self._reconnect_with_retry()
            
            if success:
                try:
                    await self.start_streaming()
                    logger.info("Streaming resumed after reconnection")
                    # Give the stream a moment to stabilize after reconnection
                    await asyncio.sleep(1.0)
                except Exception as e:
                    logger.error(f"Failed to resume streaming: {e}")
                    raise
            else:
                raise ReconnectionFailedError(
                    f"Failed to reconnect after {self.reconnect_attempts} attempts. "
                    f"Last error: {self._last_error}"
                )
    
    async def _reconnect_with_retry(self, max_attempts: int = None) -> bool:
        """Enhanced reconnection with exponential backoff and phantom connection handling.
        
        Args:
            max_attempts: Override default max attempts
            
        Returns:
            True if reconnection successful, False otherwise
        """
        max_attempts = max_attempts or self.reconnect_attempts
        start_time = time.time()
        
        for attempt in range(max_attempts):
            # Check timeout
            if time.time() - start_time > self.reconnect_timeout:
                logger.error(f"Reconnection timeout after {self.reconnect_timeout}s")
                break
                
            try:
                # Update state
                self._connection_state = ConnectionState.RECONNECTING
                self._reconnect_count = attempt + 1
                
                # Try direct reconnection
                logger.info(f"Reconnection attempt {attempt + 1}/{max_attempts} to {self.device_address}")
                await self.connect(self.device_address)
                
                # Success
                self._connection_state = ConnectionState.CONNECTED
                self._reconnect_count = 0
                self._last_error = None
                logger.info("Reconnection successful")
                return True
                
            except Exception as e:
                self._last_error = str(e)
                
                # Check for phantom connection
                if "not found" in str(e).lower() or "could not find" in str(e).lower():
                    if attempt == 0:
                        self._connection_state = ConnectionState.PHANTOM_CONNECTION
                        logger.warning(
                            f"Device {self.device_address} not advertising. "
                            "Possible phantom connection - device may still think it's connected."
                        )
                
                # Calculate exponential backoff
                wait_time = min(2 ** attempt, 30)
                logger.info(f"Reconnection failed: {e}")
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
                
                # After 2 failures, try scanning for any Mendi device
                if attempt >= 2 and self.force_scan_on_failure:
                    logger.info("Attempting to find any available Mendi device...")
                    devices = await self._scan_for_mendi_devices(timeout=5)
                    
                    if devices:
                        # Try the device with strongest signal
                        old_address = self.device_address
                        self.device_address = devices[0].address
                        logger.info(
                            f"Found Mendi device at {self.device_address} "
                            f"(was looking for {old_address})"
                        )
                    else:
                        logger.warning("No Mendi devices found during scan")
        
        # All attempts failed
        self._connection_state = ConnectionState.FAILED
        logger.error(f"All reconnection attempts exhausted. Last error: {self._last_error}")
        return False
    
    async def _scan_for_mendi_devices(self, timeout: float = 5.0) -> List:
        """Scan for available Mendi devices.
        
        Args:
            timeout: Scan timeout in seconds
            
        Returns:
            List of found devices sorted by signal strength
        """
        from .scanner import MendiScanner
        
        logger.debug(f"Scanning for Mendi devices for {timeout}s...")
        scanner = MendiScanner(timeout=timeout)
        devices = await scanner.scan_all()
        
        if devices:
            logger.info(f"Found {len(devices)} Mendi device(s):")
            for device in devices:
                rssi = getattr(device, 'rssi', -100)
                logger.info(f"  {device.address}: RSSI {rssi} dBm")
        
        return devices
    
    async def _force_disconnect(self) -> None:
        """Force disconnection on both client and device side."""
        logger.debug("Forcing disconnection...")
        
        # Cancel tasks first
        if self._trigger_task:
            self._trigger_task.cancel()
            self._trigger_task = None
            
        if self._watchdog_task:
            self._watchdog_task.cancel()
            self._watchdog_task = None
        
        # Try to disconnect cleanly
        try:
            if self.client:
                if self.client.is_connected:
                    await self.client.disconnect()
                    logger.debug("Client disconnected")
        except Exception as e:
            logger.debug(f"Force disconnect error (often expected): {e}")
        
        # Clear state
        self._connected = False
        self._streaming = False
        self._connection_state = ConnectionState.DISCONNECTED
        self.client = None
    
    async def _connection_watchdog(self) -> None:
        """Monitor connection health based on data flow."""
        logger.debug("Connection watchdog started")
        
        while self._connected and self._streaming and self.watchdog_enabled:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                if self._last_data_time:
                    time_since_data = time.time() - self._last_data_time
                    
                    if time_since_data > self.connection_timeout:
                        logger.warning(
                            f"No data received for {time_since_data:.1f}s "
                            f"(timeout: {self.connection_timeout}s)"
                        )
                        
                        # Connection likely lost
                        logger.info("Watchdog triggering reconnection...")
                        await self._force_disconnect()
                        await self._handle_disconnect()
                        break
                    elif time_since_data > self.connection_timeout * 0.7:
                        # Warning threshold
                        logger.debug(
                            f"No data for {time_since_data:.1f}s, "
                            "approaching timeout"
                        )
                        
            except asyncio.CancelledError:
                logger.debug("Watchdog cancelled")
                break
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
                break
        
        logger.debug("Connection watchdog stopped")
    
    @property
    def connection_status(self) -> dict:
        """Get detailed connection status information.
        
        Returns:
            Dictionary with connection state and metrics
        """
        status = {
            "state": self._connection_state.value,
            "is_connected": self._connected,
            "is_streaming": self._streaming,
            "device_address": self.device_address,
            "last_data_received": self._last_data_time,
            "seconds_since_data": None,
            "reconnect_attempts": self._reconnect_count,
            "last_error": self._last_error,
            "session": {
                "samples": len(self.session.samples),
                "duration": self.session.duration,
                "points": self.session.points
            },
            "config": {
                "auto_reconnect": self.auto_reconnect,
                "reconnect_attempts": self.reconnect_attempts,
                "reconnect_timeout": self.reconnect_timeout,
                "connection_timeout": self.connection_timeout,
                "force_scan_on_failure": self.force_scan_on_failure,
                "watchdog_enabled": self.watchdog_enabled
            }
        }
        
        # Calculate time since last data
        if self._last_data_time:
            status["seconds_since_data"] = round(time.time() - self._last_data_time, 1)
        
        return status
    
    async def start_streaming(self) -> None:
        """Start the streaming process with watchdog."""
        if not self._connected:
            await self.connect()
        
        self._streaming = True
        self._last_data_time = time.time()  # Initialize data time
        
        # Start trigger loop
        self._trigger_task = asyncio.create_task(self._trigger_loop())
        
        # Start watchdog if enabled
        if self.watchdog_enabled:
            self._watchdog_task = asyncio.create_task(self._connection_watchdog())
            logger.debug("Watchdog enabled for connection monitoring")
        
        logger.info("Streaming started")
    
    async def stop_streaming(self) -> None:
        """Stop streaming and end session."""
        if not self._streaming:
            return  # Already stopped
            
        self._streaming = False
        
        # Cancel tasks
        if self._trigger_task:
            self._trigger_task.cancel()
            try:
                await self._trigger_task
            except asyncio.CancelledError:
                pass
            self._trigger_task = None
        
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            self._watchdog_task = None
        
        # End session only if it hasn't been ended
        if self.session.end_time is None:
            self.session.end_session()
            
            if self.session_callback:
                self.session_callback(self.session)
            
            logger.info(f"Session ended. Points: {self.session.points}")
    
    async def disconnect(self) -> None:
        """Disconnect from device."""
        if not self._connected and not self.client:
            return  # Already disconnected
            
        await self.stop_streaming()
        
        if self.client:
            try:
                if self.client.is_connected:
                    await self.client.disconnect()
            except (AssertionError, Exception) as e:
                logger.debug(f"Disconnect error (often expected): {e}")
            finally:
                self.client = None
        
        self._connected = False
        self._connection_state = ConnectionState.DISCONNECTED
        logger.info("Disconnected")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        await self.start_streaming()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    def __aiter__(self):
        """Make the stream iterable."""
        return self
    
    async def __anext__(self) -> MendiSample:
        """Get next sample from the stream."""
        while True:  # Keep trying while auto_reconnect is enabled
            if not self._streaming:
                raise StopAsyncIteration
            
            try:
                # Wait for sample with timeout
                sample = await asyncio.wait_for(
                    self._sample_queue.get(),
                    timeout=self.RESPONSE_TIMEOUT * 2
                )
                return sample
            except asyncio.TimeoutError:
                logger.warning("No data received - device may be off or out of range")
                if self.auto_reconnect:
                    try:
                        await self._handle_disconnect()
                        # If reconnection succeeded, continue the loop to try getting data again
                        if self._streaming:
                            continue
                    except ReconnectionFailedError:
                        # Reconnection failed, stop iteration
                        raise StopAsyncIteration
                # If auto_reconnect is False or streaming stopped, exit
                raise StopAsyncIteration


@asynccontextmanager
async def mendi_stream(device_address: Optional[str] = None) -> AsyncIterator[MendiStream]:
    """Convenience function to create a MendiStream context.
    
    Example:
        async with mendi_stream() as stream:
            async for sample in stream:
                print(f"Activity: {sample.activity_level}")
    """
    stream = MendiStream(device_address=device_address)
    try:
        await stream.connect()
        await stream.start_streaming()
        yield stream
    finally:
        await stream.disconnect()