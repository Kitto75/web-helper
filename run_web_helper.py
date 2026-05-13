#!/usr/bin/env python3
"""Helper script to run web-helper with optional SSL cert files."""
import subprocess
import sys


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def main() -> int:
    host = ask("Host", "0.0.0.0")
    port = ask("Port", "38291")
    panel_url = ask("3x-ui panel URL (used to decide SSL mode, e.g. https://panel.example.com)", "")

    cmd = ["uvicorn", "app.main:app", "--host", host, "--port", port]
    if panel_url.lower().startswith("https://"):
        fullchain = ask("Path to fullchain.pem")
        privkey = ask("Path to privkey.pem")
        if not fullchain or not privkey:
            print("fullchain.pem and privkey.pem are required for HTTPS mode.")
            return 1
        cmd.extend(["--ssl-certfile", fullchain, "--ssl-keyfile", privkey])

    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
