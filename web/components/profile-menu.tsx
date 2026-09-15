"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";

import { LogoutButton } from "@/components/auth/logout-button";

type ProfileMenuProps = {
  email: string;
  isAdmin: boolean;
};

export function ProfileMenu({ email, isAdmin }: ProfileMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const initial = email.trim().charAt(0).toUpperCase() || "?";

  useEffect(() => {
    if (!open) return;

    // Move focus into the menu so keyboard users land on the first action.
    const first = menuRef.current?.querySelector<HTMLElement>("a, button");
    first?.focus();

    function onPointerDown(event: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    }
    function onFocusOut(event: FocusEvent) {
      const next = event.relatedTarget as Node | null;
      if (next && rootRef.current && !rootRef.current.contains(next)) setOpen(false);
    }

    const root = rootRef.current;
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    root?.addEventListener("focusout", onFocusOut);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
      root?.removeEventListener("focusout", onFocusOut);
    };
  }, [open]);

  return (
    <div className="portal-profile" ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className="portal-avatar"
        aria-label="Account menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden="true">{initial}</span>
      </button>
      {open ? (
        <div className="portal-menu" id={menuId} ref={menuRef} role="group" aria-label="Account">
          <p className="portal-menu-email">{email}</p>
          <Link href="/account" onClick={() => setOpen(false)}>
            Account
          </Link>
          {isAdmin ? (
            <Link href="/admin" onClick={() => setOpen(false)}>
              Admin
            </Link>
          ) : null}
          <LogoutButton className="portal-menu-button" />
        </div>
      ) : null}
    </div>
  );
}
