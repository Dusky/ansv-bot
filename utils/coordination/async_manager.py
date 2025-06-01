"""
Async operation coordination and utilities.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Optional
from functools import wraps


class AsyncManager:
    """Manages async operations and thread pool coordination."""
    
    def __init__(self, max_workers: int = 4):
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bot-worker")
        self._shutdown = False
    
    async def run_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        """Run a synchronous function in the thread pool."""
        if self._shutdown:
            raise RuntimeError("AsyncManager has been shut down")
        
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(self.thread_pool, func, *args, **kwargs)
        except Exception as e:
            logging.error(f"Error running {func.__name__} in thread pool: {e}")
            raise
    
    async def run_with_timeout(self, coro, timeout: float) -> Any:
        """Run a coroutine with a timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logging.warning(f"Operation timed out after {timeout} seconds")
            raise
    
    def create_task(self, coro, name: Optional[str] = None) -> asyncio.Task:
        """Create and return an asyncio task."""
        task = asyncio.create_task(coro, name=name)
        # Add error handling to prevent silent failures
        task.add_done_callback(self._task_error_handler)
        return task
    
    def _task_error_handler(self, task: asyncio.Task) -> None:
        """Handle task errors to prevent silent failures."""
        if task.done() and not task.cancelled():
            try:
                task.result()
            except Exception as e:
                logging.error(f"Task {task.get_name()} failed with error: {e}", exc_info=True)
    
    async def gather_with_error_handling(self, *coros, return_exceptions: bool = True):
        """Gather coroutines with proper error handling."""
        results = await asyncio.gather(*coros, return_exceptions=return_exceptions)
        
        # Log any exceptions that occurred
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logging.error(f"Coroutine {i} failed: {result}", exc_info=result)
        
        return results
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the async manager."""
        self._shutdown = True
        self.thread_pool.shutdown(wait=True)
        logging.info("AsyncManager shut down completed")


def run_sync_in_thread(async_manager: AsyncManager):
    """Decorator to run synchronous functions in thread pool."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await async_manager.run_in_thread(func, *args, **kwargs)
        return wrapper
    return decorator


def with_timeout(timeout: float):
    """Decorator to add timeout to async functions."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except asyncio.TimeoutError:
                logging.warning(f"{func.__name__} timed out after {timeout} seconds")
                raise
        return wrapper
    return decorator