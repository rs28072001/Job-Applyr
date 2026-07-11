# PyInstaller spec — builds the Smart Job Assistant backend into a
# self-contained onedir binary at backend/dist/sja-backend/.
#
# Build (from backend/, inside the venv):
#   pyinstaller sja_backend.spec --noconfirm
import os

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("api")
    + collect_submodules("core")
    + collect_submodules("platforms")
    + collect_submodules("utils")
    + collect_submodules("config")
    # runtime-selected/dynamic deps that static analysis can miss
    + collect_submodules("uvicorn")
    + collect_submodules("websockets")
    + ["passlib.handlers.bcrypt", "anyio._backends._asyncio"]
)

# Selector health check validates selectors against these DOM snapshots at
# runtime (core/selector_health.py) — without them every group reports broken.
datas = [("tests/fixtures", "tests/fixtures")]
# Ship the built frontend inside the binary when present (frontend/dist).
_frontend_dist = os.path.abspath(os.path.join("..", "frontend", "dist"))
if os.path.isdir(_frontend_dist):
    datas.append((_frontend_dist, "frontend_dist"))

a = Analysis(
    ["desktop_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "playwright", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sja-backend",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="sja-backend",
)
