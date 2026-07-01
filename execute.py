"""Install Python dependencies for the Revolt/Parley plugin."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _find_python():
    venv = Path("/opt/venv-a0/bin/python")
    return str(venv) if venv.exists() else sys.executable


def _install(pip_name: str, python: str):
    uv = shutil.which("uv")
    if uv:
        subprocess.check_call([uv, "pip", "install", pip_name, "--python", python])
    else:
        subprocess.check_call([python, "-m", "pip", "install", pip_name])


def main() -> int:
    python = _find_python()
    deps = {"aiohttp": "aiohttp>=3.9,<4", "yaml": "pyyaml>=6.0,<7", "httptools": "httptools>=0.6"}
    failed = []
    for import_name, pip_name in deps.items():
        try:
            result = subprocess.run(
                [python, "-c", f"import {import_name}"],
                capture_output=True,
            )
            if result.returncode == 0:
                continue
        except Exception:
            pass
        try:
            _install(pip_name, python)
        except subprocess.CalledProcessError as e:
            failed.append(pip_name)
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
