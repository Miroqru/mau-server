"""Обработка игры."""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from loguru import logger
from mau.deck.behavior import TakeBehavior, WildTakeBehavior
from mau.deck.card import MauCard
from mau.enums import CardColor, GameState
from mau.game.player import BaseUser

from mau_server.config import sm
from mau_server.models import Game, User
from mau_server.schemes.game import ContextData, GameContext, dump_context
from mau_server.services.game_context import game_context

router = APIRouter(prefix="/game", tags=["games"])


async def save_game(ctx: GameContext) -> None:
    """Записывает игру в базу данных."""
    if ctx.game is None:
        return

    game = Game(
        create_time=ctx.game.game_start,
        owner=await User.get_or_none(username=ctx.game.owner.user_id),
        room=ctx.room,
    )

    for pl in ctx.game.pm.iter(ctx.game.pm.winners):
        winner = await User.get_or_none(username=pl.user_id)
        if winner is not None:
            await game.winners.add(winner)
        else:
            logger.error("Not found winner {}", pl.user_id)

    for pl in ctx.game.pm.iter(ctx.game.pm.losers):
        loser = await User.get_or_none(username=pl.user_id)
        if loser is not None:
            await game.losers.add(loser)
        else:
            logger.error("Not found loser {}", pl.user_id)

    await game.save()
    sm.remove(str(ctx.room.id))
    ctx.game = None
    ctx.player = None


# Player routers
# ==============


@router.post("/join/")
async def join_player_to_game(
    ctx: GameContext = Depends(game_context),
) -> ContextData:
    """Добавляет активного пользователя в комнату.

    Под пользователем имеется ввиду активная учётная запись.
    Под комнатой предполагается текущая активная комната пользователя.
    """
    if ctx.game is None:
        raise HTTPException(404, "Room game not started to join")
    if ctx.player is not None:
        raise HTTPException(409, "Player already join to room")

    ctx.game.join_player(
        BaseUser(ctx.user.id, ctx.user.name, ctx.user.username)
    )
    return await dump_context(ctx)


@router.post("/leave")
async def leave_player_from_room(
    ctx: GameContext = Depends(game_context),
) -> ContextData:
    """Выходит из активной комнаты.

    Предполагается что прямо сейчас пользователь есть в игре.
    """
    if ctx.player is None or ctx.game is None:
        raise HTTPException(404, "Room or player not found to leave from game")

    ctx.game.leave_player(ctx.player)
    if not ctx.game.started:
        await save_game(ctx)

    return await dump_context(ctx)


# Session Routers
# ===============


@router.get("/")
async def get_active_game(
    ctx: GameContext = Depends(game_context),
) -> ContextData:
    """Получает игровой контекст.

    Включает в себя данные о пользователе, комнате, текущей игре
    и игроке.
    может быть полезно чтобы обновить полную информацию о контексте.
    """
    return await dump_context(ctx)


@router.post("/start")
async def start_room_game(
    ctx: GameContext = Depends(game_context),
) -> ContextData:
    """Начинает новую игру в комнате.

    Включает в себя как процесс создания комнаты, так и начало игры.
    """
    if ctx.game is None:
        raise HTTPException(404, "Game not found")

    if ctx.game.started:
        raise HTTPException(
            409, "Game already created, end game before create new"
        )
    elif ctx.user != ctx.room.owner:
        raise HTTPException(401, "You are not a room owner to create new game")

    # Сразу добавляем всех игроков из комнаты
    for user in ctx.room.players:
        if user.id == ctx.user.id:
            continue

        ctx.game.join_player(BaseUser(user.username, user.name))

    ctx.game.start()
    return await dump_context(ctx)


@router.post("/end")
async def end_room_game(
    ctx: GameContext = Depends(game_context),
) -> ContextData:
    """Принудительно завершает игру в комнате.

    Редко используемая опция, тем не менее имеет место быть.
    """
    if ctx.game is None:
        raise HTTPException(404, "No active game to end")
    elif ctx.user != ctx.room.owner:
        raise HTTPException(401, "You are not a room owner to end this game")

    await save_game(ctx)
    return await dump_context(ctx)


@router.post("/kick/{user_id}")
async def kick_player(
    user_id: str, ctx: GameContext = Depends(game_context)
) -> ContextData:
    """Исключает пользователя из игры.

    После пользователь сможет вернутся только как наблюдатель.
    """
    if ctx.game is None:
        raise HTTPException(404, "No active game to kick player")
    elif ctx.user != ctx.room.owner:
        raise HTTPException(401, "You are not a room owner to kik player")

    kick_player = sm.player(user_id)
    if kick_player is None:
        raise HTTPException(404, "Kick player not in game")

    ctx.game.leave_player(kick_player)
    if not ctx.game.started:
        await save_game(ctx)
    return await dump_context(ctx)


