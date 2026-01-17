import asyncio
import signal

from .assistant import VoiceAssistant


def main() -> None:
    """Entry point for the voice assistant."""
    assistant = VoiceAssistant()

    def handle_signal(sig, frame):
        assistant.shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        asyncio.run(assistant.run())
    except KeyboardInterrupt:
        pass

    print("Goodbye!")


if __name__ == "__main__":
    main()
