#!/usr/bin/env python3
"""
Example: Real-time visualization using Plotly (browser-based).

This example demonstrates:
1. Browser-based real-time visualization
2. Interactive graphs that update smoothly
3. Multiple visualization panels
4. No matplotlib display issues
"""

import asyncio
import sys
from pathlib import Path
import argparse
from datetime import datetime
import webbrowser
import time

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mendi_ble import MendiScanner, MendiClient
from mendi_ble.visualization_plotly import MendiPlotlyVisualizer, PlotlyVisualizationConfig
from mendi_ble.scoring import AdvancedScoringEngine, ScoringWeights
from mendi_ble.models import MendiSample


async def run_plotly_visualization(duration: int = 180, preset: str = 'app_like'):
    """Run browser-based visualization session."""
    print("🧠 Mendi Plotly Visualization (Browser-based)")
    print("=" * 40)
    
    # Find device
    scanner = MendiScanner()
    print("Searching for Mendi device...")
    device = await scanner.find_device()
    
    if not device:
        print("❌ No Mendi device found!")
        print("\nRunning with simulated data instead...")
        await test_with_simulated_data(duration, preset)
        return
        
    print(f"✅ Found device: {device.name} ({device.address})")
    
    # Setup visualization
    print("\nSetting up visualization...")
    
    # Choose scoring preset
    scoring_engine = AdvancedScoringEngine()
    weights = scoring_engine.get_preset_weights(preset)
    scoring_engine.weights = weights
    
    print(f"Using scoring preset: {preset}")
    print(f"- Base multiplier: {weights.base_multiplier}")
    print(f"- Control threshold: {weights.control_threshold}%")
    
    # Create visualizer with Plotly
    config = PlotlyVisualizationConfig(window_seconds=30, update_interval=500)
    visualizer = MendiPlotlyVisualizer(config=config, scoring_engine=scoring_engine)
    
    # Start visualization server
    visualizer.start()
    
    # Open browser after a short delay
    time.sleep(2)
    webbrowser.open(f'http://localhost:{config.port}')
    
    # Connect to device
    async with MendiClient(device) as client:
        print("\n📡 Connected to device")
        print(f"Duration: {duration} seconds")
        print("\nInstructions:")
        print("- View the visualization in your browser")
        print("- Try to maintain focus to increase neural activity")
        print("- Watch the activity climb into higher zones")
        print("- Press Ctrl+C to stop early\n")
        
        # Notification handler
        def handle_notification(sender, data):
            try:
                # Parse the 9-byte packet format: 0a 03 08 XX 1d 10 01 18 01
                if len(data) == 9 and data[0:3] == b'\x0a\x03\x08':
                    # Extract sensor value from byte 3
                    sensor_value = data[3]
                    
                    # Convert to HbO/HbR approximation (this is simplified)
                    # The actual conversion would need calibration data
                    # For now, treat lower values as higher oxygenation
                    baseline = 195  # Approximate baseline
                    delta = baseline - sensor_value
                    
                    # Create sample with approximated values
                    sample = MendiSample(
                        timestamp=datetime.now(),
                        hbo=100 + delta * 2,  # Simplified conversion
                        hbr=50 - delta * 0.5,  # Inverse relationship
                        quality=1.0,
                        raw_value=sensor_value
                    )
                    
                    # Update visualization
                    visualizer.update(sample)
                    
                    # Log for debugging
                    if visualizer.all_samples and len(visualizer.all_samples) % 10 == 0:
                        print(f"Raw: {sensor_value}, HbO: {sample.hbo:.1f}, HbR: {sample.hbr:.1f}")
                    
            except Exception as e:
                print(f"Error processing sample: {e}")
        
        # Enable notifications on data characteristic
        await client.client.start_notify(client.CHAR_DATA, handle_notification)
        
        # Start data streaming loop using descriptor writes
        streaming = True
        async def trigger_data():
            while streaming:
                try:
                    await client.client.write_gatt_descriptor(client.CCCD_HANDLE, b'\x01\x00')
                    await asyncio.sleep(2.0)
                except Exception as e:
                    print(f"Error triggering data: {e}")
                    
        trigger_task = asyncio.create_task(trigger_data())
        
        # Run for specified duration
        try:
            await asyncio.sleep(duration)
        except KeyboardInterrupt:
            print("\n\n⏹️  Session stopped by user")
        
        # Stop streaming
        streaming = False
        try:
            await asyncio.wait_for(trigger_task, timeout=1.0)
        except asyncio.TimeoutError:
            trigger_task.cancel()
        except asyncio.CancelledError:
            pass
        
        # Stop notifications
        try:
            await client.client.stop_notify(client.CHAR_DATA)
        except Exception as e:
            print(f"Error stopping notifications: {e}")
        
    # Get session summary
    summary = visualizer.get_session_summary()
    
    print("\n" + "=" * 40)
    print("📈 Session Summary")
    print("=" * 40)
    print(f"Duration: {summary['duration']:.1f} seconds")
    print(f"Points: {summary['points']}")
    print(f"Max Activity: {summary['max_activity']:.1f}%")
    print(f"Control Time: {summary['control_seconds']:.1f} seconds")
    print(f"\nZone Distribution:")
    for zone, pct in summary['zone_distribution'].items():
        print(f"  {zone.title()}: {pct:.0f}%")
    print(f"\nSamples collected: {summary['samples_collected']}")
    
    print("\nThe visualization will remain open in your browser.")
    print("Press Enter to exit...")
    input()
    visualizer.stop()


