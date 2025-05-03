"""Общие настройки сервера.

Здесь будут храниться необходимые для запуска приложения настройки.
Такие как url подключения к базе данных или секретные ключи для токенов.
Данные настройки будут храниться как переменные окружения в .env файле.
"""

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings
from redis.asyncio.client import Redis

# from mauserve.services.events import WebSocketEventHandler
# from mauserve.services.token import SimpleTokenManager


class Config(BaseSettings):
    """Хранит все настройки сервера.

    Args:
        jwt_key: Ключ для генерации токенов.
        db_url: Путь к основной базе данных для TortoiseORM.
        test_db_url: Путь к тестовой базе данных для TortoiseORM.
        debug: Отладочный режим работы без сохранения данных.

    """

    jwt_key: str
    db_url: PostgresDsn
    redis_url: str
    debug: bool


# Создаём экземпляр настроек
config = Config(_env_file=".env")
redis = Redis.from_url(
    config.redis_url, encoding="utf-8", decode_responses=True
)

# stm = SimpleTokenManager(config.jwt_key, ttl=86_400)
# sm: SessionManager = SessionManager(event_handler=WebSocketEventHandler())
