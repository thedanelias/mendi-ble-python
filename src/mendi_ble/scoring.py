"""Advanced scoring engine for Mendi sessions."""

import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from pathlib import Path

from .models import MendiSample, Session


@dataclass
class ScoringWeights:
    """Configurable weights for the scoring algorithm."""
    # Base scoring
    base_multiplier: float = 1.0
    
    # Zone multipliers  
    zone_multipliers: Dict[str, float] = None
    
    # Control bonuses
    control_bonus: float = 0.5
    control_threshold: float = 20.0  # % above baseline
    
    # Progressive scaling
    progression_factor: float = 1.05
    time_exponent: float = 0.3
    
    # Sustained activity bonuses
    sustain_multipliers: Dict[int, float] = None  # seconds -> multiplier
    
    def __post_init__(self):
        if self.zone_multipliers is None:
            self.zone_multipliers = {
                'baseline': 0.1,
                'active': 1.0,
                'high': 2.0,
                'peak': 4.0
            }
            
        if self.sustain_multipliers is None:
            self.sustain_multipliers = {
                5: 1.2,    # 5+ seconds
                10: 1.5,   # 10+ seconds  
                20: 2.0,   # 20+ seconds
                30: 3.0    # 30+ seconds
            }
            
    def save(self, path: str):
        """Save weights to JSON file."""
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
            
    @classmethod
    def load(cls, path: str) -> 'ScoringWeights':
        """Load weights from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls(**data)


class AdvancedScoringEngine:
    """Sophisticated scoring system that approximates the Mendi app."""
    
    def __init__(self, weights: Optional[ScoringWeights] = None):
        self.weights = weights or ScoringWeights()
        self.zones = {
            'baseline': (0, 20),
            'active': (20, 50), 
            'high': (50, 80),
            'peak': (80, float('inf'))
        }
        
    def calculate_activity_percentage(self, sample: MendiSample, baseline: MendiSample) -> float:
        """Calculate neural activity as percentage above baseline."""
        if baseline.hbo == 0:
            return 0
            
        # Focus on HbO changes
        baseline_total = abs(baseline.hbo)
        current_total = abs(sample.hbo)
        
        if baseline_total > 0:
            pct_change = ((current_total - baseline_total) / baseline_total) * 100
            return max(0, pct_change)
        return 0
        
    def get_zone(self, activity_pct: float) -> str:
        """Determine activity zone."""
        for zone_name, (min_val, max_val) in self.zones.items():
            if min_val <= activity_pct < max_val:
                return zone_name
        return 'peak'
        
    def get_sustain_multiplier(self, sustain_seconds: float) -> float:
        """Get multiplier based on sustained duration."""
        multiplier = 1.0
        for threshold, mult in sorted(self.weights.sustain_multipliers.items()):
            if sustain_seconds >= threshold:
                multiplier = mult
        return multiplier
        
    def calculate_points(self, session: Session) -> int:
        """Calculate total points for a session."""
        points = 0.0
        control_start_idx = None
        consecutive_high = 0
        
        if not session.samples or not session.baseline:
            return 0
            
        total_samples = len(session.samples)
        
        for i, sample in enumerate(session.samples):
            # Calculate activity percentage
            activity_pct = self.calculate_activity_percentage(sample, session.baseline)
            
            # Determine zone
            zone = self.get_zone(activity_pct)
            
            # Base points (activity above baseline) - normalized per second
            # Divide by sample rate and further reduce to get reasonable points
            # Target: ~10-30 points per second in high activity
            base_points = (activity_pct * self.weights.base_multiplier) / (session.sample_rate * 10)
            
            # Apply zone multiplier
            zone_mult = self.weights.zone_multipliers.get(zone, 1.0)
            
            # Progressive scaling (points increase over time)
            time_factor = 1 + (i / total_samples) ** self.weights.time_exponent
            progress_mult = self.weights.progression_factor * time_factor
            
            # Calculate frame points
            frame_points = base_points * zone_mult * progress_mult
            
            # Control tracking (sustained activity above threshold)
            if activity_pct >= self.weights.control_threshold:
                if control_start_idx is None:
                    control_start_idx = i
                consecutive_high += 1
            else:
                if control_start_idx is not None:
                    # Award control bonus
                    control_duration = (i - control_start_idx) / session.sample_rate
                    sustain_mult = self.get_sustain_multiplier(control_duration)
                    control_points = control_duration * self.weights.control_bonus * sustain_mult
                    points += control_points
                    
                control_start_idx = None
                consecutive_high = 0
                
            # Apply sustained activity multiplier to current frame
            if consecutive_high > 0:
                sustain_seconds = consecutive_high / session.sample_rate
                sustain_mult = self.get_sustain_multiplier(sustain_seconds)
                frame_points *= sustain_mult
                
            points += frame_points
            
        # Final control bonus if session ends during sustained activity
        if control_start_idx is not None:
            control_duration = (len(session.samples) - control_start_idx) / session.sample_rate
            sustain_mult = self.get_sustain_multiplier(control_duration)
            control_points = control_duration * self.weights.control_bonus * sustain_mult
            points += control_points
            
        return int(points)
        
    def calculate_live_points(self, samples: List[MendiSample], baseline: MendiSample, 
                            sample_rate: float = 20.0) -> int:
        """Calculate points for a live stream of samples."""
        # Create temporary session
        session = Session(
            device_address="live",
            start_time=None,
            baseline=baseline,
            samples=samples,
            sample_rate=sample_rate
        )
        return self.calculate_points(session)
        
    def get_preset_weights(self, preset_name: str) -> ScoringWeights:
        """Get predefined weight presets."""
        presets = {
            'default': ScoringWeights(),
            
            'app_like': ScoringWeights(
                base_multiplier=1.0,
                zone_multipliers={
                    'baseline': 0.05,
                    'active': 0.5,
                    'high': 1.5, 
                    'peak': 3.0
                },
                control_bonus=1.0,
                progression_factor=1.05,
                time_exponent=0.3
            ),
            
            'beginner': ScoringWeights(
                base_multiplier=2.0,
                zone_multipliers={
                    'baseline': 1.0,
                    'active': 2.0,
                    'high': 4.0,
                    'peak': 6.0
                },
                control_bonus=5.0,
                control_threshold=15.0,
                progression_factor=1.05
            ),
            
            'advanced': ScoringWeights(
                base_multiplier=0.8,
                zone_multipliers={
                    'baseline': 0.1,
                    'active': 2.0,
                    'high': 10.0,
                    'peak': 20.0
                },
                control_bonus=30.0,
                control_threshold=25.0,
                progression_factor=1.3,
                sustain_multipliers={
                    5: 2.0,
                    10: 3.0,
                    20: 5.0,
                    30: 10.0
                }
            )
        }
        
        return presets.get(preset_name, presets['default'])
        
    def update_weights(self, new_weights: Dict):
        """Update specific weights while keeping others."""
        for key, value in new_weights.items():
            if hasattr(self.weights, key):
                setattr(self.weights, key, value)