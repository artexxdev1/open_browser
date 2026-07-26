"""Graceful shutdown handling for container orchestrators."""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class ShutdownCoordinator:
    """Coordinates graceful shutdown on SIGTERM/SIGINT."""

    def __init__(self) -> None:
        self._shutdown_event = asyncio.Event()
        self._cleanup_callbacks: list[Callable[[], Awaitable[None]]] = []

    @property
    def is_shutting_down(self) -> bool:
        """Return True when a shutdown signal has been received."""
        return self._shutdown_event.is_set()

    def register_cleanup(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Register an async cleanup callback invoked during shutdown."""
        self._cleanup_callbacks.append(callback)

    async def wait_for_shutdown(self) -> None:
        """Block until a shutdown signal is received."""
        await self._shutdown_event.wait()

    async def shutdown(self) -> None:
        """Run registered cleanup callbacks and mark shutdown complete."""
        if self._shutdown_event.is_set():
            return

        logger.info("Shutdown initiated; running cleanup handlers")
        self._shutdown_event.set()

        for callback in reversed(self._cleanup_callbacks):
            try:
                await callback()
            except Exception:
                logger.exception("Cleanup callback failed")

        logger.info("Shutdown complete")

    def install_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        """Install SIGTERM/SIGINT handlers for graceful shutdown."""

        def _handle_signal(signum: int) -> None:
            signame = signal.Signals(signum).name
            logger.info("Received %s; initiating graceful shutdown", signame)
            loop.create_task(self.shutdown())

        for signum in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(signum, _handle_signal, signum)
            except NotImplementedError:
                # Windows fallback for environments without add_signal_handler.
                signal.signal(signum, lambda *_: loop.create_task(self.shutdown()))
