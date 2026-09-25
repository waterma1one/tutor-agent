#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import asyncio
import os
import sys

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, status
from loguru import logger

load_dotenv(override=True)

from tutor.bot import run_bot  # noqa: E402  (needs env loaded first)
from tutor.slides import DECK  # noqa: E402

# Each class spends OpenAI credit, so the server listens on this machine only
# unless HOST says otherwise.
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "7860"))

# The frontend reaches /connect and /slides through the Vite proxy, so plain
# HTTP needs no CORS. The websocket goes direct, and browsers let any page open
# a websocket to localhost, so it only accepts pages from these origins.
DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def allowed_origins() -> set[str]:
    raw = os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS)
    return {origin.strip() for origin in raw.split(",") if origin.strip()}


app = FastAPI()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    if origin not in allowed_origins():
        logger.warning(f"Refused websocket from origin {origin!r}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    try:
        await run_bot(websocket)
    except Exception:
        logger.exception("Session ended with an error")


@app.post("/connect")
async def bot_connect() -> dict:
    return {"ws_url": f"ws://localhost:{PORT}/ws"}


@app.get("/slides")
async def slides() -> list[dict]:
    return [slide.to_dict() for slide in DECK]


def check_env() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY is not set. Add it to .env (see README).")
        sys.exit(1)


async def main():
    check_env()
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT))
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
