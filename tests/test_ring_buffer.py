"""
Tests for audio ring buffer (pre-roll buffering).
"""

import pytest
import numpy as np
from app.audio_io import RingBuffer


def test_ring_buffer_creation():
    """Test creating a ring buffer."""
    buffer = RingBuffer(duration_seconds=2.0, sample_rate=16000, channels=1)
    
    assert buffer.duration_seconds == 2.0
    assert buffer.sample_rate == 16000
    assert buffer.channels == 1
    assert buffer.get_duration() == 0.0
    assert buffer.get_buffered_audio() is None


def test_ring_buffer_add_chunk():
    """Test adding audio chunks to buffer."""
    buffer = RingBuffer(duration_seconds=2.0, sample_rate=16000, channels=1)
    
    # Create a 0.1s chunk (1600 samples at 16kHz)
    chunk = np.random.rand(1600).astype(np.float32)
    buffer.add_chunk(chunk)
    
    assert buffer.get_duration() > 0.0
    assert buffer.get_buffered_audio() is not None
    assert len(buffer.get_buffered_audio()) == 1600


def test_ring_buffer_multiple_chunks():
    """Test adding multiple chunks."""
    buffer = RingBuffer(duration_seconds=2.0, sample_rate=16000, channels=1)
    
    # Add 10 chunks of 0.1s each (total 1s)
    for _ in range(10):
        chunk = np.random.rand(1600).astype(np.float32)
        buffer.add_chunk(chunk)
    
    duration = buffer.get_duration()
    assert 0.9 < duration < 1.1  # Approximately 1 second
    
    buffered = buffer.get_buffered_audio()
    assert buffered is not None
    assert len(buffered) == 16000  # 1 second at 16kHz


def test_ring_buffer_overflow():
    """Test that old chunks are dropped when buffer is full."""
    buffer = RingBuffer(duration_seconds=1.0, sample_rate=16000, channels=1)
    
    # Add 20 chunks of 0.1s each (total 2s, should keep only last 1s)
    for i in range(20):
        chunk = np.ones(1600, dtype=np.float32) * i  # Distinct values
        buffer.add_chunk(chunk)
    
    duration = buffer.get_duration()
    assert duration <= 1.2  # Should be around 1s (with some tolerance for chunk boundaries)
    
    buffered = buffer.get_buffered_audio()
    # Should contain recent chunks (higher values)
    assert np.mean(buffered) > 10  # Average should be from later chunks


def test_ring_buffer_is_full():
    """Test is_full() method."""
    buffer = RingBuffer(duration_seconds=1.0, sample_rate=16000, channels=1)
    
    assert not buffer.is_full()
    
    # Add 0.5s of audio
    for _ in range(5):
        chunk = np.random.rand(1600).astype(np.float32)
        buffer.add_chunk(chunk)
    
    assert not buffer.is_full()
    
    # Add another 0.6s (total 1.1s, should be full)
    for _ in range(6):
        chunk = np.random.rand(1600).astype(np.float32)
        buffer.add_chunk(chunk)
    
    # Should be full now (>=  1.0s)
    assert buffer.is_full()


def test_ring_buffer_clear():
    """Test clearing the buffer."""
    buffer = RingBuffer(duration_seconds=2.0, sample_rate=16000, channels=1)
    
    # Add some chunks
    for _ in range(5):
        chunk = np.random.rand(1600).astype(np.float32)
        buffer.add_chunk(chunk)
    
    assert buffer.get_duration() > 0.0
    assert buffer.get_buffered_audio() is not None
    
    # Clear buffer
    buffer.clear()
    
    assert buffer.get_duration() == 0.0
    assert buffer.get_buffered_audio() is None


def test_ring_buffer_concatenation():
    """Test that buffered audio is correctly concatenated."""
    buffer = RingBuffer(duration_seconds=2.0, sample_rate=16000, channels=1)
    
    # Add chunks with distinct patterns
    chunk1 = np.ones(1600, dtype=np.float32) * 1.0
    chunk2 = np.ones(1600, dtype=np.float32) * 2.0
    chunk3 = np.ones(1600, dtype=np.float32) * 3.0
    
    buffer.add_chunk(chunk1)
    buffer.add_chunk(chunk2)
    buffer.add_chunk(chunk3)
    
    buffered = buffer.get_buffered_audio()
    
    # Should be concatenated in order
    assert len(buffered) == 4800  # 3 chunks * 1600 samples
    assert np.allclose(buffered[:1600], 1.0)
    assert np.allclose(buffered[1600:3200], 2.0)
    assert np.allclose(buffered[3200:], 3.0)


def test_ring_buffer_different_sample_rates():
    """Test ring buffer with different sample rates."""
    # 8kHz buffer
    buffer_8k = RingBuffer(duration_seconds=1.0, sample_rate=8000, channels=1)
    chunk_8k = np.random.rand(800).astype(np.float32)  # 0.1s at 8kHz
    buffer_8k.add_chunk(chunk_8k)
    
    # 44.1kHz buffer
    buffer_44k = RingBuffer(duration_seconds=1.0, sample_rate=44100, channels=1)
    chunk_44k = np.random.rand(4410).astype(np.float32)  # 0.1s at 44.1kHz
    buffer_44k.add_chunk(chunk_44k)
    
    # Both should have similar durations
    assert 0.09 < buffer_8k.get_duration() < 0.11
    assert 0.09 < buffer_44k.get_duration() < 0.11
