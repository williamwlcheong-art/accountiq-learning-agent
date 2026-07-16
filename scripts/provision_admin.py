#!/usr/bin/env python3
"""Explicitly grant admin access to one existing AccountIQ user."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from admin_provisioning import provision_admin
from db import DB_PATH


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Grant admin access to an existing AccountIQ user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument(
        "--confirm-admin-provisioning",
        action="store_true",
        help="confirm this intentional privilege change",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.confirm_admin_provisioning:
        print("Refusing without --confirm-admin-provisioning")
        return 1
    try:
        provision_admin(args.database or DB_PATH, args.email)
    except Exception as exc:
        print(f"Admin provisioning failed: {exc}")
        return 1
    print(f"Admin access granted to {args.email.strip().lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
