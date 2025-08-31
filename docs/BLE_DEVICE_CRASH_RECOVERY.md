# BLE Device Crash and Recovery Guide

## Overview
This document explains why BLE devices can crash during development, how to recover from crashes, and best practices to prevent them.

## Why BLE Devices Crash During Development

### Common Causes
1. **BLE Stack Corruption**
   - Unexpected disconnections during operations
   - Malformed GATT commands
   - Invalid descriptor writes
   - Rapid state transitions

2. **Resource Exhaustion**
   - BLE chips have limited RAM (often <64KB)
   - Connection/disconnection floods
   - Notification buffer overflow
   - Command queue saturation

3. **Firmware State Machine Issues**
   - Invalid state transitions
   - Unhandled edge cases
   - Watchdog timer conflicts
   - Power management conflicts

### Vulnerable Operations
- Rapid connect/disconnect cycles
- Descriptor manipulation (especially CCCD writes)
- MTU changes during active operations
- Notification enable/disable floods
- Writing invalid data to characteristics
- Concurrent operations on multiple characteristics

## Device Recovery Methods

### 1. Battery Depletion (Most Reliable)
- Let device battery fully discharge
- May take hours to days depending on battery size
- Device will reset when powered back on

### 2. Hardware Reset Attempts
- Hold power button for extended periods (10-30 seconds)
- Try button combinations if device has multiple buttons
- Some devices have hidden reset sequences

### 3. Physical Battery Disconnect
- Only if device is openable
- Disconnect battery for 10+ seconds
- Requires technical comfort with hardware

### 4. Temperature-Based Reset (Last Resort)
- Cold: Freezer for 30-60 minutes (in sealed bag)
- May trigger low-voltage reset
- Risk of condensation damage

## Prevention Best Practices

### Connection Management
```python
# Always use proper cleanup
async def safe_disconnect(client):
    if client and client.is_connected:
        try:
            # Stop all notifications first
            for char_uuid in notifying_chars:
                await client.stop_notify(char_uuid)
            
            # Wait for operations to complete
            await asyncio.sleep(0.5)
            
            # Then disconnect
            await client.disconnect()
            
            # Wait before reconnecting
            await asyncio.sleep(2.0)
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
```

### Operation Timing
```python
# Add delays between sensitive operations
OPERATION_DELAY = 0.5  # seconds

# Between connects
await asyncio.sleep(2.0)

# Between characteristic writes
await asyncio.sleep(OPERATION_DELAY)

# Between notification toggles
await asyncio.sleep(OPERATION_DELAY)

# After MTU changes
await asyncio.sleep(1.0)
```

### Defensive Programming
```python
# Wrap all BLE operations
async def safe_write(client, uuid, data, max_retries=3):
    for attempt in range(max_retries):
        try:
            if not client.is_connected:
                return False
            
            await client.write_gatt_char(uuid, data)
            await asyncio.sleep(0.1)  # Small delay
            return True
            
        except Exception as e:
            logger.warning(f"Write attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1.0)
            
    return False
```

### Testing Strategy
1. **Start Slow**: Test one operation at a time
2. **Add Delays**: Liberal use of asyncio.sleep()
3. **Monitor Device**: Watch for LED changes, unresponsiveness
4. **Incremental Testing**: Build up complexity gradually
5. **Have Backups**: Keep spare devices for development

## Warning Signs of Impending Crash
- Device becomes slow to respond
- Inconsistent notification delivery
- Connection drops frequently
- LED behavior changes
- Power button becomes unresponsive

## Recovery Indicators
- Device powers on normally
- LED shows normal patterns
- Advertising resumes
- Accepts connections
- Responds to GATT operations

## Development Best Practices

### 1. Logging
```python
# Log all operations with timestamps
logger.info(f"[{time.time():.3f}] Writing {data.hex()} to {char_uuid}")
```

### 2. State Tracking
```python
class BLEDeviceState:
    def __init__(self):
        self.connected = False
        self.notifying_chars = set()
        self.last_operation = None
        self.operation_count = 0
```

### 3. Rate Limiting
```python
class RateLimiter:
    def __init__(self, max_ops_per_second=10):
        self.max_ops = max_ops_per_second
        self.operations = []
    
    async def check_rate(self):
        now = time.time()
        self.operations = [op for op in self.operations if now - op < 1.0]
        
        if len(self.operations) >= self.max_ops:
            wait_time = 1.0 - (now - self.operations[0])
            await asyncio.sleep(wait_time)
        
        self.operations.append(now)
```

## Emergency Procedures

If device crashes during testing:
1. **Document** exactly what operations were performed
2. **Save logs** immediately
3. **Note** device state (LED color, responsiveness)
4. **Attempt** soft reset (hold power button)
5. **Switch** to backup device
6. **Let** crashed device discharge

## Notes for Mendi Device

Based on our testing:
- Device can crash from rapid descriptor writes
- fc3eabb5 activity may indicate stress on device
- 34-second timing might be significant
- Power button becomes unresponsive when crashed
- No known hardware reset combination discovered

## Conclusion

BLE device crashes are common during development. Having multiple devices, following safe practices, and understanding recovery methods are essential for BLE development. The crashes often reveal important information about device limitations and proper initialization sequences.