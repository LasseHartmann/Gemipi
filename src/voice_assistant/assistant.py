import asyncio
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .audio import AudioCapture, AudioPlayer
from .config import AudioConfig, GeminiConfig


class VoiceAssistant:
    """Real-time voice assistant using Gemini Live API."""

    def __init__(
        self,
        audio_config: AudioConfig | None = None,
        gemini_config: GeminiConfig | None = None,
    ):
        load_dotenv()
        self.audio_config = audio_config or AudioConfig()
        self.gemini_config = gemini_config or GeminiConfig()

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        self._client = genai.Client(api_key=api_key)
        self._capture = AudioCapture(self.audio_config)
        self._player = AudioPlayer(self.audio_config)
        self._running = False

    async def _send_audio(self, session) -> None:
        """Send audio from microphone to Gemini."""
        async for chunk in self._capture.stream():
            if not self._running:
                break
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

    async def _receive_audio(self, session) -> None:
        """Receive and play audio from Gemini."""
        while self._running:
            try:
                async for response in session.receive():
                    if not self._running:
                        break

                    server_content = response.server_content
                    if server_content:
                        if server_content.model_turn:
                            for part in server_content.model_turn.parts:
                                if part.inline_data:
                                    self._player.play_sync(part.inline_data.data)

                        if server_content.turn_complete:
                            pass  # Turn completed, ready for next input

            except Exception as e:
                if self._running:
                    print(f"Receive error: {e}")
                break

    async def run(self) -> None:
        """Start the voice assistant."""
        print("Starting voice assistant...")
        print(f"Model: {self.gemini_config.model}")
        print("Speak into your microphone. Press Ctrl+C to exit.\n")

        self._running = True
        self._capture.start()
        self._player.start()

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
                print("Connected to Gemini. Listening...\n")

                send_task = asyncio.create_task(self._send_audio(session))
                receive_task = asyncio.create_task(self._receive_audio(session))

                await asyncio.gather(send_task, receive_task)

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
        self._capture.stop()
        self._player.stop()
