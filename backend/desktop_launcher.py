"""Entry point for the packaged desktop backend (PyInstaller).

The Electron main process launches this binary with:
  SJA_BASE_DIR — writable per-user data directory (databases, logs, CVs,
                 Chrome profile all live here via cwd-relative paths)
  SJA_PORT     — port to bind the API server on (default 8001)
"""
import multiprocessing
import os
import sys


def main() -> None:
    base_dir = os.environ.get("SJA_BASE_DIR", "").strip()
    if base_dir:
        os.makedirs(base_dir, exist_ok=True)
        # The backend uses cwd-relative paths (./data, ./logs, ./chrome_profile);
        # chdir before importing so they all resolve into the user-data dir.
        os.chdir(base_dir)

    port = int(os.environ.get("SJA_PORT", "8001"))

    import uvicorn
    from api.server import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
