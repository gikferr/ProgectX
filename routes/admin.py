from fastapi import APIRouter, Depends, HTTPException
import aiosqlite
import secrets

from auth import validate_init_data
from db import get_db

router = APIRouter(prefix="/api/admin")


async def require_admin(user_id: int, db):
    c = await db.execute(
        "SELECT is_organizer_allowed FROM users WHERE user_id = ?", (user_id,)
    )
    row = await c.fetchone()
    if not row or not row["is_organizer_allowed"]:
        raise HTTPException(403, "Нет прав")


@router.post("/generate-code")
async def generate_code(req: dict, db: aiosqlite.Connection = Depends(get_db)):
    init_data = req.get("initData")
    user = validate_init_data(init_data)
    user_id = user["id"]
    await require_admin(user_id, db)

    code = "ORG-" + secrets.token_hex(4).upper()
    await db.execute(
        "INSERT INTO organizer_codes (code, created_by) VALUES (?, ?)",
        (code, user_id)
    )
    await db.commit()
    return {"ok": True, "code": code}