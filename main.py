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
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

load_dotenv(override=True)

from tutor.bot import run_bot  # noqa: E402  (needs env loaded first)
from tutor.slides import DECK  # noqa: E402

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7860"))

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
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
