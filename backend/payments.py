"""Payment configuration helpers for paid valuation checkout."""
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckoutConfig:
    price_cents: int
    currency: str
    success_url: str
    cancel_url: str


@dataclass(frozen=True)
class CheckoutSession:
    session_id: str
    url: str


def checkout_config() -> CheckoutConfig:
    return CheckoutConfig(
        price_cents=int(os.getenv("ACCOUNTIQ_VALUATION_PRICE_CENTS", "49500")),
        currency=os.getenv("ACCOUNTIQ_CURRENCY", "nzd").lower(),
        success_url=os.getenv(
            "ACCOUNTIQ_PAYMENT_SUCCESS_URL",
            "http://localhost:3000/wizard?payment=success",
        ),
        cancel_url=os.getenv(
            "ACCOUNTIQ_PAYMENT_CANCEL_URL",
            "http://localhost:3000/wizard?payment=cancelled",
        ),
    )


def stripe_enabled() -> bool:
    return bool(os.getenv("STRIPE_SECRET_KEY", "").strip())


def create_checkout_session(
    *,
    report_id: int,
    purchase_id: int,
    user_email: str,
    config: CheckoutConfig,
) -> CheckoutSession:
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured")

    import stripe

    stripe.api_key = secret_key
    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=user_email,
        line_items=[
            {
                "price_data": {
                    "currency": config.currency,
                    "unit_amount": config.price_cents,
                    "product_data": {
                        "name": "AccountIQ Valuation Advisory",
                    },
                },
                "quantity": 1,
            }
        ],
        success_url=config.success_url,
        cancel_url=config.cancel_url,
        metadata={
            "report_id": str(report_id),
            "purchase_id": str(purchase_id),
            "report_type": "valuation_advisory",
        },
    )
    session_id = _stripe_value(session, "id")
    url = _stripe_value(session, "url")
    if not session_id or not url:
        raise RuntimeError("Stripe Checkout session response was missing id or url")
    return CheckoutSession(session_id=session_id, url=url)


def construct_webhook_event(payload: bytes, signature_header: str | None) -> Any:
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not webhook_secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured")
    if not signature_header:
        raise ValueError("Missing Stripe signature header")

    import stripe

    return stripe.Webhook.construct_event(
        payload=payload,
        sig_header=signature_header,
        secret=webhook_secret,
    )


def _stripe_value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
