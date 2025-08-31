# Mendi Device Profile

## Device Information

- **Device**: Mendi.io Single Channel fNIRS
- **Model**: v4
- **Hardware Version**: r2.2a-ub1
- **Firmware**: 1.0.4
- **MAC Address**: C3:DF:6C:5E:82:9E
- **FCC ID**: RYYEYSHJN

## Technical Specifications

### Sensor Type
- **Technology**: Functional Near-Infrared Spectroscopy (fNIRS)
- **Channels**: Single channel
- **Location**: Prefrontal cortex (Fp1/Fp2 region)
- **Measurements**: HbO (oxygenated hemoglobin) and HbR (deoxygenated hemoglobin)

### Connectivity
- **Protocol**: Bluetooth Low Energy (BLE)
- **BLE Version**: Compatible with BLE 4.0+
- **Connection Type**: GATT Server

### Hardware Details
- **Model v4**: Latest generation Mendi hardware
- **Revision r2.2a-ub1**: Specific hardware revision with ultra-low power optimizations
- **Form Factor**: Headband design for comfortable forehead placement

### Regulatory Compliance
- **FCC Certification**: RYYEYSHJN
  - This indicates the device has been tested and complies with FCC regulations for electromagnetic interference
  - Safe for consumer use in the United States

## BLE Discovery Information

When scanning for the device:
- **Device Name**: Likely "Mendi" or similar
- **MAC Address**: `C3:DF:6C:5E:82:9E`
- **Manufacturer Data**: May contain device-specific information

## Notes for Development

1. **MAC Address Usage**: The MAC address `C3:DF:6C:5E:82:9E` can be used for direct connection during development, bypassing the need for discovery.

2. **Firmware Version 1.0.4**: This firmware version will determine the BLE protocol and packet structure we need to implement.

3. **Single Channel**: Unlike multi-channel fNIRS devices, we'll only receive data from one measurement location, simplifying the data parsing.

4. **FCC Compliance**: The FCC ID can be looked up in the FCC database for additional technical details about radio frequency emissions and specifications.

## Connection Parameters (To Be Discovered)

The following parameters need to be discovered through BLE exploration:
- Service UUIDs
- Characteristic UUIDs
- Notification/Indication setup
- Connection interval preferences
- MTU size
- Data packet format
- Sampling rate

## Next Steps

1. Use this MAC address for direct BLE connection attempts
2. Document all discovered services and characteristics
3. Capture raw data packets for protocol analysis
4. Verify data format matches firmware version 1.0.4 specifications