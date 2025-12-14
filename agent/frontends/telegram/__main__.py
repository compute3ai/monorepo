"""
Telegram frontend entry point.

Usage: python -m frontends.telegram --port 8000
"""

import argparse
import uvicorn

from .app import create_app


def main():
    parser = argparse.ArgumentParser(description="Compute3 Agent Telegram Bot")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


main()
