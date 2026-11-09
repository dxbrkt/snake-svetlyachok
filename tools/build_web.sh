#!/bin/sh
# Сборка веб-версии игры (WebAssembly) через pygbag.
# Результат: build/web/ — эту папку можно выкладывать на GitHub Pages.
set -e
cd "$(dirname "$0")/.."
rm -rf build/webgame
mkdir -p build/webgame
cp the_snake.py design.py visuals.py music.py snake_art.py build/webgame/
cp -R assets build/webgame/assets
cat > build/webgame/main.py <<'PY'
import asyncio

import pygame  # noqa: F401  (pygbag ищет зависимости именно здесь)

import the_snake

asyncio.run(the_snake.main_web())
PY
SSL_CERT_FILE="$(venv/bin/python -m certifi)" venv/bin/pygbag --build --ume_block 0 build/webgame
rm -rf build/web
cp -R build/webgame/build/web build/web
# Browser media needs real HTTP URLs, not files inside the WASM archive.
mkdir -p build/web/audio
cp assets/music/*.ogg build/web/audio/
cp web/audio.js build/web/audio.js
venv/bin/python - <<'PYWEB'
from pathlib import Path
from hashlib import sha256
root = Path("build/web")
page = root / "index.html"
version = sha256((root / "webgame.tar.gz").read_bytes()
                 + (root / "audio.js").read_bytes()).hexdigest()[:12]
html = page.read_text().replace(
    '<script src=', f'<script src="audio.js?v={version}"></script><script src=', 1)
for archive in ("webgame.apk", "webgame.tar.gz"):
    html = html.replace(f'"{archive}"', f'"{archive}?v={version}"')
page.write_text(html)
PYWEB
touch build/web/.nojekyll
rm -rf docs
cp -R build/web docs
echo "Готово: build/web/ и docs/ (для GitHub Pages)"
