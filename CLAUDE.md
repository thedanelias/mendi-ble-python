# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python library for interfacing with Mendi fNIRS devices via Bluetooth Low Energy. Successfully reverse-engineered the proprietary BLE protocol to enable direct device communication.

**Repository**: https://github.com/BioMycoBit/mendi-ble-python  
**Author**: Brandon Taylor

## Key Technical Details

### BLE Protocol (Discovered through reverse engineering)
- **Service UUID**: `fc3eabb0-c6c4-49e6-922a-6e551c455af5`
- **Data Characteristic**: `fc3eabb5-c6c4-49e6-922a-6e551c455af5`
- **Streaming Method**: Request-response via descriptor writes (not standard BLE streaming)
- **Packet Format**: 9 bytes, protobuf-like encoding
- **Optimal Timing**: 2-second intervals between descriptor writes

### Data Packet Structure
```
Position: 0  1  2  3  4  5  6  7  8
Value:    0a 03 08 XX 1d 10 01 18 01
                   ^^
                   Sensor value (varies with brain activity)
```

## Development Guidelines

### Code Style
- Use type hints for all functions
- Follow PEP 8 conventions
- Max line length: 88 (black default)
- Use dataclasses for data models
- NO COMMENTS unless specifically requested

### Testing Requirements
- Run tests before committing: `pytest tests/ -v`
- Format code: `black src/ tests/ examples/`
- Type check: `mypy src/`

### Platform Considerations
- **Windows**: Full BLE functionality, all testing happens here
- **WSL**: Development only (no Bluetooth access)
- **macOS/Linux**: Should work but primary testing is Windows

## Project Structure

```
mendi-ble-python/
├── src/mendi_ble/           # Library source code
│   ├── __init__.py          # Public API exports
│   ├── client.py            # Low-level BLE client
│   ├── stream.py            # High-level streaming API
│   ├── scanner.py           # Device discovery
│   ├── parser.py            # Packet parsing
│   ├── models.py            # Data models
│   ├── scoring.py           # Activity scoring engine
│   └── visualization_plotly.py  # Browser-based visualization
├── examples/                # Usage examples
│   └── visualization_example.py
├── tests/                   # Test suite
├── docs/                    # Documentation
│   ├── REVERSE_ENGINEERING_OVERVIEW.md
│   ├── DEVICE_PROFILE.md
│   ├── BLE_DEVICE_CRASH_RECOVERY.md
│   └── API_USAGE.md
└── requirements.txt         # Dependencies
```

## Current Implementation Status

✅ **Completed**:
- BLE protocol reverse engineering
- Device discovery and connection
- Real-time data streaming
- Packet parsing (protobuf-like format)
- Browser-based visualization (Plotly)
- Reconnection handling
- Scoring engine with presets

## Common Tasks

### Adding New Features
1. Create feature branch
2. Implement in appropriate module
3. Add tests
4. Update documentation
5. Test with real device (Windows only)

### Debugging BLE Issues
- Device must be on (blue LED)
- Windows Bluetooth must be enabled
- May need to pair device first via Windows settings
- Check Device Manager for adapter status

### Running Examples
```bash
# Windows PowerShell
cd C:\repos\mendi-ble-python
.\venv\Scripts\activate
python examples\visualization_example.py

# With simulated data (no device needed)
python examples\visualization_example.py --simulate
```

## Important Notes

1. **No Button Required**: Device starts streaming automatically after BLE initialization
2. **Descriptor Writes**: Data packets triggered by writing `b'\x01\x00'` to CCCD handle 29
3. **Reconnection**: Device may maintain phantom connection, requiring special handling
4. **Cross-Platform**: Primary development/testing on Windows due to BLE requirements

## Troubleshooting

### Device Not Found
- Ensure device is on (blue LED)
- Check Windows Bluetooth settings
- Try closer proximity to adapter
- Device MAC: `C3:DF:6C:5E:82:9E` (primary device)

### No Data Streaming
- Verify descriptor write implementation
- Check 2-second timing between writes
- Ensure notifications enabled on fc3eabb5

### Import Errors
- Install in development mode: `pip install -e .`
- Check virtual environment is activated
- Verify all dependencies installed

## Contributing Guidelines

1. **Test with Real Device**: All changes must be tested with actual Mendi hardware
2. **Document Protocol Findings**: Any new protocol discoveries should be documented
3. **Maintain Compatibility**: Don't break existing API without version bump
4. **Cross-Platform**: Consider Windows/Mac/Linux compatibility

## License

MIT License - Copyright (c) 2025 Brandon Taylor

## Disclaimer

Unofficial library developed through reverse engineering. Not affiliated with Mendi.io.