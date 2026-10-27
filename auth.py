import hmac
import hashlib
import json
import os
from urllib.parse import parse_qsl, unquote
from fastapi import HTTPException

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

def validate_init_data(init_data: str) -> dict:
    if not init_data:
        raise HTTPException(401, "Empty initData")

    params = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = params.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "No hash in initData")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if calculated_hash != received_hash:
        raise HTTPException(401, "Invalid initData signature")

    try:
        user = json.loads(unquote(params["user"]))
    except (KeyError, json.JSONDecodeError):
        raise HTTPException(401, "No user in initData")

    return user