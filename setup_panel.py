#!/usr/bin/env python3
"""Interactive setup for web-helper.

Prompts for initial superadmin and 3x-ui panel config, then submits to running app.
"""
from getpass import getpass
import sys

import httpx


def ask(prompt: str, default: str = "", required: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"{prompt}{suffix}: ").strip()
        if val:
            return val
        if default:
            return default
        if not required:
            return ""
        print("This field is required.")


def main() -> int:
    print("=== web-helper setup ===")
    base = ask("App URL", "http://127.0.0.1:38291").rstrip("/")

    admin_user = ask("Superadmin username")
    admin_pass = getpass("Superadmin password: ")
    if not admin_pass:
        print("Superadmin password is required.")
        return 1

    panel_url = ask("3x-ui panel URL (e.g. http://127.0.0.1:2053)")
    panel_path = ask("3x-ui panel web base path (blank for none)", required=False)
    panel_user = ask("3x-ui panel username")
    panel_pass = getpass("3x-ui panel password: ")
    if not panel_pass:
        print("3x-ui panel password is required.")
        return 1

    try:
        with httpx.Client(follow_redirects=False, timeout=20) as client:
            boot = client.post(f"{base}/bootstrap", data={"username": admin_user, "password": admin_pass})
            if boot.status_code not in (302, 303):
                print(f"Bootstrap failed: HTTP {boot.status_code} -> {boot.text[:200]}")
                return 1

            login = client.post(f"{base}/login", data={"username": admin_user, "password": admin_pass})
            if login.status_code not in (302, 303) or "sess" not in client.cookies:
                print("Login failed. Verify superadmin credentials.")
                return 1

            cfg = client.post(
                f"{base}/panel/config",
                data={
                    "panel_url": panel_url,
                    "panel_path": panel_path,
                    "panel_username": panel_user,
                    "panel_password": panel_pass,
                },
            )
            if cfg.status_code not in (302, 303):
                print(f"Saving panel config failed: HTTP {cfg.status_code} -> {cfg.text[:200]}")
                return 1
    except httpx.ConnectError:
        print(f"Could not connect to app at {base}. Is web-helper running?")
        return 1

    print("✅ Setup complete.")
    print(f"Open {base}/ and log in as '{admin_user}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
