# mendi-ble-python

Python library for interfacing with Mendi fNIRS devices via Bluetooth Low Energy (BLE).

## Overview

This library enables real-time streaming of brain oxygenation data (HbO/HbR) from Mendi's single-channel prefrontal cortex sensor. It was developed through systematic reverse engineering of the BLE protocol, discovering the device's unique request-response streaming mechanism.

## Features

- **Device Discovery**: Automatic detection of Mendi devices
- **Real-time Streaming**: ~20Hz data acquisition using the discovered protocol
- **Browser Visualization**: Interactive real-time graphs with Plotly
- **Robust Reconnection**: Handles disconnections and phantom connections
- **Scoring Engine**: Configurable activity scoring with multiple presets

## Installation

```bash
# From PyPI (when published)
pip install mendi-ble

# From GitHub
pip install git+https://github.com/BioMycoBit/mendi-ble-python.git

# For development
git clone https://github.com/BioMycoBit/mendi-ble-python.git
cd mendi-ble-python
pip install -e ".[dev]"
```

## Quick Start

### Basic Streaming

```python
import asyncio
from mendi_ble import MendiStream

async def main():
    async with MendiStream() as stream:
        async for sample in stream:
            print(f"HbO: {sample.hbo:.2f}, HbR: {sample.hbr:.2f}")

asyncio.run(main())
```

### Visualization Example

```bash
# With real device
python examples/visualization_example.py

# With simulated data
python examples/visualization_example.py --simulate
```

Opens browser visualization at http://localhost:8050

## How It Works

Through reverse engineering, we discovered that Mendi uses a unique BLE streaming pattern:

1. **Not Standard Streaming**: Unlike typical BLE devices, Mendi doesn't continuously stream data
2. **Request-Response**: Each data packet must be requested via descriptor write
3. **Optimal Timing**: 2-second intervals between requests provides stable data flow

See [docs/REVERSE_ENGINEERING_OVERVIEW.md](docs/REVERSE_ENGINEERING_OVERVIEW.md) for the full discovery journey.

## Protocol Details

### Service and Characteristics

```python
SERVICE_UUID = "fc3eabb0-c6c4-49e6-922a-6e551c455af5"
CHAR_DATA = "fc3eabb5-c6c4-49e6-922a-6e551c455af5"  # Data stream
```

### Data Packet Format

```
Position: 0  1  2  3  4  5  6  7  8
Value:    0a 03 08 XX 1d 10 01 18 01
                   ^^
                   Sensor value (varies with brain activity)
```

## API Reference

### Core Classes

- `MendiStream` - High-level streaming interface
- `MendiClient` - Low-level BLE client
- `MendiScanner` - Device discovery
- `MendiPlotlyVisualizer` - Real-time visualization

### Data Models

- `MendiSample` - Individual measurement (HbO, HbR, timestamp, quality)
- `Session` - Complete session with baseline and metrics

## Platform Support

- **Windows**: Full functionality
- **macOS**: Requires Bluetooth permissions
- **Linux**: May need capabilities (`sudo setcap`)
- **WSL**: No Bluetooth access (development only)

## Contributing

Contributions welcome! Areas of interest:
- Protocol documentation improvements
- Additional device support
- Performance optimizations
- Cross-platform testing

## Documentation

- [Reverse Engineering Overview](docs/REVERSE_ENGINEERING_OVERVIEW.md) - How we discovered the protocol
- [Device Profile](docs/DEVICE_PROFILE.md) - Hardware specifications
- [BLE Crash Recovery](docs/BLE_DEVICE_CRASH_RECOVERY.md) - Handling device crashes
- [API Usage](docs/API_USAGE.md) - Detailed API examples

## License

MIT License - See [LICENSE](LICENSE) file

## Disclaimer

This is an unofficial library developed through reverse engineering. Not affiliated with or endorsed by Mendi.io. Use at your own risk.

## Author

Brandon Taylor

## Acknowledgments

- Developed using the [Bleak](https://github.com/hbldh/bleak) BLE library
- Visualization powered by [Plotly Dash](https://plotly.com/dash/)