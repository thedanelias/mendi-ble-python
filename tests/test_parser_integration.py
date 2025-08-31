"""Integration tests for the Mendi parser with real packet formats."""

import pytest
from datetime import datetime
from mendi_ble.parser import MendiProtobufParser
from mendi_ble.models import MendiSample


class TestParserIntegration:
    """Test parser with real device packet formats."""
    
    def test_parse_fc3eabb5_valid_packet(self):
        """Test parsing valid FC3EABB5 packet."""
        parser = MendiProtobufParser()
        
        # Real packet format: 0a 03 08 XX 1d 10 01 18 01
        # Where XX is the sensor value (typically 187-199)
        test_packets = [
            b'\x0a\x03\x08\xc3\x1d\x10\x01\x18\x01',  # 195 (baseline)
            b'\x0a\x03\x08\xbb\x1d\x10\x01\x18\x01',  # 187 (high activity)
            b'\x0a\x03\x08\xc7\x1d\x10\x01\x18\x01',  # 199 (low activity)
        ]
        
        for packet in test_packets:
            sample = parser.parse_fc3eabb5(packet)
            
            # Verify sample was created
            assert sample is not None
            assert isinstance(sample, MendiSample)
            
            # Verify required fields
            assert isinstance(sample.timestamp, datetime)
            assert isinstance(sample.hbo, float)
            assert isinstance(sample.hbr, float)
            assert sample.quality == 1.0
            assert sample.characteristic == 'fc3eabb5'
            
            # Verify raw value was preserved
            assert sample.raw_value == packet[3]
            
            # Verify HbO/HbR are in reasonable ranges
            assert 80 <= sample.hbo <= 120  # Typical HbO range
            assert 40 <= sample.hbr <= 60   # Typical HbR range
    
    def test_parse_fc3eabb5_conversion_logic(self):
        """Test HbO/HbR conversion logic."""
        parser = MendiProtobufParser()
        
        # Test baseline value (195)
        baseline_packet = b'\x0a\x03\x08\xc3\x1d\x10\x01\x18\x01'
        baseline_sample = parser.parse_fc3eabb5(baseline_packet)
        assert baseline_sample.hbo == 100.0  # Baseline HbO
        assert baseline_sample.hbr == 50.0   # Baseline HbR
        
        # Test high activity (187)
        high_packet = b'\x0a\x03\x08\xbb\x1d\x10\x01\x18\x01'
        high_sample = parser.parse_fc3eabb5(high_packet)
        assert high_sample.hbo > baseline_sample.hbo  # Higher HbO
        assert high_sample.hbr < baseline_sample.hbr  # Lower HbR (inverse)
        
        # Test low activity (199)
        low_packet = b'\x0a\x03\x08\xc7\x1d\x10\x01\x18\x01'
        low_sample = parser.parse_fc3eabb5(low_packet)
        assert low_sample.hbo < baseline_sample.hbo  # Lower HbO
        assert low_sample.hbr > baseline_sample.hbr  # Higher HbR
    
    def test_parse_fc3eabb4_valid_packet(self):
        """Test parsing valid FC3EABB4 packet."""
        parser = MendiProtobufParser()
        
        # Real packet format: 08 XX 20
        test_packets = [
            b'\x08\xc3\x20',  # 195 (baseline)
            b'\x08\xbb\x20',  # 187 (high activity)
            b'\x08\xc7\x20',  # 199 (low activity)
        ]
        
        for packet in test_packets:
            sample = parser.parse_fc3eabb4(packet)
            
            # Verify sample was created
            assert sample is not None
            assert isinstance(sample, MendiSample)
            
            # Verify required fields
            assert isinstance(sample.timestamp, datetime)
            assert isinstance(sample.hbo, float)
            assert isinstance(sample.hbr, float)
            assert sample.quality == 1.0
            assert sample.characteristic == 'fc3eabb4'
            
            # Verify raw value was preserved
            assert sample.raw_value == packet[1]
    
    def test_parse_invalid_packets(self):
        """Test handling of invalid packets."""
        parser = MendiProtobufParser()
        
        # Invalid FC3EABB5 packets
        assert parser.parse_fc3eabb5(b'') is None  # Empty
        assert parser.parse_fc3eabb5(b'\x00' * 8) is None  # Wrong length
        assert parser.parse_fc3eabb5(b'\xff' * 9) is None  # Wrong header
        
        # Invalid FC3EABB4 packets
        assert parser.parse_fc3eabb4(b'') is None  # Empty
        assert parser.parse_fc3eabb4(b'\x00' * 2) is None  # Wrong length
        assert parser.parse_fc3eabb4(b'\xff\xc3\x20') is None  # Wrong header
        assert parser.parse_fc3eabb4(b'\x08\xc3\xff') is None  # Wrong tail
    
    def test_parser_statistics(self):
        """Test parser statistics tracking."""
        parser = MendiProtobufParser()
        
        # Parse some valid packets
        valid_packet = b'\x0a\x03\x08\xc3\x1d\x10\x01\x18\x01'
        for _ in range(3):
            parser.parse_fc3eabb5(valid_packet)
        
        # Parse some invalid packets
        invalid_packet = b'\xff' * 9
        for _ in range(2):
            parser.parse_fc3eabb5(invalid_packet)
        
        # Check statistics
        stats = parser.stats
        assert stats['packets_parsed'] == 3
        assert stats['errors'] == 2
        assert 0.5 < stats['success_rate'] < 0.7
    
    def test_timestamp_ordering(self):
        """Test that timestamps increase with each sample."""
        parser = MendiProtobufParser()
        packet = b'\x0a\x03\x08\xc3\x1d\x10\x01\x18\x01'
        
        samples = []
        for _ in range(3):
            sample = parser.parse_fc3eabb5(packet)
            samples.append(sample)
            # Small delay to ensure different timestamps
            import time
            time.sleep(0.001)
        
        # Verify timestamps are increasing
        for i in range(1, len(samples)):
            assert samples[i].timestamp > samples[i-1].timestamp