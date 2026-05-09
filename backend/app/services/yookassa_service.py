import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import httpx

from app.core.config import settings

YOOKASSA_API_URL = "https://api.yookassa.ru/v3/payments"


def _is_configured() -> bool:
    return bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY)


async def create_payment(amount_rub: int, user_id: int, credits: int) -> dict:
    if not _is_configured():
        fake_id = f"test_{uuid.uuid4().hex}"
        return {
            "yookassa_id": fake_id,
            "confirmation_url": f"{settings.BASE_URL}/api/v1/billing/payment/stub?id={fake_id}",
            "test_mode": True,
        }

    idempotency_key = str(uuid.uuid4())
    payload = {
        "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "return_url": settings.YOOKASSA_RETURN_URL,
        },
        "capture": True,
        "description": f"DrugCheck: {credits} кредитов для пользователя #{user_id}",
        "metadata": {"user_id": str(user_id), "credits": str(credits)},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            YOOKASSA_API_URL,
            json=payload,
            auth=(settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY),
            headers={"Idempotence-Key": idempotency_key},
        )
        resp.raise_for_status()
        data = resp.json()

    return {
        "yookassa_id": data["id"],
        "confirmation_url": data["confirmation"]["confirmation_url"],
        "test_mode": False,
    }


def verify_webhook_signature(body: bytes, signature_header: str) -> bool:
    if not _is_configured():
        return True

    expected = hmac.new(
        settings.YOOKASSA_SECRET_KEY.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def parse_webhook(body: bytes) -> dict:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None

    if data.get("event") != "payment.succeeded":
        return None

    payment_obj = data.get("object", {})
    metadata = payment_obj.get("metadata", {})
    user_id = metadata.get("user_id")
    credits = metadata.get("credits")

    if not user_id or not credits:
        return None

    return {
        "event": data["event"],
        "yookassa_id": payment_obj.get("id"),
        "status": payment_obj.get("status"),
        "user_id": int(user_id),
        "credits": Decimal(credits),
    }
