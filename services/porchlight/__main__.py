from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from uuid import UUID, uuid4

import uvicorn

from porchlight.app import create_app
from porchlight.config import Config


async def serve(launch_id: UUID | None = None) -> None:
    config = Config()
    instance = str(launch_id or uuid4())
    config.data_root.mkdir(parents=True, exist_ok=True)
    stop_file = config.data_root / f"{instance}.stop"
    state_file = config.data_root / "process.json"
    app = create_app(config)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=config.host,
            port=config.port,
            workers=1,
            access_log=False,
            proxy_headers=False,
            log_level="warning",
        )
    )

    async def stop_watcher() -> None:
        while not server.started:
            if server.should_exit or stop_file.exists():
                server.should_exit = True
                if hasattr(app.state, "changes"):
                    app.state.changes.closing = True
                return
            await asyncio.sleep(0.1)
        # This file describes only a successfully started, locked Porchlight process.
        state_file.write_text(
            json.dumps({"pid": os.getpid(), "instance": instance, "port": config.port}),
            encoding="utf-8",
        )
        print(f"Porchlight: http://127.0.0.1:{config.port}", flush=True)
        print(f"Local data: {config.data_root}", flush=True)
        while not server.should_exit:
            if stop_file.exists():
                server.should_exit = True
                break
            await asyncio.sleep(0.3)
        if hasattr(app.state, "changes"):
            app.state.changes.closing = True

    watcher = asyncio.create_task(stop_watcher())
    try:
        await server.serve()
    finally:
        watcher.cancel()
        if state_file.exists():
            try:
                if json.loads(state_file.read_text(encoding="utf-8")).get("instance") == instance:
                    state_file.unlink()
            except (OSError, ValueError):
                pass
        stop_file.unlink(missing_ok=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Run the local Porchlight server.")
    parser.add_argument("--launch-id", type=UUID, default=None)
    arguments = parser.parse_args()
    asyncio.run(serve(arguments.launch_id))
