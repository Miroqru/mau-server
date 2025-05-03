"""Главный файл.

Настраивает сервер и запускает его.
"""

from fastapi import FastAPI

app = FastAPI(
    # lifespan=lifespan,
    # debug=config.debug,
    title="mau:server",
    version="v2.0",
    root_path="/api",
)