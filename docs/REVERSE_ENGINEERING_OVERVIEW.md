# Mendi BLE Reverse Engineering Overview

## Executive Summary

This document details the successful reverse engineering of the Mendi fNIRS (functional near-infrared spectroscopy) headband's Bluetooth Low Energy (BLE) protocol. Through systematic exploration using only Python and the Bleak library, we discovered the device's unique request-response streaming mechanism and implemented a complete client library for real-time brain oxygenation data acquisition.

## The Challenge

The Mendi headband is a consumer neurofeedback device that measures prefrontal cortex activity through fNIRS technology. While the device has official mobile apps, no public API or protocol documentation existed for direct integration. Our goal was to enable programmatic access to the brain oxygenation data stream for research and development purposes.

## Methodology

### Phase 1: Device Discovery and Service Enumeration
**Scripts: 01_discover_device.py, 02_connect_and_explore.py**

We began by scanning for the Mendi device and systematically cataloging its BLE services and characteristics. Key findings:
- Custom service UUID: `fc3eabb0-c6c4-49e6-922a-6e551c455af5`
- Six characteristics with different read/write/notify properties
- No standard BLE protocols (not Nordic UART or similar)

### Phase 2: Command Pattern Discovery
**Scripts: 05_discover_commands.py through 10_exhaustive_discovery.py**

Through methodical testing of command bytes across all writable characteristics, we discovered:
- The device responds to a `0x0808` command on characteristics fc3eabb2 and fc3eabb3
- This triggers initial packet responses but not continuous streaming
- Response packets contained structured data with consistent headers

### Phase 3: Protocol Analysis
**Scripts: 11_advanced_ble_discovery.py through 14_binary_protocol_analysis.py**

Deeper analysis revealed:
- 9-byte data packets on characteristic fc3eabb5 with format: `0a 03 08 XX 1d 10 01 18 01`
- The variable byte (position 3) contains the sensor reading
- Packets appeared to use Protocol Buffer (protobuf) encoding
- No automatic continuous streaming despite various command combinations

### Phase 4: The Breakthrough - Descriptor Manipulation
**Scripts: 17_fc3eabb5_descriptor_manipulation.py, 18_continuous_streaming_via_descriptor.py**

The critical discovery came when examining BLE descriptors:
- **Writing to the CCCD (Client Characteristic Configuration Descriptor) of fc3eabb5 triggers a data packet**
- Each descriptor write causes the device to send one data packet after ~2-3 seconds
- This creates a request-response pattern rather than traditional streaming

### Phase 5: Implementation and Optimization
**Scripts: 19_advanced_dual_capture.py through 24_reconnection_test.py**

With the protocol understood, we:
- Implemented continuous streaming by periodic descriptor writes
- Added data visualization and analysis tools
- Built robust reconnection logic for production use
- Created a high-level Python API (`MendiStream`)

## Technical Details

### The Streaming Mechanism

```python
# Traditional BLE streaming (NOT how Mendi works):
await client.start_notify(characteristic, handler)
# Device sends data continuously

# Mendi's unique approach:
await client.start_notify(CHAR_DATA, handler)
while streaming:
    # Write to descriptor to request next packet
    await client.write_gatt_descriptor(CCCD_HANDLE, b'\x01\x00')
    await asyncio.sleep(2.0)  # Wait for response
```

### Data Packet Structure

```
Position: 0  1  2  3  4  5  6  7  8
Value:    0a 03 08 XX 1d 10 01 18 01
                   ^^
                   Sensor data (varies based on measurement)
```

### Key Characteristics

| UUID Suffix | Properties | Purpose |
|------------|------------|---------|
| fc3eabb1 | Read, Notify | 89-byte device status |
| fc3eabb2 | Write, Notify | Command interface |
| fc3eabb3 | Write, Notify | Command interface |
| fc3eabb4 | Read, Notify | 3-byte baseline data |
| fc3eabb5 | Notify | **Data stream (9-byte packets)** |
| fc3eabb6 | Read, Write | Configuration |

## Challenges Overcome

1. **No Documentation**: Started with zero knowledge of the protocol
2. **Non-Standard Streaming**: Device doesn't follow typical BLE streaming patterns
3. **WSL Limitations**: Bluetooth unavailable in WSL, requiring Windows testing
4. **Protocol Obfuscation**: Data uses protobuf encoding requiring careful analysis
5. **Timing Sensitivity**: Descriptor writes must be properly timed to maintain stream

## Key Insights

1. **Request-Response Pattern**: Unlike most BLE devices that stream continuously, Mendi requires active polling via descriptor writes
2. **Optimal Timing**: 2-second intervals between descriptor writes provides stable streaming
3. **No Button Required**: Device auto-calibrates and begins responding to BLE commands without physical interaction
4. **Robust Protocol**: The device handles reconnections well with proper initialization

## Tools and Approach

- **Python-First**: All exploration done using Python and Bleak library
- **No External Tools**: Avoided dependency on nRF Connect, Wireshark, etc.
- **Systematic Testing**: 24 progressive scripts building on each discovery
- **Real Device Testing**: All findings validated against actual hardware

## Final Implementation

The resulting `mendi_ble` library provides:
- Automatic device discovery and connection
- Continuous data streaming with the discovered protocol
- Automatic reconnection on disconnection
- Clean Python API for integration
- Full async/await support

## Conclusion

Through methodical exploration and creative problem-solving, we successfully reverse-engineered the Mendi BLE protocol without any documentation or external tools. The key breakthrough was discovering the unique descriptor-based streaming mechanism, which differs from standard BLE implementations. This work enables researchers and developers to directly interface with Mendi devices for custom applications and research.

## Ethical Considerations

This reverse engineering was performed:
- For interoperability and research purposes
- Without circumventing any security measures
- Using only publicly broadcast BLE data
- To enable legitimate use cases for device owners

The resulting library empowers users to access data from devices they own, promoting open science and innovation in the neurofeedback space.