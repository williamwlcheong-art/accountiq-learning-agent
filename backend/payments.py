"""Payment configuration helpers for paid valuation checkout."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckoutConfig:
    price_cents: int
    currency: str
    success_url: str
    cancel_url: str


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
