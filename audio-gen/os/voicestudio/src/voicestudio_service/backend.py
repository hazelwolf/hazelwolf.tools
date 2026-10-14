"""Launch the upstream VoiceStudio backend (uvicorn backend.main:app) with our data/cache dirs."""

from __future__ import annotations

import argparse
import os
import sys

from . import config


def command(host: str, port: int) -> list[str]:
    return [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", host, "--port", str(port)]


def main():
    parser = argparse.ArgumentParser(description="Run the upstream VoiceStudio backend")
    parser.add_argument("--host", default=config.BACKEND_HOST)
    parser.add_argument("--port", type=int, default=config.BACKEND_PORT)
    parser.add_argument("--diagnose", action="store_true", help="Run upstream self-checks and exit")
    args = parser.parse_args()

    env = config.backend_env()
    env["OMNIVOICE_PORT"] = str(args.port)
    env["OMNIVOICE_BIND_HOST"] = args.host
    os.chdir(config.UPSTREAM_DIR)
    if args.diagnose:
        argv = [sys.executable, "backend/main.py", "--diagnose"]
    else:
        argv = command(args.host, args.port)
    os.execvpe(argv[0], argv, env)


if __name__ == "__main__":
    main()
