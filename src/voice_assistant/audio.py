import asyncio
import contextlib
import os
import struct
import threading
import time
from typing import TYPE_CHECKING
import pyaudio
import numpy as np
from collections import deque
from collections.abc import AsyncGenerator

from .config import AudioConfig

if TYPE_CHECKING:
    from .glados_effects import GLaDOSEffectsProcessor


@contextlib.contextmanager
def _suppress_alsa_errors():
    """Suppress ALSA/JACK warnings during PyAudio initialization."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(old_stderr)


class AcousticEchoCanceller:
    """Echo suppression using playback-aware gating with interrupt detection.

    Mutes mic during playback to prevent self-interruption, but allows
    user to interrupt by speaking louder than a threshold.
    """

    def __init__(self, frame_size: int, sample_rate: int, filter_length: int = 2048):
        """Initialize echo canceller.

        Args:
            frame_size: Number of samples per frame (must match audio chunk size).
            sample_rate: Audio sample rate in Hz.
            filter_length: Not used (kept for API compatibility).
        """
        self._frame_size = frame_size
        self._frame_bytes = frame_size * 2  # 16-bit = 2 bytes per sample
        self._lock = threading.Lock()

        # Playback state tracking
        self._playback_active = False
        self._playback_energy = 0.0
        self._silence_frames = 0

        # Energy threshold for interrupt detection (user speaking over playback)
        # This is relative to playback energy
        self._interrupt_threshold = 3.0  # User must be 3x louder than playback
        self._silence_threshold = 0.001  # Minimum energy to consider as speech
        self._silence_frames_needed = 10  # Frames of silence before allowing mic through

        # Smoothing for energy estimation
        self._energy_alpha = 0.3

        # Playback queue for synchronization
        self._playback_queue: deque[np.ndarray] = deque(maxlen=50)

        # Accumulation buffer for partial playback chunks
        self._playback_buffer = np.array([], dtype=np.float32)

        # Timing stats for performance monitoring
        self._process_times: list[float] = []
        self._process_count = 0
        self._stats_interval = 100  # Print stats every N frames

        # Shutdown flag for fast exit
        self._shutdown = False

    def feed_playback(self, data: bytes) -> None:
        """Feed playback audio to the echo canceller reference buffer."""
        # Convert bytes to float32 samples
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

        with self._lock:
            # Accumulate samples in buffer
            self._playback_buffer = np.concatenate([self._playback_buffer, samples])

            # Extract complete frame-sized chunks
            while len(self._playback_buffer) >= self._frame_size:
                chunk = self._playback_buffer[:self._frame_size]
                self._playback_buffer = self._playback_buffer[self._frame_size:]
                self._playback_queue.append(chunk)

    def process(self, mic_data: bytes) -> bytes:
        """Process microphone input and remove echo using FDAF algorithm.

        Uses overlap-save method with FFT for efficient block processing.

        Args:
            mic_data: Raw microphone input (16-bit PCM).

        Returns:
            Echo-cancelled audio.
        """
        if len(mic_data) != self._frame_bytes or self._shutdown:
            return mic_data

        # Convert mic input to float64 for better FFT precision
        mic_samples = np.frombuffer(mic_data, dtype=np.int16).astype(np.float64) / 32768.0

        start_time = time.perf_counter()

        with self._lock:
            # Get reference playback (or pass through if none)
            if not self._playback_queue:
                return mic_data
            ref_samples = self._playback_queue.popleft().astype(np.float64)

            B = self._frame_size
            L = self._fft_size

            # Update reference buffer (overlap-save: shift and add new block)
            self._ref_buffer[:B] = self._ref_buffer[B:]
            self._ref_buffer[B:] = ref_samples

            # FFT of reference signal
            X = np.fft.fft(self._ref_buffer)

            # Compute filter output in frequency domain
            Y = self._W * X

            # IFFT and take last B samples (overlap-save)
            y = np.real(np.fft.ifft(Y))[B:]

            # Error signal (microphone - estimated echo)
            error = mic_samples - y

            # Update power spectrum estimate (smoothed)
            self._P = self._beta * self._P + (1 - self._beta) * np.abs(X) ** 2

            # Compute gradient in frequency domain
            # Pad error with zeros for proper correlation
            e_padded = np.concatenate([np.zeros(B), error])
            E = np.fft.fft(e_padded)

            # Normalized frequency domain update
            gradient = np.conj(X) * E / (self._P + self._eps)
            self._W += self._mu * gradient

            # Gradient constraint: force filter to be causal
            # Transform to time domain, zero out non-causal part, transform back
            w_time = np.fft.ifft(self._W)
            w_time[B:] = 0  # Keep only first B samples (causal part)
            self._W = np.fft.fft(w_time)

            output = error

            # Safety check: if output contains NaN/Inf, pass through original
            if not np.isfinite(output).all():
                output = mic_samples

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self._process_times.append(elapsed_ms)
        self._process_count += 1

        # Print stats periodically
        if self._process_count % self._stats_interval == 0:
            avg_ms = sum(self._process_times) / len(self._process_times)
            max_ms = max(self._process_times)
            frame_duration_ms = (self._frame_size / 16000) * 1000  # At 16kHz
            # Calculate echo reduction ratio
            mic_power = np.mean(mic_samples ** 2)
            out_power = np.mean(output ** 2)
            reduction_db = 10 * np.log10(out_power / (mic_power + 1e-10))
            print(f"[AEC] {self._process_count} frames: avg={avg_ms:.1f}ms, max={max_ms:.1f}ms, reduction={reduction_db:.1f}dB")
            self._process_times.clear()

        # Convert back to int16 bytes
        output_int16 = np.clip(output * 32768, -32768, 32767).astype(np.int16)
        return output_int16.tobytes()

    def clear(self) -> None:
        """Clear buffers and reset filter."""
        with self._lock:
            self._playback_queue.clear()
            self._ref_buffer.fill(0)
            self._W.fill(0)
            self._P.fill(self._eps)

    def shutdown(self) -> None:
        """Signal shutdown to exit processing early."""
        self._shutdown = True


def resample_linear(data: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resample 16-bit PCM audio using linear interpolation."""
    if from_rate == to_rate:
        return data

    samples = struct.unpack(f'<{len(data) // 2}h', data)
    if not samples:
        return data

    ratio = to_rate / from_rate
    new_length = int(len(samples) * ratio)

    resampled = []
    for i in range(new_length):
        src_idx = i / ratio
        idx = int(src_idx)
        frac = src_idx - idx

        if idx + 1 < len(samples):
            sample = int(samples[idx] * (1 - frac) + samples[idx + 1] * frac)
        else:
            sample = samples[-1]

        sample = max(-32768, min(32767, sample))
        resampled.append(sample)

    return struct.pack(f'<{len(resampled)}h', *resampled)