async def test_with_simulated_data(duration: int = 60, preset: str = 'app_like'):
    """Test Plotly visualization with simulated data."""
    import random
    import math
    
    print("🧠 Plotly Visualization Test (Simulated Data)")
    print("=" * 40)
    
    # Setup
    scoring_engine = AdvancedScoringEngine()
    weights = scoring_engine.get_preset_weights(preset)
    scoring_engine.weights = weights
    
    print(f"Using scoring preset: {preset}")
    
    config = PlotlyVisualizationConfig(window_seconds=30, update_interval=500)
    visualizer = MendiPlotlyVisualizer(config=config, scoring_engine=scoring_engine)
    
    # Start server
    visualizer.start()
    
    # Open browser
    time.sleep(2)
    webbrowser.open(f'http://localhost:{config.port}')
    
    print("\n📊 Generating simulated data...")
    print("Check your browser for the visualization!")
    
    # Simulate data
    baseline_hbo = 100.0
    baseline_hbr = 50.0
    
    try:
        for i in range(duration * 20):  # 20Hz
            # Create realistic patterns
            t = i / 20.0
            
            # Base oscillation
            wave = math.sin(t * 0.1) * 10
            
            # Activity bursts
            if 10 < t < 20 or 35 < t < 50:
                activity = 30 + random.gauss(0, 5)
            elif 20 < t < 30:
                activity = 60 + random.gauss(0, 8)  
            else:
                activity = 5 + random.gauss(0, 3)
                
            # Calculate values
            hbo = baseline_hbo * (1 + (wave + activity) / 100)
            hbr = baseline_hbr * (1 - (wave + activity) / 200)
            
            sample = MendiSample(
                timestamp=datetime.now(),
                hbo=hbo,
                hbr=hbr,
                quality=1.0
            )
            
            visualizer.update(sample)
            await asyncio.sleep(0.05)  # 20Hz
    except KeyboardInterrupt:
        print("\n\n⏹️  Session stopped by user")
        
    # Summary
    summary = visualizer.get_session_summary()
    print(f"\n✅ Session complete!")
    print(f"Points: {summary['points']}")
    print(f"Max Activity: {summary['max_activity']:.1f}%")
    
    print("\nThe visualization remains open in your browser.")
    print("Press Enter to close...")
    input()
    visualizer.stop()


def main():
    parser = argparse.ArgumentParser(description="Plotly-based Mendi visualization")
    parser.add_argument('--duration', type=int, default=180,
                       help='Session duration in seconds (default: 180)')
    parser.add_argument('--preset', choices=['default', 'app_like', 'beginner', 'advanced'],
                       default='app_like', help='Scoring preset to use')
    parser.add_argument('--simulate', action='store_true',
                       help='Use simulated data for testing')
    
    args = parser.parse_args()
    
    try:
        if args.simulate:
            asyncio.run(test_with_simulated_data(args.duration, args.preset))
        else:
            asyncio.run(run_plotly_visualization(args.duration, args.preset))
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()