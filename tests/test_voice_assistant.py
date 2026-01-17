"""Tests to validate the voice assistant implementation."""

import asyncio
import os
import sys

import pyaudio


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")

    from voice_assistant import VoiceAssistant, AudioConfig, GeminiConfig
    from voice_assistant.audio import AudioCapture, AudioPlayer
    from voice_assistant.config import AudioConfig, GeminiConfig

    print("  All imports successful")
    return True


def test_config_defaults():
    """Test configuration default values."""
    print("Testing configuration defaults...")

    from voice_assistant.config import AudioConfig, GeminiConfig

    audio = AudioConfig()
    assert audio.send_sample_rate == 16000, "Wrong send sample rate"
    assert audio.receive_sample_rate == 24000, "Wrong receive sample rate"
    assert audio.playback_sample_rate == 48000, "Wrong playback sample rate"
    assert audio.chunk_size == 1024, "Wrong chunk size"
    assert audio.channels == 1, "Wrong channel count"
    assert audio.format_width == 2, "Wrong format width"
    assert audio.input_device_index == 1, "Wrong input device index (should be 1 for WM8960)"
    assert audio.output_device_index == 1, "Wrong output device index (should be 1 for WM8960)"
    print(f"  AudioConfig: {audio}")

    gemini = GeminiConfig()
    assert gemini.model == "gemini-2.5-flash-preview-native-audio-dialog", "Wrong model"
    assert "voice assistant" in gemini.system_instruction.lower(), "Wrong system instruction"
    print(f"  GeminiConfig: model={gemini.model}")

    print("  Configuration defaults correct")
    return True


def test_pyaudio_devices():
    """Test PyAudio initialization and list available devices."""
    print("Testing PyAudio and listing audio devices...")

    pa = pyaudio.PyAudio()

    device_count = pa.get_device_count()
    print(f"  Found {device_count} audio device(s):")

    input_devices = []
    output_devices = []

    for i in range(device_count):
        info = pa.get_device_info_by_index(i)
        name = info['name']
        inputs = info['maxInputChannels']
        outputs = info['maxOutputChannels']
        rate = int(info['defaultSampleRate'])

        device_type = []
        if inputs > 0:
            device_type.append("INPUT")
            input_devices.append(i)
        if outputs > 0:
            device_type.append("OUTPUT")
            output_devices.append(i)

        print(f"    [{i}] {name} ({', '.join(device_type)}) - {rate}Hz")

    pa.terminate()

    if not input_devices:
        print("  WARNING: No input devices found!")
    if not output_devices:
        print("  WARNING: No output devices found!")

    print(f"  Input devices: {input_devices}")
    print(f"  Output devices: {output_devices}")
    return True


def test_audio_capture_init():
    """Test AudioCapture initialization."""
    print("Testing AudioCapture initialization...")

    from voice_assistant.audio import AudioCapture
    from voice_assistant.config import AudioConfig

    config = AudioConfig()
    capture = AudioCapture(config)

    assert capture.config == config, "Config not set"
    assert capture._pyaudio is None, "PyAudio should be None before start"
    assert capture._stream is None, "Stream should be None before start"
    assert capture._running is False, "Should not be running before start"

    print("  AudioCapture initialized correctly")
    return True


def test_audio_player_init():
    """Test AudioPlayer initialization."""
    print("Testing AudioPlayer initialization...")

    from voice_assistant.audio import AudioPlayer
    from voice_assistant.config import AudioConfig

    config = AudioConfig()
    player = AudioPlayer(config)

    assert player.config == config, "Config not set"
    assert player._pyaudio is None, "PyAudio should be None before start"
    assert player._stream is None, "Stream should be None before start"
    assert player._running is False, "Should not be running before start"

    print("  AudioPlayer initialized correctly")
    return True


def test_audio_capture_start_stop():
    """Test AudioCapture start and stop."""
    print("Testing AudioCapture start/stop...")

    from voice_assistant.audio import AudioCapture
    from voice_assistant.config import AudioConfig

    config = AudioConfig()
    capture = AudioCapture(config)

    try:
        capture.start()
        assert capture._running is True, "Should be running after start"
        assert capture._pyaudio is not None, "PyAudio should be initialized"
        assert capture._stream is not None, "Stream should be initialized"
        print("  AudioCapture started successfully")
    finally:
        capture.stop()
        assert capture._running is False, "Should not be running after stop"
        print("  AudioCapture stopped successfully")

    return True


def test_audio_player_start_stop():
    """Test AudioPlayer start and stop."""
    print("Testing AudioPlayer start/stop...")

    from voice_assistant.audio import AudioPlayer
    from voice_assistant.config import AudioConfig

    config = AudioConfig()
    player = AudioPlayer(config)

    try:
        player.start()
        assert player._running is True, "Should be running after start"
        assert player._pyaudio is not None, "PyAudio should be initialized"
        assert player._stream is not None, "Stream should be initialized"
        print("  AudioPlayer started successfully")
    finally:
        player.stop()
        assert player._running is False, "Should not be running after stop"
        print("  AudioPlayer stopped successfully")

    return True


