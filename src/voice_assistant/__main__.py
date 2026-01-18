import asyncio
import signal
import sys

from .assistant import VoiceAssistant


async def run_assistant() -> None:
    """Run the voice assistant with proper signal handling."""
    assistant = VoiceAssistant()
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
    try:
        asyncio.run(run_assistant())
    except KeyboardInterrupt:
        pass

    print("Goodbye!")


if __name__ == "__main__":
    main()