class AudioCapture:
    """Captures audio from microphone using callback mode."""

    def __init__(self, config: AudioConfig, echo_canceller: AcousticEchoCanceller | None = None):
        self.config = config
        self._echo_canceller = echo_canceller
        self._pyaudio: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._running = False
        self._buffer: deque[bytes] = deque(maxlen=100)
        self._lock = threading.Lock()
        self._event = asyncio.Event()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for capturing audio."""
        if self._running:
            # Apply echo cancellation if available
            if self._echo_canceller:
                in_data = self._echo_canceller.process(in_data)
            with self._lock:
                self._buffer.append(in_data)
            # Signal that new data is available
            try:
                self._event.set()
            except RuntimeError:
                pass  # Event loop might not be running
        return (None, pyaudio.paContinue)

    def start(self) -> None:
        """Initialize and start the audio capture stream."""
        with _suppress_alsa_errors():
            self._pyaudio = pyaudio.PyAudio()
        self._running = True
        self._stream = self._pyaudio.open(
            format=pyaudio.paInt16,
            channels=self.config.channels,
            rate=self.config.send_sample_rate,
            input=True,
            input_device_index=self.config.input_device_index,
            frames_per_buffer=self.config.chunk_size,
            stream_callback=self._audio_callback,
        )
        self._stream.start_stream()

    def stop(self) -> None:
        """Stop and clean up the audio capture stream."""
        self._running = False
        # Signal AEC to exit early
        if self._echo_canceller:
            self._echo_canceller.shutdown()
        stream = self._stream
        self._stream = None
        if stream:
            try:
                if stream.is_active():
                    stream.abort()  # Faster than stop_stream()
                stream.close()
            except Exception:
                pass
        pa = self._pyaudio
        self._pyaudio = None
        if pa:
            try:
                pa.terminate()
            except Exception:
                pass

    async def stream(self) -> AsyncGenerator[bytes, None]:
        """Async generator that yields audio chunks from the microphone."""
        while self._running:
            # Wait for data or timeout
            try:
                await asyncio.wait_for(self._event.wait(), timeout=0.1)
                self._event.clear()
            except asyncio.TimeoutError:
                continue

            # Get all available data
            while True:
                with self._lock:
                    if not self._buffer:
                        break
                    data = self._buffer.popleft()
                yield data


class AudioPlayer:
    """Plays audio to the speaker."""

    def __init__(
        self,
        config: AudioConfig,
        echo_canceller: AcousticEchoCanceller | None = None,
        effects_processor: "GLaDOSEffectsProcessor | None" = None,
    ):
        self.config = config
        self._echo_canceller = echo_canceller
        self._effects_processor = effects_processor
        self._pyaudio: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._running = False

    def start(self) -> None:
        """Initialize and start the audio playback stream."""
        with _suppress_alsa_errors():
            self._pyaudio = pyaudio.PyAudio()
        self._stream = self._pyaudio.open(
            format=pyaudio.paInt16,
            channels=self.config.channels,
            rate=self.config.playback_sample_rate,
            output=True,
            output_device_index=self.config.output_device_index,
            frames_per_buffer=self.config.chunk_size,
        )
        self._running = True

    def stop(self) -> None:
        """Stop and clean up the audio playback stream."""
        self._running = False
        stream = self._stream
        self._stream = None
        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        pa = self._pyaudio
        self._pyaudio = None
        if pa:
            try:
                pa.terminate()
            except Exception:
                pass

    async def play(self, queue: asyncio.Queue[bytes | None]) -> None:
        """Play audio from queue until None is received or stopped."""
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=0.1)
                if data is None:
                    break
                resampled = resample_linear(
                    data,
                    self.config.receive_sample_rate,
                    self.config.playback_sample_rate
                )
                # Apply GLaDOS effects after resampling
                if self._effects_processor:
                    resampled = self._effects_processor.process(resampled)
                # Feed to echo canceller before playing
                if self._echo_canceller:
                    self._echo_canceller.feed_playback(resampled)
                await loop.run_in_executor(None, self._stream.write, resampled)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    def play_sync(self, data: bytes) -> None:
        """Synchronously write audio data to the stream (with resampling and effects)."""
        if self._stream and self._running:
            resampled = resample_linear(
                data,
                self.config.receive_sample_rate,
                self.config.playback_sample_rate
            )
            # Apply GLaDOS effects after resampling
            if self._effects_processor:
                resampled = self._effects_processor.process(resampled)
            # Feed to echo canceller before playing
            if self._echo_canceller:
                self._echo_canceller.feed_playback(resampled)
            self._stream.write(resampled)
