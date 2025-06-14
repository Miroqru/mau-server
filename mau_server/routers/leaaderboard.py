"""Таблица лидеров."""

from enum import StrEnum

from fastapi import APIRouter, HTTPException

from mau_server.models import User
from mau_server.schemes.db import UserData

router = APIRouter(prefix="/leaderboard", tags=["rating"])


class CategoryEnum(StrEnum):
    """Все используемые категории в таблице лидеров."""

    gems = "gems"
    play_count = "games"
    win_count = "wins"
    cards_count = "cards"


@router.get("/{username}/{category}")
async def get_my_leaderboard_index(
    username: str, category: CategoryEnum
) -> int:
    """Получает таблицу лидеров из базы данных."""
    user = await User.get_or_none(username=username)
    if user is None:
        raise HTTPException(404, "User not found")
    position = (await User.filter(gems__gt=user.gems).count()) + 1
    return position


@router.get("/{category}")
async def get_leaderboard_by_category(category: CategoryEnum) -> list[UserData]:
    """Получает таблицу лидеров из базы данных."""
    return await UserData.from_queryset(
        User.all().order_by("-" + category.name).limit(100)
    )
