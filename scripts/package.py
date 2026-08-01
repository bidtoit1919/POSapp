"""Run on the target OS: python scripts/package.py"""
from __future__ import annotations
import shutil
import subprocess
import sys
from pathlib import Path
subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--name", "ShopPOS", "--collect-all", "tkinter", "posdesk/main.py"])
release_installer = Path("dist") / "installer"
if release_installer.exists(): shutil.rmtree(release_installer)
shutil.copytree("installer", release_installer)
print("Release layout created: dist/ShopPOS and dist/installer")
