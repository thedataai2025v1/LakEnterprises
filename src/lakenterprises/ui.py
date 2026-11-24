"""UI shell launcher and integration helpers for LakEnterprises Console."""

from __future__ import annotations

import logging
import os
import subprocess  # nosec B404

logger = logging.getLogger(__name__)


def get_frontend_dir() -> str:
    """Return the absolute path to the frontend Next.js directory."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(project_root, "frontend")


def run_frontend_server(port: int = 3001, dev: bool = True) -> int:
    """Launch the Next.js console UI shell process."""
    frontend_dir = get_frontend_dir()
    if not os.path.isdir(frontend_dir):
        logger.error("Frontend directory not found at: %s", frontend_dir)
        return 1

    npm_binary = "npm.cmd" if os.name == "nt" else "npm"
    cmd = [npm_binary, "run", "dev" if dev else "start", "--", "-p", str(port)]
    logger.info("Starting Console UI Shell on port %d from %s", port, frontend_dir)

    try:
        res = subprocess.run(cmd, cwd=frontend_dir, shell=False)  # nosec B603
        return res.returncode
    except Exception as exc:
        logger.error("Failed to start UI console server: %s", exc)
        return 1
