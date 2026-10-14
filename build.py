"""Gera o EXE do Snake Game e, com --installer, seu instalador."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def run(command):
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", action="store_true")
    parser.add_argument("--iscc", help="Caminho do compilador ISCC.exe do Inno Setup")
    args = parser.parse_args()
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        parser.error("Use Windows e Python de 64 bits para gerar este pacote.")
    compiler = None
    if args.installer:
        candidates = [args.iscc, shutil.which("ISCC.exe")]
        for folder in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
            if folder:
                candidates.extend(str(Path(folder) / f"Inno Setup {version}" / "ISCC.exe") for version in (6, 7))
        compiler = next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)
        if not compiler:
            parser.error("Instale Inno Setup 6/7 ou informe --iscc CAMINHO_DO_ISCC.exe.")
    try:
        from PIL import Image
        import PyInstaller
        import pygame
        from main import make_icon
    except ImportError:
        parser.error("Instale as ferramentas: python -m pip install -r requirements-build.txt")
    (ROOT / "build").mkdir(exist_ok=True)
    icon = make_icon()
    image = Image.frombytes("RGB", icon.get_size(), pygame.image.tostring(icon, "RGB"))
    image.resize((256, 256), Image.Resampling.NEAREST).save(ROOT / "build" / "snake.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
         "--name", "SnakeGame", "--icon", str(ROOT / "build" / "snake.ico"),
         "--specpath", str(ROOT / "build"), "--workpath", str(ROOT / "build" / "pyinstaller"),
         "--distpath", str(ROOT / "dist"), str(ROOT / "main.py")])
    print("Executável gerado em:", ROOT / "dist" / "SnakeGame.exe")
    if compiler:
        run([compiler, str(ROOT / "installer" / "game.iss")])
        print("Instalador gerado em:", ROOT / "releases" / "SnakeGame-Setup.exe")


if __name__ == "__main__":
    main()
