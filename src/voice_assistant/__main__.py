import argparse
import asyncio
import signal

from .assistant import VoiceAssistant
from .config import DEFAULT_PERSONALITY, PERSONALITIES


async def run_assistant(personality_name: str, enable_eye: bool) -> None:
    """Run the voice assistant with proper signal handling."""
    assistant = VoiceAssistant(personality=personality_name, enable_eye_display=enable_eye)
    loop = asyncio.get_running_loop()

    def handle_signal():
        """Signal handler that properly cancels async tasks."""
        assistant.shutdown()
        # Also cancel all running tasks to ensure quick exit
        for task in asyncio.all_tasks(loop):
            if task is not asyncio.current_task():
                task.cancel()

    # Register signal handlers in the event loop context
    loop.add_signal_handler(signal.SIGINT, handle_signal)
    loop.add_signal_handler(signal.SIGTERM, handle_signal)

    try:
        await assistant.run()
    except asyncio.CancelledError:
        pass


def main() -> None:
    """Entry point for the voice assistant."""
    parser = argparse.ArgumentParser(description="Voice Assistant with multiple personalities")
    parser.add_argument(
        "-p", "--personality",
        choices=list(PERSONALITIES.keys()),
        default=DEFAULT_PERSONALITY,
        help=f"Personality to use (default: {DEFAULT_PERSONALITY})",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available personalities and exit",
    )
    parser.add_argument(
        "-e", "--eye",
        action="store_true",
        help="Enable animated eye display (requires pygame)",
    )
    args = parser.parse_args()

    if args.list:
        print("Available personalities:")
        for key, p in PERSONALITIES.items():
            default = " (default)" if key == DEFAULT_PERSONALITY else ""
            print(f"  {key}: {p.name}{default}")
        return

    try:
        asyncio.run(run_assistant(args.personality, args.eye))
    except KeyboardInterrupt:
        pass

    print("Goodbye!")


if __name__ == "__main__":
    main()
