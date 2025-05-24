"""Схемы, используемые во время игры."""

from dataclasses import dataclass
from datetime import datetime

from mau.deck.card import MauCard
from mau.deck.deck import Deck
from mau.enums import CardColor, GameState
from mau.game.game import MauGame
from mau.game.player import Player, SortedCards
from pydantic import BaseModel

from mau_server.models import Room, User
from mau_server.schemes.roomlist import RoomMode


class CardData(BaseModel):
    """Сохраняет информацию о карте.

    Информация о картах является исчерпывающей.
    - цвет карты.
    - Тип карты.
    - Числовое значение.
    - Стоимость карты.
    """

    color: CardColor
    behavior: str
    value: int
    cost: int


class CardDeckData(BaseModel):
    """Информация о колоде карт.

    Предоставляет статистику сколько карт доступно и сколько уже
    использовано,
    """

    top: CardData | None
    cards: int
    used: int


class CoverCardsData(BaseModel):
    """Описание карт в руке игрока."""

    cover: list[CardData]
    uncover: list[CardData]


class PlayerData(BaseModel):
    """Информация об игроке.

    Используется при отображении всех игроков.
    Чтобы получить подробную информацию о пользователе. лучше
    воспользоваться методом получения пользователя из бд.

    - id пользователя.
    - Сколько карт у него вв руке.
    - Скольку раз стрелял из револьвера.

    также вместо количества карт может быть полное их описание.
    Только в том случае, если это игрок, запрашивающий данные о себе.
    """

    user_id: str
    name: str
    hand: int | CoverCardsData
    shotgun_current: int


class GameData(BaseModel):
    """Полная информация о состоянии игры."""

    # Информация о настройках комнаты
    room_id: str
    rules: list[RoomMode]
    owner_id: str
    game_started: datetime
    turn_started: datetime

    # Информация об игроках комнаты
    players: list[PlayerData]
    winners: list[PlayerData]
    losers: list[PlayerData]
    current_player: int

    # Состояние комнаты
    deck: CardDeckData
    reverse: bool
    bluff_player: tuple[PlayerData, bool] | None
    take_counter: int
    shotgun_current: int
    state: GameState


@dataclass(slots=True)
class GameContext:
    """Игровой контекст."""

    user: User
    room: Room
    game: MauGame | None
    player: Player | None


class ContextData(BaseModel):
    """Отправляемая схема контекста."""

    game: GameData | None
    player: PlayerData | None


# конвертация моделей
# ===================


def dump_card(card: MauCard) -> CardData:
    """Преобразуем экземпляр карты в её схему."""
    return CardData(
        color=card.color,
        behavior=card.behavior.name,
        value=card.value,
        cost=card.cost,
    )


def dump_deck(deck: Deck) -> CardDeckData:
    """Преобразует колоду карт в схему, оставляя только количество карт."""
    return CardDeckData(
        top=dump_card(deck._top) if deck._top else None,
        cards=len(deck.cards),
        used=len(deck.used_cards),
    )


def dump_cover_cards(player_hand: SortedCards) -> CoverCardsData:
    """Перегоняет сортированные карты в схему."""
    return CoverCardsData(
        cover=[dump_card(card) for card in player_hand.cover],
        uncover=[dump_card(card) for card in player_hand.uncover],
    )


def dump_player(player: Player, show_cards: bool | None = False) -> PlayerData:
    """Преобразует игрока в схему.

    Пропускает поле `shotgun_lose`, чтобы не подсматривали.
    Также если `show_cards` не установлен, отобразит только количество
    карт.
    """
    return PlayerData(
        user_id=player.user_id,
        name=player.name,
        hand=dump_cover_cards(player.cover_cards())
        if show_cards
        else len(player.hand),
        shotgun_current=player.shotgun.cur,
    )


def dump_rule(name: str, status: bool) -> RoomMode:
    """Преобразует игровое правило в схему."""
    return RoomMode(name=name, status=status)


def dump_bluff(
    bluff: tuple[Player, bool] | None,
) -> tuple[PlayerData, bool] | None:
    """Запаковывает флаг блефа."""
    if bluff is None:
        return None
    return (dump_player(bluff[0]), bluff[1])


def dump_game(game: MauGame) -> GameData:
    """Преобразует игру в схему."""
    return GameData(
        room_id=game.room_id,
        rules=[
            dump_rule(name, status) for name, status in game.rules.iter_rules()
        ],
        owner_id=game.owner.user_id,
        game_started=game.game_start,
        turn_started=game.turn_start,
        players=[
            dump_player(player) for player in game.pm.iter(game.pm._players)
        ],
        winners=[
            dump_player(player) for player in game.pm.iter(game.pm.winners)
        ],
        losers=[dump_player(player) for player in game.pm.iter(game.pm.losers)],
        current_player=game.pm._cp,
        deck=dump_deck(game.deck),
        reverse=game.reverse,
        take_counter=game.take_counter,
        shotgun_current=game.shotgun.cur,
        state=game.state,
        bluff_player=dump_bluff(game.bluff_player),
    )


async def dump_context(ctx: GameContext) -> ContextData:
    """Преобразует игровой контекст в схему."""
    return ContextData(
        game=None if ctx.game is None else dump_game(ctx.game),
        player=None
        if ctx.player is None
        else dump_player(ctx.player, show_cards=True),
    )
