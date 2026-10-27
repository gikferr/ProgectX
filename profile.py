from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import aiosqlite

from auth import validate_init_data
from db import get_db

router = APIRouter(prefix="/api")


class InitDataReq(BaseModel):
    initData: str


class ProfileReq(BaseModel):
    initData: str
    fio: Optional[str] = None
    alcohol: Optional[str] = None
    food_pref: Optional[str] = None


@router.post("/auth")
async def auth(req: InitDataReq, db: aiosqlite.Connection = Depends(get_db)):
    user = validate_init_data(req.initData)
    user_id = user["id"]

    cursor = await db.execute(
        "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
    )
    existing = await cursor.fetchone()

    if not existing:
        await db.execute(
            """INSERT INTO users (user_id, username, first_name, via_bot)
               VALUES (?, ?, ?, 0)""",
            (user_id, user.get("username", ""), user.get("first_name", ""))
        )
        await db.commit()

    cursor = await db.execute(
        "SELECT is_organizer_allowed FROM users WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()

    return {
        "ok": True,
        "user_id": user_id,
        "is_new": not existing,
        "is_organizer_allowed": bool(row["is_organizer_allowed"]) if row else False,
    }


@router.post("/profile")
async def save_profile(req: ProfileReq, db: aiosqlite.Connection = Depends(get_db)):
    user = validate_init_data(req.initData)
    user_id = user["id"]

    await db.execute(
        "UPDATE users SET first_name = ?, username = ? WHERE user_id = ?",
        (user.get("first_name", ""), user.get("username", ""), user_id)
    )
    await db.commit()
    return {"ok": True}


@router.post("/become-organizer")
async def become_organizer(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    code = (req.get("code") or "").strip()
    if not code:
        raise HTTPException(400, "No code")

    user = validate_init_data(init_data)
    user_id = user["id"]

    cursor = await db.execute(
        "SELECT code, used_by FROM organizer_codes WHERE code = ?", (code,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(400, "Код не найден")
    if row["used_by"] is not None:
        raise HTTPException(400, "Код уже использован")

    await db.execute(
        "UPDATE organizer_codes SET used_by = ?, used_at = CURRENT_TIMESTAMP WHERE code = ?",
        (user_id, code)
    )
    await db.execute(
        "UPDATE users SET is_organizer_allowed = 1 WHERE user_id = ?", (user_id,)
    )
    await db.commit()
    return {"ok": True}