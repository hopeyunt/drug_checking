from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.config import settings
from app.models.drug import Drug


GRLS_SEARCH_URL = "https://grls.rosminzdrav.ru/api/v1/Registration/GetRegistrationList"


async def search_drugs_local(db: AsyncSession, query: str, limit: int = 10) -> list[Drug]:
    result = await db.execute(
        select(Drug)
        .where(
            func.lower(Drug.trade_name).contains(query.lower()) |
            func.lower(Drug.inn).contains(query.lower())
        )
        .limit(limit)
    )
    return result.scalars().all()


async def get_drug_by_name(db: AsyncSession, name: str) -> Optional[Drug]:
    result = await db.execute(
        select(Drug).where(
            or_(
                func.lower(Drug.trade_name) == name.lower(),
                func.lower(Drug.inn) == name.lower(),
            )
        )
    )
    return result.scalar_one_or_none()


async def fetch_from_grls(trade_name: str) -> Optional[dict]:
    params = {
        "RegistrationNumber": "",
        "MnnName": "",
        "TradeName": trade_name,
        "PageSize": 1,
        "PageNumber": 1,
    }
    headers = {}
    if settings.GRLS_API_KEY:
        headers["Authorization"] = f"Bearer {settings.GRLS_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(GRLS_SEARCH_URL, params=params, headers=headers)
            if resp.status_code != 200:
                return None
            data = resp.json()
            items = data.get("data", [])
            if not items:
                return None
            item = items[0]
            return {
                "trade_name": item.get("tradeName", trade_name),
                "inn": item.get("mnnName", ""),
                "atc_code": item.get("atcCode", ""),
            }
    except (httpx.RequestError, Exception):
        return None


async def resolve_drug(db: AsyncSession, name: str) -> Optional[Drug]:
    drug = await get_drug_by_name(db, name)
    if drug:
        return drug

    # TODO: добавить кэш чтобы не ходить в ГРЛС каждый раз
    grls_data = await fetch_from_grls(name)
    if not grls_data or not grls_data.get("inn"):
        return None

    drug = Drug(
        trade_name=grls_data["trade_name"],
        inn=grls_data["inn"],
        atc_code=grls_data.get("atc_code"),
        source="grls",
    )
    db.add(drug)
    await db.flush()
    return drug
