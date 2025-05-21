"""Главный файл.

Настраивает сервер и запускает его.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from tortoise import generate_config
from tortoise.contrib.fastapi import RegisterTortoise

from mau_server.config import config
from mau_server.routers import ROUTERS


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Жизненный цикл базы данных.

    Если это тестовая сессия, то создаёт базу данных в оперативной
    памяти.
    Иначе же просто  к базе данных postgres, на всё время
    работы сервера.
    """
    async with RegisterTortoise(
        app=app,
        config=generate_config(
            str(config.db_url),
            app_modules={"models": ["mau_server.models"]},
            testing=config.debug,
            connection_label="models",
        ),
        generate_schemas=True,
        add_exception_handlers=True,
    ):
        # db connected
        yield
        # app teardown


app = FastAPI(
    lifespan=lifespan,
    debug=config.debug,
    title="mau:server",
    version="v2.0",
    root_path="/api",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Подключает сторонние маршруты
for router in ROUTERS:
    app.include_router(router)
    logger.info("Include router: {}", router.prefix)