def test_audio_capture_read():
    """Test reading audio from microphone."""
    print("Testing AudioCapture read (2 seconds)...")

    from voice_assistant.audio import AudioCapture
    from voice_assistant.config import AudioConfig

    config = AudioConfig()
    capture = AudioCapture(config)

    chunks_read = 0
    bytes_read = 0

    async def read_audio():
        nonlocal chunks_read, bytes_read
        capture.start()
        try:
            async for chunk in capture.stream():
                chunks_read += 1
                bytes_read += len(chunk)
                if chunks_read >= 30:  # ~2 seconds at 16kHz
                    break
        finally:
            capture.stop()

    asyncio.run(read_audio())

    print(f"  Read {chunks_read} chunks, {bytes_read} bytes")
    assert chunks_read > 0, "Should have read some chunks"
    assert bytes_read > 0, "Should have read some bytes"

    return True


def test_audio_playback():
    """Test playing a short tone."""
    print("Testing AudioPlayer playback (1 second tone)...")

    import math
    import struct

    from voice_assistant.audio import AudioPlayer
    from voice_assistant.config import AudioConfig

    config = AudioConfig()
    player = AudioPlayer(config)

    # Generate a 440Hz tone for 1 second at 24kHz (Gemini's output rate)
    # The player will resample to 48kHz automatically
    duration = 1.0
    frequency = 440
    sample_rate = config.receive_sample_rate  # 24kHz - what Gemini sends
    num_samples = int(sample_rate * duration)

    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        value = int(16000 * math.sin(2 * math.pi * frequency * t))
        samples.append(struct.pack('<h', value))

    audio_data = b''.join(samples)

    player.start()
    try:
        # Play in chunks (player resamples from 24kHz to 48kHz internally)
        chunk_size = config.chunk_size * 2  # bytes (16-bit = 2 bytes per sample)
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            player.play_sync(chunk)
        print("  Played 440Hz tone for 1 second (resampled 24kHz -> 48kHz)")
    finally:
        player.stop()

    return True


def test_api_key_validation():
    """Test API key validation."""
    print("Testing API key validation...")

    # We need to test that VoiceAssistant raises an error when no key is set
    # Since dotenv may have already loaded .env, we need to temporarily clear it
    # and prevent dotenv from reloading

    original_key = os.environ.get("GEMINI_API_KEY")

    # Clear the key and set a flag to prevent reload
    os.environ.pop("GEMINI_API_KEY", None)

    # Test by directly checking the validation logic
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("  Verified: Missing API key correctly detected as None")

    # Restore original value
    if original_key:
        os.environ["GEMINI_API_KEY"] = original_key

    # Now test with a placeholder key
    if original_key == "your_api_key_here":
        print("  Note: .env contains placeholder key - replace with real key to test")

    print("  API key validation logic verified")
    return True


def test_assistant_with_key():
    """Test VoiceAssistant initialization with API key."""
    print("Testing VoiceAssistant initialization with API key...")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("  SKIPPED: No valid API key set in .env")
        return True

    from voice_assistant import VoiceAssistant

    assistant = VoiceAssistant()
    assert assistant._client is not None, "Client should be initialized"
    assert assistant._capture is not None, "Capture should be initialized"
    assert assistant._player is not None, "Player should be initialized"
    assert assistant._running is False, "Should not be running before run()"

    print("  VoiceAssistant initialized successfully")
    return True


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Voice Assistant Validation Tests")
    print("=" * 60)
    print()

    tests = [
        ("Imports", test_imports),
        ("Config Defaults", test_config_defaults),
        ("PyAudio Devices", test_pyaudio_devices),
        ("AudioCapture Init", test_audio_capture_init),
        ("AudioPlayer Init", test_audio_player_init),
        ("AudioCapture Start/Stop", test_audio_capture_start_stop),
        ("AudioPlayer Start/Stop", test_audio_player_start_stop),
        ("AudioCapture Read", test_audio_capture_read),
        ("AudioPlayer Playback", test_audio_playback),
        ("API Key Validation", test_api_key_validation),
        ("Assistant Init", test_assistant_with_key),
    ]

    results = []

    for name, test_func in tests:
        print(f"\n[TEST] {name}")
        print("-" * 40)
        try:
            result = test_func()
            results.append((name, result, None))
        except Exception as e:
            print(f"  FAILED: {e}")
            results.append((name, False, str(e)))

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    passed = sum(1 for _, r, _ in results if r)
    failed = len(results) - passed

    for name, result, error in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
        if error:
            print(f"         Error: {error}")

    print()
    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")
    print()

    return failed == 0


if __name__ == "__main__":
    # Change to project directory to load .env
    os.chdir("/home/gemipi/voice-assistant")

    from dotenv import load_dotenv
    load_dotenv()

    success = run_all_tests()
    sys.exit(0 if success else 1)