@router.post("/skip")
async def skip_player(ctx: GameContext = Depends(game_context)) -> ContextData:
    """Пропускает игрока.

    Если к примеру игрок зазевался и не даёт продолжать игру.
    """
    if ctx.game is None:
        raise HTTPException(404, "No active game to skip player")

    ctx.game.take_counter += 1
    ctx.game.player.take_cards()
    ctx.game.next_turn()
    return await dump_context(ctx)


# Turn routers
# ============


@router.post("/next")
async def next_turn(ctx: GameContext = Depends(game_context)) -> ContextData:
    """Передает ход дальше.

    Есть такая вероятность что пользователи могут шалить, пропуская свой ход.
    Но поскольку цель сбросить свои карты, это мало вероятно.
    """
    if ctx.game is None:
        raise HTTPException(404, "No active game in room")
    elif ctx.player is None:
        raise HTTPException(404, "You are not a game player")
    elif ctx.player != ctx.game.player:
        raise HTTPException(404, "It's not your turn to skip it.")

    ctx.game.next_turn()
    return await dump_context(ctx)


@router.post("/take")
async def take_cards(ctx: GameContext = Depends(game_context)) -> ContextData:
    """Взятие карт.

    Игрок берёт количество карт, равное игровому счётчику.
    При режиме с револьвером будет предложено выстрелить или взять
    карты.

    Чтобы взять карты и отказаться от выстрела - `/shotgun/take`.
    """
    if ctx.game is None:
        raise HTTPException(404, "No active game in room")
    elif ctx.player is None:
        raise HTTPException(404, "You are not a game player")

    ctx.player.call_take_cards()
    return await dump_context(ctx)


@router.post("/shotgun/take")
async def shotgun_take_cards(
    ctx: GameContext = Depends(game_context),
) -> ContextData:
    """Взять карты, чтобы не стрелять.

    В случае, когда игрок решил что лучше взять карты, чем рисковать
    своей игрой.
    """
    if ctx.game is None:
        raise HTTPException(404, "No active game in room")
    elif ctx.player is None:
        raise HTTPException(404, "You are not a game player")

    ctx.player.take_cards()
    if (
        isinstance(ctx.game.deck.top.behavior, TakeBehavior | WildTakeBehavior)
        and ctx.game.take_counter
    ):
        ctx.game.next_turn()
    return await dump_context(ctx)


@router.post("/shotgun/shot")
async def shotgun_shot(ctx: GameContext = Depends(game_context)) -> ContextData:
    """Когда решил стрелять, лишь бы не брать карты."""
    if ctx.game is None:
        raise HTTPException(404, "No active game in room")
    elif ctx.player is None:
        raise HTTPException(404, "You are not a game player")

    res = ctx.player.shotgun.shot()
    if res:
        ctx.game.leave_player(ctx.player)

    else:
        ctx.game.take_counter = round(ctx.game.take_counter * 1.5)
        if ctx.game.player != ctx.player:
            ctx.game.pm.set_cp(ctx.player)
        ctx.game.next_turn()
        ctx.game.state = GameState.SHOTGUN

    if not ctx.game.started:
        await save_game(ctx)
    return await dump_context(ctx)


@router.post("/bluff")
async def bluff_player(ctx: GameContext = Depends(game_context)) -> ContextData:
    """Проверка игрока на честность."""
    if ctx.game is None:
        raise HTTPException(404, "No active game in room")
    elif ctx.player is None:
        raise HTTPException(404, "You are not a game player")

    ctx.player.call_bluff()
    return await dump_context(ctx)


@router.post("/color/{color}")
async def select_card_color(
    color: CardColor, ctx: GameContext = Depends(game_context)
) -> ContextData:
    """Выбирает цвет для карты выбор цвета или +4."""
    if ctx.game is None:
        raise HTTPException(404, "No active game in room")
    elif ctx.player is None:
        raise HTTPException(404, "You are not a game player")

    ctx.game.choose_color(color)
    return await dump_context(ctx)


@router.post("/player/{user_id}")
async def select_player(
    user_id: str, ctx: GameContext = Depends(game_context)
) -> ContextData:
    """Выбирает игрока, с кем можно обменяться картами."""
    if ctx.game is None:
        raise HTTPException(404, "No active game in room")
    elif ctx.player is None:
        raise HTTPException(404, "You are not a game player")

    other_player = sm.player(user_id)
    if other_player is None:
        raise HTTPException(404, "Other player is None")

    if ctx.game.state == GameState.TWIST_HAND:
        ctx.player.twist_hand(other_player)

    return await dump_context(ctx)


@router.post("/card/")
async def push_card_from_hand(
    card: MauCard | None = Depends(MauCard.unpack),
    ctx: GameContext = Depends(game_context),
) -> ContextData:
    """Разыгрывает карту из руки игрока."""
    if card is None:
        raise HTTPException(404, "Card is None")
    if ctx.game is None:
        raise HTTPException(404, "No active game in room")
    elif ctx.player is None:
        raise HTTPException(404, "You are not a game player")

    ctx.game.process_turn(card, ctx.player)

    if not ctx.game.started:
        await save_game(ctx)

    return await dump_context(ctx)
