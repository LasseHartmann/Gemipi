import asyncio
import logging
import os
import time
from enum import Enum, auto

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .audio import AudioCapture, AudioPlayer
from .config import AudioConfig, GeminiConfig, GLaDOSEffectsConfig, WakeWordConfig
from .glados_effects import GLaDOSEffectsProcessor
from .wakeword import WakeWordDetector

logger = logging.getLogger('assistant')


class AssistantState(Enum):
    """State machine states for the voice assistant."""

    LISTENING = auto()   # Waiting for wake word
    ACTIVATED = auto()   # Wake word detected, connected to Gemini
    RESPONDING = auto()  # Gemini is generating a response


class VoiceAssistant:
    """Real-time voice assistant using Gemini Live API with wake word detection."""

    def __init__(
        self,
        audio_config: AudioConfig | None = None,
        gemini_config: GeminiConfig | None = None,
        wakeword_config: WakeWordConfig | None = None,
        glados_effects_config: GLaDOSEffectsConfig | None = None,
    ):
        load_dotenv()
        self.audio_config = audio_config or AudioConfig()
        self.gemini_config = gemini_config or GeminiConfig()
        self.wakeword_config = wakeword_config or WakeWordConfig()
        self.glados_effects_config = glados_effects_config or GLaDOSEffectsConfig()

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        self._client = genai.Client(api_key=api_key)

        # Initialize GLaDOS effects processor if enabled
        self._effects_processor: GLaDOSEffectsProcessor | None = None
        if self.glados_effects_config.enabled:
            self._effects_processor = GLaDOSEffectsProcessor(
                config=self.glados_effects_config,
                sample_rate=self.audio_config.playback_sample_rate,
            )

        # AEC disabled - using mic-mute during playback instead
        self._capture = AudioCapture(self.audio_config)
        self._player = AudioPlayer(self.audio_config, effects_processor=self._effects_processor)
        self._running = False
        self._state = AssistantState.LISTENING
        self._last_activity_time = 0.0
        self._wakeword_detector: WakeWordDetector | None = None

        # Initialize wake word detector if enabled
        if self.wakeword_config.enabled:
            self._wakeword_detector = WakeWordDetector(
                model_path=self.wakeword_config.model_path,
                threshold=self.wakeword_config.threshold,
                inference_framework=self.wakeword_config.inference_framework,
            )

    async def _send_audio(self, session) -> None:
        """Send audio from microphone to Gemini.

        Mic is muted during RESPONDING state to prevent self-interruption.
        """
        async for chunk in self._capture.stream():
            if not self._running or self._state == AssistantState.LISTENING:
                break

            # Mute mic while assistant is speaking (no AEC available)
            if self._state == AssistantState.RESPONDING:
                continue

            await session.send(
                input=types.LiveClientRealtimeInput(
                    media_chunks=[
                        types.Blob(
                            data=chunk,
                            mime_type=f"audio/pcm;rate={self.audio_config.send_sample_rate}",
                        )
                    ]
                )
            )
            self._last_activity_time = time.monotonic()

    async def _receive_audio(self, session) -> None:
        """Receive and play audio from Gemini."""
        while self._running and self._state != AssistantState.LISTENING:
            try:
                async for response in session.receive():
                    if not self._running or self._state == AssistantState.LISTENING:
                        break

                    server_content = response.server_content
                    if server_content:
                        if server_content.model_turn:
                            self._state = AssistantState.RESPONDING
                            for part in server_content.model_turn.parts:
                                if part.inline_data:
                                    self._player.play_sync(part.inline_data.data)

                        if server_content.turn_complete:
                            self._state = AssistantState.ACTIVATED
                            self._last_activity_time = time.monotonic()

            except Exception as e:
                if self._running:
                    logger.error(f"Receive error: {e}")
                break

    async def _check_timeout(self) -> None:
        """Check for inactivity timeout and return to listening state."""
        while self._running and self._state != AssistantState.LISTENING:
            await asyncio.sleep(1.0)
            if self._state == AssistantState.ACTIVATED:
                elapsed = time.monotonic() - self._last_activity_time
                if elapsed >= self.wakeword_config.timeout:
                    print("\nTimeout - returning to wake word listening...")
                    self._state = AssistantState.LISTENING
                    break

    async def _listen_for_wakeword(self) -> bool:
        """Listen for wake word and return True when detected.

        Returns:
            True if wake word detected, False if assistant is shutting down.
        """
        if not self._wakeword_detector:
            return True  # Wake word disabled, proceed immediately

        print("Listening for wake word...")
        self._wakeword_detector.reset()

        async for chunk in self._capture.stream():
            if not self._running:
                return False

            detected = self._wakeword_detector.process_audio(chunk)
            if detected:
                print(f"\nWake word '{detected}' detected!")
                return True

        return False

    async def _run_session(self) -> None:
        """Run a single Gemini session after wake word detection."""
        self._state = AssistantState.ACTIVATED
        self._last_activity_time = time.monotonic()

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(
                parts=[types.Part(text=self.gemini_config.system_instruction)]
            ),
        )

        try:
            async with self._client.aio.live.connect(
                model=self.gemini_config.model,
                config=config,
            ) as session:
                print("Connected to Gemini.")

                # Send activation prompt to make Gemini speak a varied greeting
                if self.wakeword_config.activation_prompt:
                    prompt = "[Begrüßung] Begrüße den Benutzer kurz und knapp im GLaDOS-Stil. Variiere deine Begrüßung jedes Mal."
                    await session.send(
                        input=types.LiveClientContent(
                            turns=[
                                types.Content(
                                    role="user",
                                    parts=[types.Part(text=prompt)]
                                )
                            ],
                            turn_complete=True,
                        )
                    )
                    # Wait for and play the greeting response
                    async for response in session.receive():
                        server_content = response.server_content
                        if server_content:
                            if server_content.model_turn:
                                for part in server_content.model_turn.parts:
                                    if part.inline_data:
                                        self._player.play_sync(part.inline_data.data)
                            if server_content.turn_complete:
                                break

                print("Listening for your question...\n")
                self._last_activity_time = time.monotonic()

                send_task = asyncio.create_task(self._send_audio(session))
                receive_task = asyncio.create_task(self._receive_audio(session))
                timeout_task = asyncio.create_task(self._check_timeout())

                # Wait until we return to listening state or shutdown
                await asyncio.gather(send_task, receive_task, timeout_task)

        except Exception as e:
            print(f"Session error: {e}")

        self._state = AssistantState.LISTENING

    async def run(self) -> None:
        """Start the voice assistant with wake word detection."""
        if self.wakeword_config.enabled:
            print("Starting voice assistant with wake word detection...")
            print(f"Wake word model: {self._wakeword_detector.model_names}")
            print(f"Threshold: {self.wakeword_config.threshold}")
            print(f"Timeout: {self.wakeword_config.timeout}s")
        else:
            print("Starting voice assistant (wake word disabled)...")
        print(f"Model: {self.gemini_config.model}")
        if self.glados_effects_config.enabled:
            print(f"GLaDOS effects: enabled (pitch +{self.glados_effects_config.pitch_shift} semitones)")
        else:
            print("GLaDOS effects: disabled")
        print("Press Ctrl+C to exit.\n")

        self._running = True
        self._capture.start()
        self._player.start()

        try:
            while self._running:
                if self.wakeword_config.enabled:
                    # Wait for wake word
                    detected = await self._listen_for_wakeword()
                    if not detected:
                        break

                # Run Gemini session
                await self._run_session()

                if not self.wakeword_config.enabled:
                    # If wake word disabled, only run one session
                    break

        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Clean up resources."""
        if not self._running:
            return
        print("\nShutting down...")
        self._running = False
        self._state = AssistantState.LISTENING
        self._capture.stop()
        self._player.stop()
