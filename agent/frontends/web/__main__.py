"""
Web API frontend entry point.

Usage: python -m frontends.web --port 8001
"""

import argparse
import logging
import uvicorn

from .app import create_app


class HealthCheckFilter(logging.Filter):
    """Filter out health check requests from access logs."""
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "/health" not in message


def main():
    parser = argparse.ArgumentParser(description="Compute3 Agent Web API")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    # Suppress health check logging
    logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


main()
