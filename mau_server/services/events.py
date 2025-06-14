"""Вспомогательный модуль отправки игровых событий."""

import asyncio

from fastapi import WebSocket
from loguru import logger
from mau.enums import GameEvents
from mau.events import BaseEventHandler, Event
from pydantic import BaseModel

from mau_server.schemes.game import GameData, PlayerData, dump_game, dump_player


class EventData(BaseModel):
    """Определённое игровое события на сервере.

    - event_type: Тип произошедшего события.
    - from_player: Кто совершил данное событие.
    - data: Некоторая полезная информация.
    - context: Текущий игровой контекст.
    """

    event: GameEvents
    player: PlayerData
    data: str
    game: GameData


class WebSocketEventHandler(BaseEventHandler):
    """Отправляет события клиентам через веб сокеты."""

    def __init__(self) -> None:
        self.clients: dict[str, list[WebSocket]] = {}
        self.event_loop = asyncio.get_running_loop()

    async def connect(self, room_id: str, websocket: WebSocket) -> None:
        """Добавляет нового клиента."""
        await websocket.accept()
        if room_id not in self.clients:
            self.clients[room_id] = []
        self.clients[room_id].append(websocket)
        logger.info("New client, now {} clients", len(self.clients))

    def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        """Отключает клиента от комнаты."""
        if websocket in self.clients[room_id]:
            self.clients[room_id].remove(websocket)
        logger.info("Client disconnect, now {} clients", len(self.clients))

    def push(self, event: Event) -> None:
        """Отправляет событие клиентам."""
        event_data = EventData(
            event=event.event_type,
            player=dump_player(event.player),
            data=event.data,
            game=dump_game(event.game),
        )

        for connection in self.clients.get(event.game.room_id, []):
            try:
                self.event_loop.create_task(
                    connection.send_text(event_data.model_dump_json())
                )
            except Exception as e:
                logger.error(e)
