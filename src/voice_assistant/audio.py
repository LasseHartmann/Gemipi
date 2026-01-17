import asyncio
import struct
import threading
import pyaudio
from collections import deque
from collections.abc import AsyncGenerator

from .config import AudioConfig


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

    def __init__(self, config: AudioConfig):
        self.config = config
        self._pyaudio: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._running = False
        self._buffer: deque[bytes] = deque(maxlen=100)
        self._lock = threading.Lock()
        self._event = asyncio.Event()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for capturing audio."""
        if self._running:
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

    def __init__(self, config: AudioConfig):
        self.config = config
        self._pyaudio: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._running = False

    def start(self) -> None:
        """Initialize and start the audio playback stream."""
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
                await loop.run_in_executor(None, self._stream.write, resampled)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    def play_sync(self, data: bytes) -> None:
        """Synchronously write audio data to the stream (with resampling)."""
        if self._stream and self._running:
            resampled = resample_linear(
                data,
                self.config.receive_sample_rate,
                self.config.playback_sample_rate
            )
            self._stream.write(resampled)
