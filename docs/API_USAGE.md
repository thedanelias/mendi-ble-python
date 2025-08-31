# Mendi BLE Python API Usage Guide

This guide clarifies common API usage patterns for the mendi-ble-python library.

## Accessing Baseline Data

The baseline is not directly available on the MendiStream object, but through its session:

```python
async with MendiStream() as stream:
    # Access baseline through session
    baseline = stream.session.baseline
    
    # Note: baseline is None until calibration completes
    # (typically after first 5 samples)
    async for sample in stream:
        if stream.session.baseline:
            print(f"Baseline HbO: {stream.session.baseline.hbo}")
```

## Device Discovery

Use `MendiScanner` to find devices:

```python
from mendi_ble import MendiScanner

scanner = MendiScanner()

# Find any Mendi device
device = await scanner.find_device()

# Find specific device by address
device = await scanner.find_device(address="C3:DF:6C:5E:82:9E")

# Scan for all Mendi devices (returns list)
devices = await scanner.scan_all()  # Note: scan_all(), not scan()
```

## Advanced Scoring Engine

The `AdvancedScoringEngine` provides activity calculations:

```python
from mendi_ble import AdvancedScoringEngine, ScoringWeights

# Create engine with preset
engine = AdvancedScoringEngine()
weights = engine.get_preset_weights('app_like')
engine.weights = weights

# Calculate activity percentage
if stream.session.baseline:
    activity_pct = engine.calculate_activity_percentage(
        sample, 
        stream.session.baseline
    )
    zone = engine.get_zone(activity_pct)
```

## Complete Integration Example

```python
import asyncio
from mendi_ble import MendiStream, AdvancedScoringEngine

async def stream_with_scoring():
    # Setup scoring
    scoring_engine = AdvancedScoringEngine()
    weights = scoring_engine.get_preset_weights('app_like')
    scoring_engine.weights = weights
    
    # Stream data
    async with MendiStream() as stream:
        async for sample in stream:
            # Access baseline through session
            if stream.session.baseline:
                activity_pct = scoring_engine.calculate_activity_percentage(
                    sample, 
                    stream.session.baseline
                )
                zone = scoring_engine.get_zone(activity_pct)
                
                print(f"HbO: {sample.hbo:.2f}, Activity: {activity_pct:.1f}%, Zone: {zone}")

asyncio.run(stream_with_scoring())
```

## Common Patterns

### Pattern 1: Wait for Baseline Calibration
```python
async with MendiStream() as stream:
    print("Calibrating baseline...")
    
    async for sample in stream:
        if stream.session.baseline:
            print("Baseline established!")
            break
    
    # Now continue with calibrated streaming
    async for sample in stream:
        # Process calibrated samples
        pass
```

### Pattern 2: Session Management
```python
# Access session data
async with MendiStream() as stream:
    # Session is automatically created
    print(f"Session started at: {stream.session.start_time}")
    
    async for sample in stream:
        # Samples are automatically added to session
        pass
    
    # Session ends automatically
    print(f"Total points: {stream.session.points}")
```

### Pattern 3: Error Handling
```python
try:
    async with MendiStream() as stream:
        async for sample in stream:
            process_sample(sample)
except Exception as e:
    print(f"Streaming error: {e}")
```

## API Reference Summary

- **MendiStream**: Main streaming interface
  - `stream.session`: Access to session data
  - `stream.session.baseline`: Baseline sample (after calibration)
  - `stream.session.samples`: All collected samples
  - `stream.session.points`: Calculated session points

- **MendiScanner**: Device discovery
  - `scan_all()`: Find all Mendi devices
  - `find_device()`: Find first/specific device

- **AdvancedScoringEngine**: Activity calculations  
  - `calculate_activity_percentage()`: Get activity % above baseline
  - `get_zone()`: Get activity zone name
  - `get_preset_weights()`: Get scoring presets