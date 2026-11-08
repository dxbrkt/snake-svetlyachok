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
touch build/web/.nojekyll
rm -rf docs
cp -R build/web docs
echo "Готово: build/web/ и docs/ (для GitHub Pages)"
