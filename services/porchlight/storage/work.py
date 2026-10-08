"""Finish native database/file work before releasing the process profile lock."""

import asyncio
from collections.abc import Callable


async def local_work[T](operation: Callable[[], T]) -> T:
    worker = asyncio.create_task(asyncio.to_thread(operation))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        await worker
        raise
