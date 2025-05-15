"""Получает игровой контекст."""

from fastapi import Depends, HTTPException

from mau_server.config import sm, stm
from mau_server.models import Room, User
from mau_server.schemes.game import GameContext


async def game_context(
    user: User = Depends(stm.read_token),
) -> GameContext:
    """Получает игровой контекст пользователя.

    Контекст хранит в себе исчерпывающую информацию о состоянии игры.
    Актуальная информация об активном игроке.
    В какой комнате сейчас находится игрок.
    Если игрок не находится в комнате, вернётся ошибка.
    Также включат информацию об игре внутри комнаты и пользователя
    как игрока.
    """
    room = (
        await Room.filter(players=user)
        .exclude(status="ended")
        .get_or_none()
        .prefetch_related("players")
    )
    if room is None:
        raise HTTPException(404, "user not in room")

    game = sm.room(str(room.id))
    if game is not None:
        player = sm.player(user.username)
    else:
        player = None

    return GameContext(
        user=user,
        room=room,
        game=game,
        player=player,
    )
