"""Схема списка комнат.

Используются при взаимодействии с комнатами
"""

from uuid import UUID

from pydantic import BaseModel


class RoomMode(BaseModel):
    """Режим игры, изменяющий правила."""

    name: str | None
    status: bool


class RoomModeIn(BaseModel):
    """Настройка списка активных режимов."""

    rules: list[str]


class RoomDelete(BaseModel):
    """Данные при принудительном удалении комнаты."""

    rom_id: UUID


class RoomDataIn(BaseModel):
    """Изменяемые данные комнаты."""

    name: str | None = None
    private: bool | None = None
    room_password: str | None = None
    gems: int | None = None
    max_players: int | None = None
    min_players: int | None = None
