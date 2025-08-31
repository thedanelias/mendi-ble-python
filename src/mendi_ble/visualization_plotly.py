"""Real-time visualization for Mendi fNIRS data using Plotly."""

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output, State
import threading
import queue

from .models import MendiSample, Session
from .scoring import AdvancedScoringEngine, ScoringWeights


@dataclass
class PlotlyVisualizationConfig:
    """Configuration for the Plotly visualizer."""
    window_seconds: int = 30  # Rolling window duration
    update_interval: int = 500  # Update rate in ms (reduced from 100)
    port: int = 8050  # Dash server port
    zones: Dict[str, Tuple[float, float, str]] = None
    
    def __post_init__(self):
        if self.zones is None:
            self.zones = {
                'baseline': (0, 20, 'rgba(52, 152, 219, 0.3)'),     # Blue
                'active': (20, 50, 'rgba(241, 196, 15, 0.3)'),     # Yellow
                'high': (50, 80, 'rgba(230, 126, 34, 0.3)'),       # Orange
                'peak': (80, 100, 'rgba(231, 76, 60, 0.3)')        # Red
            }


class MendiPlotlyVisualizer:
    """Real-time visualization using Plotly and Dash."""
    
    def __init__(self, config: Optional[PlotlyVisualizationConfig] = None,
                 scoring_engine: Optional[AdvancedScoringEngine] = None):
        self.config = config or PlotlyVisualizationConfig()
        self.scoring_engine = scoring_engine or AdvancedScoringEngine()
        
        # Data buffers
        self.max_points = int(self.config.window_seconds * 20)  # ~20Hz
        self.time_buffer = deque(maxlen=self.max_points)
        self.activity_buffer = deque(maxlen=self.max_points)
        self.hbo_buffer = deque(maxlen=self.max_points)
        self.hbr_buffer = deque(maxlen=self.max_points)
        
        # Session tracking
        self.session_start = None
        self.baseline_sample = None
        self.current_zone = 'baseline'
        self.zone_times = {zone: 0 for zone in self.config.zones}
        self.last_update = None
        
        # All samples for scoring
        self.all_samples = []
        
        # Metrics
        self.points = 0
        self.control_seconds = 0
        self.control_start = None
        self.max_activity = 0
        
        # Thread-safe queue for updates with larger buffer
        self.update_queue = queue.Queue(maxsize=100)
        
        # Dash app
        self.app = None
        self.server_thread = None
        
    def create_dash_app(self):
        """Create the Dash application."""
        self.app = dash.Dash(__name__)
        
        # Define layout
        self.app.layout = html.Div([
            html.H1('Mendi Real-Time Visualization', 
                   style={'textAlign': 'center', 'color': '#2c3e50'}),
            
            # Control panel
            html.Div([
                html.Div([
                    html.H3('Scoring Controls', style={'display': 'inline-block', 'color': '#34495e', 'marginRight': '20px'}),
                    # Preset selector inline with title
                    html.Label('Preset: ', style={'marginRight': '10px'}),
                    dcc.Dropdown(
                        id='preset-dropdown',
                        options=[
                            {'label': 'Default', 'value': 'default'},
                            {'label': 'App-like', 'value': 'app_like'},
                            {'label': 'Beginner', 'value': 'beginner'},
                            {'label': 'Advanced', 'value': 'advanced'}
                        ],
                        value='app_like',
                        style={'width': '150px', 'display': 'inline-block', 'verticalAlign': 'middle'}
                    )
                ], style={'marginBottom': '15px'}),
                
                # Weight sliders in grid layout
                html.Div([
                    # Row 1: Base multiplier, Control threshold, Control bonus
                    html.Div([
                        html.Div([
                            html.Label('Base Multiplier', style={'fontSize': '12px', 'marginBottom': '5px'}),
                            dcc.Slider(id='base-multiplier', min=0.1, max=5.0, step=0.1, value=1.0,
                                     marks={0: '0', 2.5: '2.5', 5: '5'},
                                     tooltip={'placement': 'bottom', 'always_visible': True}),
                        ], style={'width': '30%', 'display': 'inline-block', 'marginRight': '3%'}),
                        
                        html.Div([
                            html.Label('Control Threshold %', style={'fontSize': '12px', 'marginBottom': '5px'}),
                            dcc.Slider(id='control-threshold', min=10, max=50, step=5, value=20,
                                     marks={10: '10', 30: '30', 50: '50'},
                                     tooltip={'placement': 'bottom', 'always_visible': True}),
                        ], style={'width': '30%', 'display': 'inline-block', 'marginRight': '3%'}),
                        
                        html.Div([
                            html.Label('Control Bonus', style={'fontSize': '12px', 'marginBottom': '5px'}),
                            dcc.Slider(id='control-bonus', min=0.1, max=5.0, step=0.1, value=1.0,
                                     marks={0: '0', 2.5: '2.5', 5: '5'},
                                     tooltip={'placement': 'bottom', 'always_visible': True}),
                        ], style={'width': '30%', 'display': 'inline-block'}),
                    ], style={'marginBottom': '20px'}),
                    
                    # Zone multipliers header
                    html.H4('Zone Multipliers', style={'fontSize': '14px', 'marginBottom': '10px'}),
                    
                    # Row 2: Zone multipliers
                    html.Div([
                        html.Div([
                            html.Label('Baseline', style={'fontSize': '12px', 'marginBottom': '5px'}),
                            dcc.Slider(id='zone-baseline', min=0.01, max=2.0, step=0.01, value=0.05,
                                     marks={0: '0', 1: '1', 2: '2'},
                                     tooltip={'placement': 'bottom', 'always_visible': True}),
                        ], style={'width': '23%', 'display': 'inline-block', 'marginRight': '2%'}),
                        
                        html.Div([
                            html.Label('Active', style={'fontSize': '12px', 'marginBottom': '5px'}),
                            dcc.Slider(id='zone-active', min=0.1, max=5.0, step=0.1, value=0.5,
                                     marks={0: '0', 2.5: '2.5', 5: '5'},
                                     tooltip={'placement': 'bottom', 'always_visible': True}),
                        ], style={'width': '23%', 'display': 'inline-block', 'marginRight': '2%'}),
                        
                        html.Div([
                            html.Label('High', style={'fontSize': '12px', 'marginBottom': '5px'}),
                            dcc.Slider(id='zone-high', min=0.5, max=10.0, step=0.5, value=1.5,
                                     marks={0: '0', 5: '5', 10: '10'},
                                     tooltip={'placement': 'bottom', 'always_visible': True}),
                        ], style={'width': '23%', 'display': 'inline-block', 'marginRight': '2%'}),
                        
                        html.Div([
                            html.Label('Peak', style={'fontSize': '12px', 'marginBottom': '5px'}),
                            dcc.Slider(id='zone-peak', min=1.0, max=20.0, step=1.0, value=3.0,
                                     marks={0: '0', 10: '10', 20: '20'},
                                     tooltip={'placement': 'bottom', 'always_visible': True}),
                        ], style={'width': '23%', 'display': 'inline-block'}),
                    ]),
                ])
            ], style={
                'backgroundColor': '#ecf0f1',
                'padding': '15px',
                'borderRadius': '10px',
                'margin': '10px',
                'marginBottom': '20px'
            }),
            
            # Main graph
            dcc.Graph(id='live-graph', style={'height': '60vh'}),
            
            # Metrics panel
            html.Div([
                html.Div([
                    html.H3('Session Metrics', style={'color': '#34495e'}),
                    html.Div(id='metrics-display', style={
                        'fontSize': '18px',
                        'lineHeight': '1.8',
                        'fontFamily': 'monospace'
                    })
                ], style={
                    'width': '30%',
                    'display': 'inline-block',
                    'verticalAlign': 'top',
                    'padding': '20px',
                    'backgroundColor': '#ecf0f1',
                    'borderRadius': '10px',
                    'margin': '10px'
                }),
                
                html.Div([
                    html.H3('Zone Distribution', style={'color': '#34495e'}),
                    dcc.Graph(id='zone-pie', style={'height': '300px'})
                ], style={
                    'width': '30%',
                    'display': 'inline-block',
                    'verticalAlign': 'top',
                    'padding': '20px',
                    'backgroundColor': '#ecf0f1',
                    'borderRadius': '10px',
                    'margin': '10px'
                }),
                
                html.Div([
                    html.H3('Activity Histogram', style={'color': '#34495e'}),
                    dcc.Graph(id='activity-hist', style={'height': '300px'})
                ], style={
                    'width': '30%',
                    'display': 'inline-block',
                    'verticalAlign': 'top',
                    'padding': '20px',
                    'backgroundColor': '#ecf0f1',
                    'borderRadius': '10px',
                    'margin': '10px'
                })
            ], style={'textAlign': 'center'}),
            
            # Interval component for updates
            dcc.Interval(
                id='graph-update',
                interval=self.config.update_interval
            ),
            
            # Store for data
            dcc.Store(id='data-store', data={
                'time': [],
                'activity': [],
                'hbo': [],
                'hbr': [],
                'points': 0,
                'max_activity': 0,
                'control_seconds': 0,
                'zone_times': self.zone_times,
                'duration': 0
            }),
            
            # Store for weights update trigger
            dcc.Store(id='weights-updated', data=False)
        ])
        
        # Define callbacks
        
        # Callback for preset dropdown
        @self.app.callback(
            [Output('base-multiplier', 'value'),
             Output('control-threshold', 'value'),
             Output('control-bonus', 'value'),
             Output('zone-baseline', 'value'),
             Output('zone-active', 'value'),
             Output('zone-high', 'value'),
             Output('zone-peak', 'value')],
            [Input('preset-dropdown', 'value')]
        )
        def update_sliders_from_preset(preset_name):
            weights = self.scoring_engine.get_preset_weights(preset_name)
            return (
                weights.base_multiplier,
                weights.control_threshold,
                weights.control_bonus,
                weights.zone_multipliers.get('baseline', 0.1),
                weights.zone_multipliers.get('active', 1.0),
                weights.zone_multipliers.get('high', 2.0),
                weights.zone_multipliers.get('peak', 4.0)
            )
        
        # Callback for weight changes
        @self.app.callback(
            Output('weights-updated', 'data'),
            [Input('base-multiplier', 'value'),
             Input('control-threshold', 'value'),
             Input('control-bonus', 'value'),
             Input('zone-baseline', 'value'),
             Input('zone-active', 'value'),
             Input('zone-high', 'value'),
             Input('zone-peak', 'value')]
        )
        def update_weights(base_mult, control_thresh, control_bonus,
                         zone_baseline, zone_active, zone_high, zone_peak):
            # Update scoring engine weights
            self.scoring_engine.weights.base_multiplier = base_mult
            self.scoring_engine.weights.control_threshold = control_thresh
            self.scoring_engine.weights.control_bonus = control_bonus
            self.scoring_engine.weights.zone_multipliers = {
                'baseline': zone_baseline,
                'active': zone_active,
                'high': zone_high,
                'peak': zone_peak
            }
            return True
        
        @self.app.callback(
            [Output('data-store', 'data'),
             Output('live-graph', 'figure'),
             Output('metrics-display', 'children'),
             Output('zone-pie', 'figure'),
             Output('activity-hist', 'figure')],
            [Input('graph-update', 'n_intervals')],
            [State('data-store', 'data')]
        )
        def update_graphs(n, stored_data):
            # Get latest data from queue (only get one update per interval)
            latest_data = None
            try:
                # Use get with timeout to avoid blocking
                latest_data = self.update_queue.get(timeout=0.01)
            except queue.Empty:
                pass
                    
            if latest_data:
                stored_data = latest_data
                
            # Create main figure with subplots
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=('Neural Activity (%)', 'Hemoglobin Signals'),
                row_heights=[0.6, 0.4],
                vertical_spacing=0.15
            )
            
            # Add zone backgrounds to activity plot
            for zone_name, (min_val, max_val, color) in self.config.zones.items():
                fig.add_hrect(
                    y0=min_val, y1=max_val,
                    fillcolor=color, layer="below",
                    line_width=0, row=1, col=1
                )
                
            # Activity trace
            if stored_data['time'] and stored_data['activity']:
                fig.add_trace(
                    go.Scatter(
                        x=stored_data['time'],
                        y=stored_data['activity'],
                        mode='lines',
                        name='Activity',
                        line=dict(color='white', width=3)
                    ),
                    row=1, col=1
                )
                
            # HbO and HbR traces
            if stored_data['time']:
                fig.add_trace(
                    go.Scatter(
                        x=stored_data['time'],
                        y=stored_data['hbo'],
                        mode='lines',
                        name='HbO',
                        line=dict(color='red', width=2)
                    ),
                    row=2, col=1
                )
                
                fig.add_trace(
                    go.Scatter(
                        x=stored_data['time'],
                        y=stored_data['hbr'],
                        mode='lines',
                        name='HbR',
                        line=dict(color='blue', width=2)
                    ),
                    row=2, col=1
                )
                
            # Update layout
            fig.update_xaxes(title_text="Time (s)", row=2, col=1)
            fig.update_yaxes(title_text="Activity %", range=[-10, 110], row=1, col=1)
            fig.update_yaxes(title_text="Hemoglobin", row=2, col=1)
            
            fig.update_layout(
                height=600,
                template='plotly_dark',
                showlegend=True,
                legend=dict(x=0.02, y=0.98)
            )
            
            # Metrics display
            metrics_html = html.Div([
                html.P(f"Duration: {stored_data['duration']:.1f}s"),
                html.P(f"Points: {stored_data['points']}",
                      style={'fontSize': '24px', 'fontWeight': 'bold', 'color': '#e74c3c'}),
                html.P(f"Max Activity: {stored_data['max_activity']:.1f}%"),
                html.P(f"Control Time: {stored_data['control_seconds']:.1f}s"),
            ])
            
            # Zone pie chart
            zone_values = list(stored_data['zone_times'].values())
            zone_labels = [z.title() for z in stored_data['zone_times'].keys()]
            zone_colors = [self.config.zones[z][2] for z in stored_data['zone_times'].keys()]
            
            pie_fig = go.Figure(data=[go.Pie(
                labels=zone_labels,
                values=zone_values,
                marker=dict(colors=zone_colors),
                hole=0.3
            )])
            pie_fig.update_layout(
                template='plotly_dark',
                showlegend=True,
                margin=dict(t=20, b=20)
            )
            
            # Activity histogram
            if stored_data['activity']:
                hist_fig = go.Figure(data=[go.Histogram(
                    x=stored_data['activity'],
                    nbinsx=20,
                    marker_color='lightblue'
                )])
                hist_fig.update_layout(
                    template='plotly_dark',
                    xaxis_title="Activity %",
                    yaxis_title="Count",
                    margin=dict(t=20, b=40)
                )
            else:
                hist_fig = go.Figure()
                
            return stored_data, fig, metrics_html, pie_fig, hist_fig
            
    def calculate_activity_percentage(self, sample: MendiSample) -> float:
        """Calculate neural activity as percentage above baseline."""
        if self.baseline_sample is None:
            return 0
        return self.scoring_engine.calculate_activity_percentage(sample, self.baseline_sample)
        
    def get_current_zone(self, activity_pct: float) -> str:
        """Determine which zone the current activity falls into."""
        return self.scoring_engine.get_zone(activity_pct)
        
    def update_metrics(self, sample: MendiSample, activity_pct: float):
        """Update running metrics."""
        now = datetime.now()
        
        # Track zone times
        if self.last_update:
            dt = (now - self.last_update).total_seconds()
            self.zone_times[self.current_zone] += dt
            
        # Track control
        if activity_pct >= self.scoring_engine.weights.control_threshold:
            if self.control_start is None:
                self.control_start = now
        else:
            if self.control_start:
                self.control_seconds += (now - self.control_start).total_seconds()
                self.control_start = None
                
        # Update max activity
        self.max_activity = max(self.max_activity, activity_pct)
        
        # Update points using scoring engine
        if self.baseline_sample:
            self.points = self.scoring_engine.calculate_live_points(
                self.all_samples, self.baseline_sample, sample_rate=20.0
            )
            
        self.last_update = now
        
    def update(self, sample: MendiSample):
        """Update visualization with new sample."""
        if self.session_start is None:
            self.session_start = datetime.now()
            self.baseline_sample = sample
            
        # Calculate metrics
        elapsed = (datetime.now() - self.session_start).total_seconds()
        activity_pct = self.calculate_activity_percentage(sample)
        self.current_zone = self.get_current_zone(activity_pct)
        
        # Update buffers
        self.time_buffer.append(elapsed)
        self.activity_buffer.append(activity_pct)
        self.hbo_buffer.append(sample.hbo)
        self.hbr_buffer.append(sample.hbr)
        
        # Update metrics
        self.update_metrics(sample, activity_pct)
        
        # Store sample for scoring
        self.all_samples.append(sample)
        
        # Push update to queue (non-blocking)
        update_data = {
            'time': list(self.time_buffer),
            'activity': list(self.activity_buffer),
            'hbo': list(self.hbo_buffer),
            'hbr': list(self.hbr_buffer),
            'points': self.points,
            'max_activity': self.max_activity,
            'control_seconds': self.control_seconds,
            'zone_times': self.zone_times.copy(),
            'duration': elapsed
        }
        
        try:
            # Use put_nowait to avoid blocking if queue is full
            self.update_queue.put_nowait(update_data)
        except queue.Full:
            # If queue is full, remove oldest and add new
            try:
                self.update_queue.get_nowait()
                self.update_queue.put_nowait(update_data)
            except:
                pass
        
    def start(self):
        """Start the visualization server."""
        self.create_dash_app()
        
        def run_server():
            self.app.run(
                debug=False,
                port=self.config.port,
                host='127.0.0.1',
                use_reloader=False
            )
            
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        print(f"\n📊 Visualization server started at http://localhost:{self.config.port}")
        print("Open this URL in your browser to see the real-time visualization\n")
        
    def stop(self):
        """Stop the visualization server."""
        # Dash doesn't have a clean shutdown method, thread will stop when program exits
        pass
        
    def get_session_summary(self) -> Dict:
        """Get summary statistics for the session."""
        if not self.session_start:
            return {}
            
        duration = (datetime.now() - self.session_start).total_seconds()
        
        return {
            'duration': duration,
            'points': int(self.points),
            'max_activity': self.max_activity,
            'control_seconds': self.control_seconds,
            'zone_distribution': {
                zone: (time / duration * 100) if duration > 0 else 0
                for zone, time in self.zone_times.items()
            },
            'samples_collected': len(self.all_samples)
        }