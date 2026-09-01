"use client";

import { useRouter } from "next/navigation";

type LogoutButtonProps = {
  className?: string;
};

export function LogoutButton({ className = "button button-secondary" }: LogoutButtonProps) {
  const router = useRouter();

  async function logout() {
    await fetch("/api/backend/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    router.replace("/login");
    router.refresh();
  }

  return (
    <button type="button" className={className} onClick={logout}>
      Sign out
    </button>
  );
}
