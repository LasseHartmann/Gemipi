"""GLaDOS-style audio effects processor."""

import numpy as np
from .config import GLaDOSEffectsConfig


class GLaDOSEffectsProcessor:
    """Real-time audio effects for GLaDOS voice.

    Applies pitch shifting, chorus, bitcrushing, and resonance filtering
    to create the characteristic GLaDOS synthetic voice sound.
    """

    def __init__(self, config: GLaDOSEffectsConfig, sample_rate: int = 16000):
        """Initialize the effects processor.

        Args:
            config: Effects configuration.
            sample_rate: Audio sample rate in Hz.
        """
        self.config = config
        self.sample_rate = sample_rate

        # Pitch shift ratio (semitones to frequency ratio)
        self._pitch_ratio = 2 ** (config.pitch_shift / 12.0)

        # Chorus parameters
        self._chorus_delay_samples = int(0.025 * sample_rate)  # 25ms delay
        self._chorus_buffer = np.zeros(self._chorus_delay_samples * 2, dtype=np.float32)
        self._chorus_write_pos = 0
        self._chorus_lfo_phase = 0.0
        self._chorus_lfo_rate = 0.5  # Hz

        # Resonance filter state (2nd order IIR)
        self._resonance_z1 = 0.0
        self._resonance_z2 = 0.0
        self._update_resonance_coefficients()

    def _update_resonance_coefficients(self) -> None:
        """Calculate biquad filter coefficients for resonance."""
        freq = self.config.resonance_freq_hz
        q = 5.0  # Resonance Q factor (higher = more pronounced peak)

        omega = 2.0 * np.pi * freq / self.sample_rate
        alpha = np.sin(omega) / (2.0 * q)

        # Band-pass filter coefficients
        b0 = alpha
        b1 = 0.0
        b2 = -alpha
        a0 = 1.0 + alpha
        a1 = -2.0 * np.cos(omega)
        a2 = 1.0 - alpha

        # Normalize coefficients
        self._res_b0 = b0 / a0
        self._res_b1 = b1 / a0
        self._res_b2 = b2 / a0
        self._res_a1 = a1 / a0
        self._res_a2 = a2 / a0

    def _apply_pitch_shift(self, samples: np.ndarray) -> np.ndarray:
        """Apply pitch shift using linear interpolation resampling.

        Args:
            samples: Input audio samples (float32, -1.0 to 1.0).

        Returns:
            Pitch-shifted audio samples.
        """
        if self._pitch_ratio == 1.0:
            return samples

        # Calculate new length (pitch up = shorter, pitch down = longer)
        new_length = int(len(samples) / self._pitch_ratio)
        if new_length < 1:
            return samples

        # Create output indices
        indices = np.linspace(0, len(samples) - 1, new_length)

        # Linear interpolation
        idx_floor = np.floor(indices).astype(int)
        idx_ceil = np.minimum(idx_floor + 1, len(samples) - 1)
        frac = indices - idx_floor

        output = samples[idx_floor] * (1 - frac) + samples[idx_ceil] * frac

        # Pad or trim to original length to maintain timing
        if len(output) < len(samples):
            output = np.pad(output, (0, len(samples) - len(output)), mode='constant')
        elif len(output) > len(samples):
            output = output[:len(samples)]

        return output.astype(np.float32)

    def _apply_chorus(self, samples: np.ndarray) -> np.ndarray:
        """Apply chorus effect for synthetic quality.

        Args:
            samples: Input audio samples (float32, -1.0 to 1.0).

        Returns:
            Audio with chorus effect applied.
        """
        output = np.zeros_like(samples)
        mix = self.config.chorus_mix

        for i, sample in enumerate(samples):
            # Write to circular buffer
            self._chorus_buffer[self._chorus_write_pos] = sample
            self._chorus_write_pos = (self._chorus_write_pos + 1) % len(self._chorus_buffer)

            # LFO modulates delay time
            lfo = np.sin(2.0 * np.pi * self._chorus_lfo_phase)
            self._chorus_lfo_phase += self._chorus_lfo_rate / self.sample_rate
            if self._chorus_lfo_phase >= 1.0:
                self._chorus_lfo_phase -= 1.0

            # Variable delay (15-35ms range)
            delay = self._chorus_delay_samples + int(lfo * self._chorus_delay_samples * 0.4)
            read_pos = (self._chorus_write_pos - delay) % len(self._chorus_buffer)
            delayed = self._chorus_buffer[read_pos]

            # Mix dry and wet signals
            output[i] = sample * (1 - mix) + delayed * mix

        return output

    def _apply_resonance(self, samples: np.ndarray) -> np.ndarray:
        """Apply resonance filter for metallic quality.

        Args:
            samples: Input audio samples (float32, -1.0 to 1.0).

        Returns:
            Audio with resonance filter applied.
        """
        output = np.zeros_like(samples)

        for i, x in enumerate(samples):
            # Biquad filter (Direct Form II Transposed)
            y = self._res_b0 * x + self._resonance_z1
            self._resonance_z1 = self._res_b1 * x - self._res_a1 * y + self._resonance_z2
            self._resonance_z2 = self._res_b2 * x - self._res_a2 * y

            # Mix filtered with original (30% resonance)
            output[i] = x * 0.7 + y * 0.3

        return output

    def _apply_bitcrush(self, samples: np.ndarray) -> np.ndarray:
        """Apply bitcrushing for quantization artifacts.

        Args:
            samples: Input audio samples (float32, -1.0 to 1.0).

        Returns:
            Bitcrushed audio samples.
        """
        bits = self.config.bitcrush_bits
        levels = 2 ** bits

        # Quantize to reduced bit depth
        quantized = np.round(samples * (levels / 2)) / (levels / 2)

        return quantized.astype(np.float32)

    def process(self, audio_bytes: bytes) -> bytes:
        """Process audio with GLaDOS effects.

        Args:
            audio_bytes: Raw 16-bit PCM audio data.

        Returns:
            Processed audio as 16-bit PCM bytes.
        """
        if not self.config.enabled:
            return audio_bytes

        # Convert bytes to float32 samples (-1.0 to 1.0)
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Apply effects in order
        if self.config.pitch_shift != 0:
            samples = self._apply_pitch_shift(samples)

        if self.config.chorus_enabled:
            samples = self._apply_chorus(samples)

        if self.config.resonance_enabled:
            samples = self._apply_resonance(samples)

        if self.config.bitcrush_enabled:
            samples = self._apply_bitcrush(samples)

        # Convert back to 16-bit PCM bytes
        output = np.clip(samples * 32768, -32768, 32767).astype(np.int16)
        return output.tobytes()

    def reset(self) -> None:
        """Reset all effect states (e.g., between sessions)."""
        self._chorus_buffer.fill(0)
        self._chorus_write_pos = 0
        self._chorus_lfo_phase = 0.0
        self._resonance_z1 = 0.0
        self._resonance_z2 = 0.0
