"""Настройки оформления игры «Изгиб Питона» (концепция «Светлячок»).

Здесь собраны размеры, цвета, тексты и тайминги анимаций. Игровая логика
лежит в the_snake.py, а отрисовка и эффекты — в visuals.py.
"""

from __future__ import annotations

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

# --- Окно и игровое поле ----------------------------------------------------
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
GRID_SIZE = 28
GRID_WIDTH = 31
GRID_HEIGHT = 17
FIELD_WIDTH = GRID_WIDTH * GRID_SIZE
FIELD_HEIGHT = GRID_HEIGHT * GRID_SIZE
FIELD_X = (SCREEN_WIDTH - FIELD_WIDTH) // 2
FIELD_Y = 118
FIELD_RECT = (FIELD_X, FIELD_Y, FIELD_WIDTH, FIELD_HEIGHT)
FPS = 60

# --- Палитра ----------------------------------------------------------------
NIGHT_TEAL = (9, 45, 56)          # #092D38
DEEP_TEAL = (18, 70, 83)          # #124653
LEAF_GREEN = (104, 201, 59)       # #68C93B
LIGHT_GREEN = (161, 215, 91)      # #A1D75B
GOLD = (255, 212, 90)             # #FFD45A
CREAM = (255, 240, 201)           # #FFF0C9
WOOD = (152, 96, 47)              # #98602F
WOOD_DARK = (92, 56, 26)
WOOD_LIGHT = (236, 203, 146)
TEXT_DARK = (62, 38, 18)
BOARD_BACKGROUND_COLOR = NIGHT_TEAL

# --- Игровой процесс --------------------------------------------------------
WIN_SCORE = 12                    # столько окон в домиках, все и загорятся
LAMPS_PER_LEVEL = 4
STEP_MS_BY_LEVEL = (150, 130, 112)  # чем выше уровень, тем быстрее змейка

# --- Анимации ---------------------------------------------------------------
LIGHT_EFFECT_DURATION = 2.7       # секунд
LIGHT_RAY_COUNT = 7
LIGHT_RAY_ALPHA = 160
BANNER_TIME = 1.9
WINDOW_FADE_TIME = 0.9
COUNTER_BUMP_TIME = 0.4
HEAD_BOUNCE_TIME = 0.4
BUBBLE_TIME = 2.2
MAX_PARTICLES = 220
RAY_RENDER_DIVIDER = 6            # лучи рисуются в уменьшенном виде и мягчатся

# --- Тексты -----------------------------------------------------------------
GAME_TITLE = "СВЕТЛЯЧОК"
WINDOW_TITLE = "Изгиб Питона"
SNAKE_NAME = "Питоша"
DEFAULT_TIP = "Собирай лампочки — береги энергию!"
HURRAY_BANNER = "Ура! Ты сберёг энергию!"
TIPS = (
    "Выключай свет, когда выходишь из комнаты!",
    "Береги электричество!",
    "Дневной свет — наш друг!",
    "Молодец! Ты экономишь энергию!",
)
PRAISES = (
    "Ура!",
    "Как светло!",
    "Ням-ням, свет!",
    "Ещё одна!",
    "Стало уютно!",
    "Ой, как тепло!",
)
START_SPEECH = "Привет! Я Питоша!"
OOPS_SPEECH = "Ой! Ничего, ещё раз!"
LOST_SPEECH = "Где же лампочка?.."
TIP_SHOW_TIME = 5.0
IDLE_SPEECH_AFTER = 9.0

FONT_FILE = ASSETS_DIR / "fonts" / "Marmelad.ttf"
