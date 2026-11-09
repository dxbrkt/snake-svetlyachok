"""Отрисовка и визуальные эффекты игры «Изгиб Питона».

Классы: Assets (загрузка графики один раз), ParticleSystem, LightRayEffect,
BulbRenderer, SnakeRenderer, BackgroundRenderer, SpeechBubble, TipBar и GameUI.
Настройки берутся из design.py.
"""

from __future__ import annotations

import json
import math
import random
from typing import Dict, List, Optional, Tuple

import pygame

import design as ds
from snake_art import SnakeRenderer, make_head, SKINS

Color = Tuple[int, int, int]
Point = Tuple[float, float]


# --- Небольшие помощники ----------------------------------------------------
def clamp01(value: float) -> float:
    """Ограничить число диапазоном 0..1."""
    return max(0.0, min(1.0, value))


def smoothstep(value: float) -> float:
    """Плавный переход 0..1."""
    value = clamp01(value)
    return value * value * (3 - 2 * value)


def ease_out_back(value: float) -> float:
    """Лёгкий «пружинистый» подъём к единице."""
    value = clamp01(value)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (value - 1) ** 3 + c1 * (value - 1) ** 2


def build_glow(radius: int, color: Color, peak: int) -> pygame.Surface:
    """Создать мягкое радиальное свечение с прозрачными краями."""
    surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -1):
        alpha = int(peak * (1 - r / radius) ** 2)
        pygame.draw.circle(surface, (*color, alpha), (radius, radius), r)
    return surface


def outlined_text(
    font: pygame.font.Font,
    text: str,
    color: Color,
    outline: Color,
    width: int = 3,
) -> pygame.Surface:
    """Отрисовать текст с обводкой, чтобы он читался на любом фоне."""
    base = font.render(text, True, color)
    edge = font.render(text, True, outline)
    surface = pygame.Surface(
        (base.get_width() + width * 2, base.get_height() + width * 2),
        pygame.SRCALPHA,
    )
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if dx * dx + dy * dy <= width * width + 1:
                surface.blit(edge, (width + dx, width + dy))
    surface.blit(base, (width, width))
    return surface


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> List[str]:
    """Разбить текст на строки заданной ширины."""
    lines: List[str] = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if font.size(candidate)[0] <= max_width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def wood_panel(
    size: Tuple[int, int],
    radius: int = 18,
    fill: Color = ds.WOOD_LIGHT,
    border: Color = ds.WOOD,
    seed: int = 3,
) -> pygame.Surface:
    """Нарисовать деревянную табличку с рамкой и лёгкими прожилками."""
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(surface, ds.WOOD_DARK, (0, 3, width, height - 3),
                     border_radius=radius)
    pygame.draw.rect(surface, border, (0, 0, width, height - 4),
                     border_radius=radius)
    inner = pygame.Rect(5, 5, width - 10, height - 14)
    pygame.draw.rect(surface, fill, inner, border_radius=max(radius - 5, 4))
    rnd = random.Random(seed)
    grain = tuple(max(c - 22, 0) for c in fill)
    streaks = pygame.Surface(inner.size, pygame.SRCALPHA)
    for _ in range(max(width // 60, 3)):
        y = rnd.randint(8, inner.height - 8)
        x0 = rnd.randint(6, inner.width // 2)
        x1 = min(x0 + rnd.randint(40, 120), inner.width - 6)
        pygame.draw.line(streaks, (*grain, 38), (x0, y), (x1, y), 2)
    surface.blit(streaks, inner.topleft)
    pygame.draw.line(
        surface, (255, 255, 255, 60),
        (inner.left + radius, inner.top + 2), (inner.right - radius, inner.top + 2), 2,
    )
    return surface


# --- Загрузка ресурсов ------------------------------------------------------
class Assets:
    """Загружает всю графику и шрифты один раз при старте."""

    def __init__(self) -> None:
        """Прочитать изображения из папки assets."""
        load = self._load
        self.background = pygame.image.load(
            str(ds.ASSETS_DIR / "backgrounds" / "background.png")
        ).convert()
        self.head = make_head()
        self.body = load("characters/snake_body.png")
        self.tail = load("characters/snake_tail.png")
        self.bulb = load("objects/bulb.png")
        self.switch_on = load("objects/switch.png")
        self.switch_off = load("objects/switch_off.png")
        self.switch_icon_on = load("ui/switch_icon_on.png")
        self.switch_icon_off = load("ui/switch_icon_off.png")
        self.click_flash = load("effects/click_flash.png")
        self.star = load("effects/star.png")
        self.leaf = load("ui/leaf.png")
        self.pause = load("ui/pause.png")
        meta = json.loads(
            (ds.ASSETS_DIR / "backgrounds" / "windows.json").read_text(encoding="utf-8")
        )
        self.windows = [
            (load("backgrounds/" + item["file"]), tuple(item["pos"]),
             tuple(item["center"]))
            for item in meta
        ]
        self._fonts: Dict[int, pygame.font.Font] = {}

    @staticmethod
    def _load(relative: str) -> pygame.Surface:
        return pygame.image.load(str(ds.ASSETS_DIR / relative)).convert_alpha()

    def font(self, size: int) -> pygame.font.Font:
        """Вернуть шрифт нужного размера (с кириллицей)."""
        if size not in self._fonts:
            font = pygame.font.Font(str(ds.FONT_FILE), size)
            font.set_bold(True)
            self._fonts[size] = font
        return self._fonts[size]


# --- Частицы ----------------------------------------------------------------
class _Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "kind", "spin")

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 life: float, kind: int, spin: float = 0.0) -> None:
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.kind = kind
        self.spin = spin


class ParticleSystem:
    """Маленькие светящиеся золотые частицы (искры и пылинки света)."""

    def __init__(self, star: pygame.Surface) -> None:
        """Подготовить спрайты частиц, чтобы не создавать их каждый кадр."""
        self._dots = [
            build_glow(r, ds.GOLD, 255) for r in (4, 6, 9)
        ]
        self._star = pygame.transform.smoothscale(star, (16, 18))
        self.items: List[_Particle] = []
        self._rnd = random.Random()

    def _add(self, particle: _Particle) -> None:
        if len(self.items) < ds.MAX_PARTICLES:
            self.items.append(particle)

    def burst(self, x: float, y: float, count: int) -> None:
        """Разлёт искр вокруг точки."""
        for _ in range(count):
            angle = self._rnd.uniform(0, math.tau)
            speed = self._rnd.uniform(50, 230)
            self._add(_Particle(
                x, y, math.cos(angle) * speed, math.sin(angle) * speed - 30,
                self._rnd.uniform(0.7, 1.5), self._rnd.choice((0, 1, 2, 3)),
            ))

    def dust(self, x: float, y: float) -> None:
        """Одна медленная пылинка света, плывущая вниз."""
        self._add(_Particle(
            x, y, self._rnd.uniform(-12, 12), self._rnd.uniform(18, 48),
            self._rnd.uniform(1.4, 2.6), self._rnd.choice((0, 0, 1)),
        ))

    def update(self, dt: float) -> None:
        """Подвинуть частицы и убрать угасшие."""
        alive = []
        drag = max(0.0, 1 - 1.8 * dt)
        for p in self.items:
            p.life -= dt
            if p.life <= 0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.max_life < 1.6 and p.kind != 4:
                p.vx *= drag
                p.vy = p.vy * drag + 24 * dt
            alive.append(p)
        self.items = alive

    def draw(self, surface: pygame.Surface) -> None:
        """Нарисовать частицы с плавным угасанием."""
        for p in self.items:
            fade = clamp01(p.life / p.max_life)
            alpha = int(255 * min(1.0, fade * 2.2) * min(1.0, (1 - fade) * 8 + 0.2))
            if p.kind == 3:
                sprite = self._star
            else:
                sprite = self._dots[p.kind]
            sprite.set_alpha(alpha)
            surface.blit(sprite, sprite.get_rect(center=(p.x, p.y)))


# --- Эффект лучей света -----------------------------------------------------
class LightRayEffect:
    """Тёплые мягкие лучи света сверху, свечение и надпись «Ура!»."""

    def __init__(self, assets: Assets, particles: ParticleSystem) -> None:
        """Подготовить кэшированные поверхности эффекта."""
        self.particles = particles
        self.active = False
        self.t = 0.0
        self.origin: Point = (0, 0)
        self.target: Point = (0, 0)
        div = ds.RAY_RENDER_DIVIDER
        self._low_size = (ds.FIELD_WIDTH // div, ds.FIELD_HEIGHT // div)
        self._low = pygame.Surface(self._low_size, pygame.SRCALPHA)
        self._mask = pygame.Surface(self._low_size, pygame.SRCALPHA)
        for y in range(self._low_size[1]):
            fade = 1 - 0.65 * (y / self._low_size[1])
            pygame.draw.line(
                self._mask, (255, 255, 255, int(255 * fade)),
                (0, y), (self._low_size[0], y),
            )
        self._glow_big = build_glow(170, (255, 205, 90), 200)
        self._glow_small = build_glow(80, (255, 236, 170), 255)
        self._flash = pygame.Surface((ds.FIELD_WIDTH, ds.FIELD_HEIGHT))
        self._flash.fill((255, 226, 140))
        self._star = assets.star
        self._banner = outlined_text(
            assets.font(46), ds.HURRAY_BANNER, ds.CREAM, ds.WOOD_DARK, 4
        )
        self._rnd = random.Random()

    def trigger(self, origin: Point, target: Point) -> None:
        """Запустить эффект; повторный запуск плавно продлевает свет."""
        self.origin = origin
        if self.active:
            self.t = min(self.t, 0.6)
        else:
            self.target = target
            self.t = 0.0
        self.active = True
        self.particles.burst(origin[0], origin[1], 30)

    def _intensity(self) -> float:
        fade_in = smoothstep(self.t / 0.45)
        fade_out = 1 - smoothstep((self.t - (ds.LIGHT_EFFECT_DURATION - 1.2)) / 1.2)
        return fade_in * fade_out

    def update(self, dt: float, target: Point) -> None:
        """Подвинуть эффект за змейкой и добавить пылинки света в лучи."""
        if not self.active:
            return
        self.t += dt
        if self.t >= ds.LIGHT_EFFECT_DURATION:
            self.active = False
            return
        follow = min(1.0, dt * 5)
        self.target = (
            self.target[0] + (target[0] - self.target[0]) * follow,
            self.target[1] + (target[1] - self.target[1]) * follow,
        )
        if self._intensity() > 0.35 and self._rnd.random() < dt * 55:
            self.particles.dust(
                self.target[0] + self._rnd.uniform(-150, 150),
                self._rnd.uniform(0, ds.FIELD_HEIGHT * 0.55),
            )

    def draw_under(self, field: pygame.Surface) -> None:
        """Лучи и сияние (рисуются под змейкой, чтобы она оставалась видна)."""
        if not self.active:
            return
        strength = self._intensity()
        div = ds.RAY_RENDER_DIVIDER
        tx, ty = self.target
        count = ds.LIGHT_RAY_COUNT
        self._low.fill((0, 0, 0, 0))
        for k in range(count):
            spread = k - (count - 1) / 2
            sway = math.sin(self.t * 1.5 + k * 1.3)
            apex_x = tx + spread * 14
            bottom_x = tx + spread * (92 + 10 * sway)
            bottom_y = min(ty + 70, ds.FIELD_HEIGHT + 20)
            pulse = 0.72 + 0.28 * math.sin(self.t * 2.1 + k * 0.9)
            for width, scale in ((62, 0.5), (34, 1.0)):
                half_bottom = (width + 6 * sway) / div
                points = [
                    ((apex_x - 5) / div, -6 / div),
                    ((apex_x + 5) / div, -6 / div),
                    (bottom_x / div + half_bottom, bottom_y / div),
                    (bottom_x / div - half_bottom, bottom_y / div),
                ]
                alpha = int(ds.LIGHT_RAY_ALPHA * scale * pulse)
                pygame.draw.polygon(self._low, (255, 214, 104, alpha), points)
        self._low.blit(self._mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        softened = pygame.transform.smoothscale(
            self._low, (self._low_size[0] // 2, self._low_size[1] // 2)
        )
        rays = pygame.transform.smoothscale(
            softened, (ds.FIELD_WIDTH, ds.FIELD_HEIGHT)
        )
        rays.set_alpha(int(255 * strength))
        field.blit(rays, (0, 0))

        flash = clamp01(1 - self.t / 0.45)
        if flash > 0:
            self._flash.set_alpha(int(80 * flash * flash))
            field.blit(self._flash, (0, 0))

        pulse = 0.85 + 0.15 * math.sin(self.t * 4)
        self._glow_big.set_alpha(int(255 * strength * pulse))
        field.blit(self._glow_big, self._glow_big.get_rect(center=(tx, ty)))

        if self.t < 0.5:
            local = self.t / 0.5
            ox, oy = self.origin
            size = int(30 + 190 * local)
            star = pygame.transform.smoothscale(self._star, (size, int(size * 1.1)))
            star.set_alpha(int(255 * (1 - local)))
            field.blit(star, star.get_rect(center=(ox, oy)))
            self._glow_small.set_alpha(int(255 * (1 - local)))
            field.blit(self._glow_small, self._glow_small.get_rect(center=(ox, oy)))

    def draw_banner(self, screen: pygame.Surface) -> None:
        """Надпись «Ура! Ты сберёг энергию!» с мягким появлением."""
        if not self.active or self.t > ds.BANNER_TIME:
            return
        start = 0.15
        appear = smoothstep((self.t - start) / 0.25)
        vanish = 1 - smoothstep((self.t - (ds.BANNER_TIME - 0.5)) / 0.5)
        alpha = int(255 * appear * vanish)
        if alpha <= 0:
            return
        pop = 0.75 + 0.25 * ease_out_back((self.t - start) / 0.35)
        size = (int(self._banner.get_width() * pop),
                int(self._banner.get_height() * pop))
        image = pygame.transform.smoothscale(self._banner, size)
        image.set_alpha(alpha)
        center = (ds.SCREEN_WIDTH // 2, ds.FIELD_Y + 58 - 10 * smoothstep(self.t))
        screen.blit(image, image.get_rect(center=center))


# --- Управление светом ------------------------------------------------------
class LightController:
    """Прогресс энергосбережения: окна не включаются сами."""

    def __init__(self) -> None:
        """В начале партии все окна горят."""
        self.off_count = 0
        self.remaining = 0.0
        self.darkness = 0.0

    @property
    def is_off(self) -> bool:
        """Выключен ли свет во всех домиках."""
        return self.off_count == ds.WIN_SCORE

    @property
    def fraction(self) -> float:
        """Доля погашенных окон."""
        return self.off_count / ds.WIN_SCORE

    def switch_off(self) -> None:
        """Погасить ещё одно окно до конца партии."""
        self.off_count = min(ds.WIN_SCORE, self.off_count + 1)
        self.remaining = ds.NIGHT_DURATION

    def reset(self) -> None:
        """Начать новую партию с включённым светом."""
        self.off_count = 0
        self.remaining = 0.0
        self.darkness = 0.0

    def update(self, dt: float) -> None:
        """После выключения наступает ночь, через пять секунд — утро."""
        night_dt = min(dt, self.remaining)
        self.remaining = max(0.0, self.remaining - dt)
        self.darkness = min(1.0, self.darkness + night_dt / ds.NIGHT_FADE_TIME)
        morning_dt = dt - night_dt
        self.darkness = max(0.0, self.darkness - morning_dt / ds.MORNING_FADE_TIME)


# --- Выключатель ------------------------------------------------------------
class SwitchRenderer:
    """Выключатель света: покачивается, светится и заметен даже в темноте."""

    def __init__(self, assets: Assets, particles: ParticleSystem) -> None:
        """Заранее повернуть выключатель на несколько углов для покачивания."""
        base = assets.switch_on
        self._frames = [
            pygame.transform.rotozoom(base, angle, 1.0) for angle in range(-6, 7, 2)
        ]
        self._halo = build_glow(54, (255, 214, 120), 150)
        self._spark = build_glow(5, (255, 244, 190), 255)
        self.born = 0.0
        self.particles = particles

    def respawn(self, now: float) -> None:
        """Выключатель появился в новом месте — запустить анимацию появления."""
        self.born = now

    def draw(self, field: pygame.Surface, cell: Tuple[int, int], now: float) -> None:
        """Нарисовать выключатель в клетке поля."""
        cx = (cell[0] + 0.5) * ds.GRID_SIZE
        cy = (cell[1] + 0.5) * ds.GRID_SIZE - 3 + 2 * math.sin(now * 2.4)
        wave = 0.5 + 0.5 * math.sin(now * 3.2)
        sway = math.sin(now * 2.6)
        pop = ease_out_back((now - self.born) / 0.45)

        def scaled(image: pygame.Surface) -> pygame.Surface:
            if pop >= 0.999:
                return image
            size = (max(int(image.get_width() * pop), 2),
                    max(int(image.get_height() * pop), 2))
            return pygame.transform.smoothscale(image, size)

        halo = scaled(self._halo)
        halo.set_alpha(int(120 + 100 * wave))
        field.blit(halo, halo.get_rect(center=(cx, cy)))

        frame = self._frames[round((sway + 1) / 2 * (len(self._frames) - 1))]
        frame = scaled(frame)
        field.blit(frame, frame.get_rect(center=(cx, cy)))

        for k in range(3):
            angle = now * 1.7 + k * math.tau / 3
            radius = 36 + 4 * math.sin(now * 2 + k)
            self._spark.set_alpha(int(120 + 120 * math.sin(now * 5 + k * 2) ** 2))
            field.blit(
                self._spark,
                self._spark.get_rect(
                    center=(cx + math.cos(angle) * radius,
                            cy + math.sin(angle) * radius * 0.8)
                ),
            )


class SwitchClickEffect:
    """Щелчок: рычаг переключается, мягкая вспышка, лёгкая вспышка поля."""

    def __init__(self, assets: Assets) -> None:
        """Подготовить спрайты и слой вспышки."""
        self.on = assets.switch_on
        self.off = assets.switch_off
        self.flash = assets.click_flash
        self._field_flash = pygame.Surface((ds.FIELD_WIDTH, ds.FIELD_HEIGHT))
        self._field_flash.fill((205, 225, 255))
        self.pos: Point = (0, 0)
        self.t = ds.CLICK_EFFECT_TIME

    @property
    def active(self) -> bool:
        """Идёт ли сейчас анимация."""
        return self.t < ds.CLICK_EFFECT_TIME

    def trigger(self, pos: Point) -> None:
        """Запустить анимацию щелчка в точке поля."""
        self.pos = pos
        self.t = 0.0

    def update(self, dt: float) -> None:
        """Продвинуть время анимации."""
        if self.active:
            self.t += dt

    def draw(self, field: pygame.Surface) -> None:
        """Нарисовать анимацию щелчка."""
        if not self.active:
            return
        k = self.t / ds.CLICK_EFFECT_TIME
        x, y = self.pos

        flash_k = clamp01(self.t / 0.4)
        size = int(60 + 110 * flash_k)
        star = pygame.transform.smoothscale(self.flash, (size, int(size * 1.11)))
        star.set_alpha(int(170 * (1 - flash_k)))
        field.blit(star, star.get_rect(center=(x, y)))

        sprite = self.on if self.t < 0.1 else self.off
        scale = 1 + 0.35 * smoothstep(k * 1.6)
        image = pygame.transform.smoothscale(
            sprite,
            (int(sprite.get_width() * scale), int(sprite.get_height() * scale)),
        )
        image.set_alpha(int(255 * (1 - smoothstep((k - 0.35) / 0.65))))
        field.blit(image, image.get_rect(center=(x, y - 10 * k)))

        flash = (1 - clamp01(self.t / 0.3)) ** 2 * 26
        if flash > 1:
            self._field_flash.set_alpha(int(flash))
            field.blit(self._field_flash, (0, 0))


class Banner:
    """Надпись по центру сверху поля: быстро появляется и плавно исчезает."""

    def __init__(self, assets: Assets, text: str, duration: float,
                 outline: Color = ds.WOOD_DARK) -> None:
        """Нарисовать текст один раз."""
        self.image = outlined_text(assets.font(46), text, ds.CREAM, outline, 4)
        self.duration = duration
        self.t = duration

    def show(self) -> None:
        """Показать надпись."""
        self.t = 0.0

    def update(self, dt: float) -> None:
        """Продвинуть время показа."""
        if self.t < self.duration:
            self.t += dt

    def draw(self, screen: pygame.Surface) -> None:
        """Нарисовать надпись с мягким появлением."""
        if self.t >= self.duration:
            return
        appear = smoothstep(self.t / 0.2)
        vanish = 1 - smoothstep((self.t - (self.duration - 0.6)) / 0.6)
        alpha = int(255 * appear * vanish)
        if alpha <= 0:
            return
        pop = 0.75 + 0.25 * ease_out_back(self.t / 0.35)
        size = (int(self.image.get_width() * pop), int(self.image.get_height() * pop))
        image = pygame.transform.smoothscale(self.image, size)
        image.set_alpha(alpha)
        center = (ds.SCREEN_WIDTH // 2, ds.FIELD_Y + 58 - 8 * smoothstep(self.t))
        screen.blit(image, image.get_rect(center=center))


# --- Змейка-персонаж --------------------------------------------------------
# --- Фон с домиками ---------------------------------------------------------
class BackgroundRenderer:
    """Ночной мир с домиками: окна светятся, пока свет включён."""

    def __init__(self, assets: Assets) -> None:
        """Подготовить фон, окна, мерцающие звёзды и лёгкий туман."""
        self.background = assets.background
        self.night_background = assets.background.copy()
        self.windows = assets.windows
        self.ramp = [0.0] * len(self.windows)
        self.target = [0.0] * len(self.windows)
        self.time = 0.0
        self.fog = pygame.transform.smoothscale(
            build_glow(150, (150, 205, 195), 46), (440, 150)
        )
        self.spill = build_glow(46, (255, 196, 80), 140)
        # Светлый дневной вариант фона: рисунок и фактура сохраняются.
        self.background = self.background.copy()
        daylight = pygame.Surface(self.background.get_size())
        for y in range(ds.SCREEN_HEIGHT):
            t = y / ds.SCREEN_HEIGHT
            color = tuple(int(a * (1 - t) + b * t)
                          for a, b in zip((115, 160, 175), (65, 95, 35)))
            pygame.draw.line(daylight, color, (0, y), (ds.SCREEN_WIDTH, y))
        self.background.blit(daylight, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        field = assets.background.subsurface(ds.FIELD_RECT).copy()
        field.fill((165, 146, 91), special_flags=pygame.BLEND_RGB_ADD)
        self.background.blit(field, ds.FIELD_RECT[:2])
        frame = pygame.Rect(ds.FIELD_RECT).inflate(12, 12)
        pygame.draw.rect(self.background, (69, 119, 72), frame,
                         width=4, border_radius=28)

    def set_lit(self, count: int) -> None:
        """Сколько окон должно гореть."""
        for i in range(len(self.target)):
            self.target[i] = 1.0 if i >= len(self.target) - count else 0.0

    def update(self, dt: float) -> None:
        """Плавно зажигать и гасить окна."""
        self.time += dt
        step = dt / ds.WINDOW_FADE_TIME
        for i, goal in enumerate(self.target):
            if self.ramp[i] < goal:
                self.ramp[i] = min(goal, self.ramp[i] + step)
            elif self.ramp[i] > goal:
                self.ramp[i] = max(goal, self.ramp[i] - step * 3)

    def draw(self, screen: pygame.Surface, darkness: float = 0.0) -> None:
        """Плавная смена дневного и ночного леса после выключения."""
        screen.blit(self.background, (0, 0))
        if darkness > 0:
            self.night_background.set_alpha(round(255 * darkness))
            screen.blit(self.night_background, (0, 0))
        for i, (image, pos, center) in enumerate(self.windows):
            ramp = self.ramp[i] * (1 - darkness)
            if ramp <= 0.01:
                continue
            self.spill.set_alpha(int(255 * clamp01(ramp)))
            screen.blit(self.spill, self.spill.get_rect(center=center))
            glow = 1 + 0.4 * math.sin(clamp01(ramp) * math.pi) * (ramp < 1)
            image.set_alpha(int(min(255, 255 * ramp * min(glow, 1.0))
                                * (0.93 + 0.07 * math.sin(self.time * 2.3 + i))))
            screen.blit(image, pos)

    def draw_mist(self, field: pygame.Surface) -> None:
        """Лёгкий туман, плывущий над полем."""
        for i, speed in enumerate((14, -9, 6)):
            x = (self.time * speed + i * 330) % (ds.FIELD_WIDTH + 420) - 420
            y = 60 + i * 150 + 16 * math.sin(self.time * 0.4 + i)
            field.blit(self.fog, (x, y))


# --- Реплики змейки и подсказки ---------------------------------------------
class SpeechBubble:
    """Облачко с короткой фразой над головой змейки."""

    def __init__(self, assets: Assets) -> None:
        """Запомнить шрифт."""
        self.font = assets.font(24)
        self.image: Optional[pygame.Surface] = None
        self.t = 0.0
        self.duration = ds.BUBBLE_TIME

    def say(self, text: str, duration: float = ds.BUBBLE_TIME) -> None:
        """Показать фразу."""
        label = self.font.render(text, True, ds.TEXT_DARK)
        pad_x, pad_y, tail = 16, 9, 10
        width, height = label.get_width() + pad_x * 2, label.get_height() + pad_y * 2
        bubble = pygame.Surface((width, height + tail), pygame.SRCALPHA)
        pygame.draw.rect(bubble, ds.WOOD, (0, 0, width, height), border_radius=16)
        pygame.draw.rect(bubble, ds.CREAM, (3, 3, width - 6, height - 6),
                         border_radius=13)
        pygame.draw.polygon(
            bubble, ds.WOOD,
            [(width // 2 - 9, height - 2), (width // 2 + 9, height - 2),
             (width // 2, height + tail)],
        )
        pygame.draw.polygon(
            bubble, ds.CREAM,
            [(width // 2 - 6, height - 4), (width // 2 + 6, height - 4),
             (width // 2, height + tail - 4)],
        )
        bubble.blit(label, (pad_x, pad_y))
        self.image = bubble
        self.t = 0.0
        self.duration = duration

    def update(self, dt: float) -> None:
        """Отсчитать время показа."""
        if self.image is not None:
            self.t += dt
            if self.t >= self.duration:
                self.image = None

    def draw(self, screen: pygame.Surface, head_px: Point) -> None:
        """Нарисовать облачко над головой, не выходя за рамку поля."""
        if self.image is None:
            return
        appear = smoothstep(self.t / 0.18)
        vanish = 1 - smoothstep((self.t - (self.duration - 0.4)) / 0.4)
        self.image.set_alpha(int(255 * appear * vanish))
        rect = self.image.get_rect()
        x = ds.FIELD_X + head_px[0] - rect.width / 2
        y = ds.FIELD_Y + head_px[1] - 56 - rect.height + 6 * (1 - appear)
        x = max(ds.FIELD_X + 8, min(x, ds.FIELD_X + ds.FIELD_WIDTH - rect.width - 8))
        y = max(ds.FIELD_Y + 6, y)
        screen.blit(self.image, (x, y))


class TipBar:
    """Нижняя табличка с подсказкой, фразы меняются плавно."""

    def __init__(self, assets: Assets) -> None:
        """Подготовить табличку."""
        self.font = assets.font(30)
        self.size = (800, 74)
        self.panel = wood_panel(self.size, 24, ds.CREAM, ds.WOOD, seed=11)
        self.leaf = pygame.transform.smoothscale(assets.leaf, (34, 40))
        self.current = self._render(ds.DEFAULT_TIP)
        self.previous: Optional[pygame.Surface] = None
        self.fade = 1.0
        self.text = ds.DEFAULT_TIP

    def _render(self, text: str) -> pygame.Surface:
        font = self.font
        size = 30
        while font.size(text)[0] > self.size[0] - 150 and size > 20:
            size -= 2
            font = pygame.font.Font(str(ds.FONT_FILE), size)
            font.set_bold(True)
        return font.render(text, True, (52, 86, 40))

    def set_text(self, text: str) -> None:
        """Сменить фразу с затуханием."""
        if text == self.text:
            return
        self.text = text
        self.previous, self.current = self.current, self._render(text)
        self.fade = 0.0

    def update(self, dt: float) -> None:
        """Продвинуть затухание."""
        if self.fade < 1:
            self.fade = min(1.0, self.fade + dt / 0.35)

    def draw(self, screen: pygame.Surface) -> None:
        """Нарисовать табличку по центру внизу."""
        rect = self.panel.get_rect(center=(730, 660))
        screen.blit(self.panel, rect)
        screen.blit(self.leaf, (rect.x + 34, rect.centery - 24))
        center = (rect.centerx + 30, rect.centery - 4)
        if self.previous is not None and self.fade < 1:
            self.previous.set_alpha(int(255 * (1 - self.fade)))
            screen.blit(self.previous, self.previous.get_rect(center=center))
        self.current.set_alpha(int(255 * self.fade))
        screen.blit(self.current, self.current.get_rect(center=center))


class LightIndicator:
    """Табличка «СВЕТ ВКЛЮЧЁН / ВЫКЛЮЧЕН» с обратным отсчётом."""

    SIZE = (296, 74)

    def __init__(self, assets: Assets) -> None:
        """Нарисовать обе версии таблички один раз."""
        self.assets = assets
        self.panel_on = wood_panel(self.SIZE, 22, ds.CREAM, ds.WOOD, seed=21)
        self.icon_on = assets.switch_icon_on
        self.icon_off = assets.switch_icon_off
        self.rect = pygame.Rect(0, 0, *self.SIZE)
        self.rect.center = (20 + self.SIZE[0] // 2, 660)
        self.texts: Dict[Tuple[str, int, Color], pygame.Surface] = {}

    def _text(self, text: str, size: int, color: Color) -> pygame.Surface:
        key = (text, size, color)
        if key not in self.texts:
            self.texts[key] = self.assets.font(size).render(text, True, color)
        return self.texts[key]

    def draw(self, screen: pygame.Surface, light: LightController) -> None:
        """Показать накопленный результат вместо таймера включения света."""
        rect = self.rect
        screen.blit(self.panel_on, rect)
        icon = self.icon_off if light.off_count else self.icon_on
        screen.blit(icon, icon.get_rect(center=(rect.x + 40, rect.centery - 3)))
        label = self._text("ОКОН ПОГАШЕНО", 17, (52, 86, 40))
        screen.blit(label, label.get_rect(midleft=(rect.x + 74, rect.y + 24)))
        bar = pygame.Rect(rect.x + 74, rect.y + 45, 136, 9)
        pygame.draw.rect(screen, (207, 187, 137), bar, border_radius=4)
        fill = bar.copy()
        fill.width = int(bar.width * light.fraction)
        if fill.width > 0:
            pygame.draw.rect(screen, (64, 128, 57), fill, border_radius=4)
        number = self._text(f"{light.off_count}/{ds.WIN_SCORE}", 19, ds.TEXT_DARK)
        screen.blit(number, number.get_rect(center=(rect.right - 41, rect.y + 49)))


# --- Интерфейс --------------------------------------------------------------
class Button:
    """Деревянная кнопка с зелёной серединой."""

    def __init__(self, assets: Assets, label: str, center: Tuple[int, int],
                 width: int = 300) -> None:
        """Нарисовать кнопку один раз."""
        size = (width, 70)
        self.image = wood_panel(size, 26, ds.LEAF_GREEN, ds.WOOD, seed=5)
        text = outlined_text(assets.font(32), label, ds.CREAM, (40, 90, 30), 3)
        self.image.blit(text, text.get_rect(center=(width // 2, 33)))
        self.rect = self.image.get_rect(center=center)

    def draw(self, screen: pygame.Surface, hover: bool) -> None:
        """Нарисовать кнопку; при наведении она чуть увеличивается."""
        if hover:
            big = pygame.transform.smoothscale(
                self.image,
                (int(self.rect.width * 1.05), int(self.rect.height * 1.05)),
            )
            screen.blit(big, big.get_rect(center=self.rect.center))
        else:
            screen.blit(self.image, self.rect)


class GameUI:
    """Верхняя и нижняя панели, кнопка паузы и экраны игры."""

    def __init__(self, assets: Assets) -> None:
        """Нарисовать неизменные элементы один раз."""
        self.assets = assets
        self.title = outlined_text(
            assets.font(42), ds.GAME_TITLE, ds.CREAM, (14, 40, 32), 4
        )
        self.leaf_big = pygame.transform.smoothscale(assets.leaf, (46, 54))
        self.counter_panel = wood_panel((330, 64), 22, (244, 214, 160), ds.WOOD, 2)
        self.counter_font = assets.font(34)
        self.level_panel = self._level_panel()
        self.tip = TipBar(assets)
        self.click_banner = Banner(assets, ds.CLICK_BANNER, ds.CLICK_BANNER_TIME,
                                   (14, 30, 66))
        self.switch_big = pygame.transform.smoothscale(assets.switch_on, (96, 107))
        self.switch_off_big = pygame.transform.smoothscale(assets.switch_off, (96, 107))
        self.pause_image = pygame.transform.smoothscale(assets.pause, (66, 68))
        self.pause_rect = self.pause_image.get_rect(center=(1196, 660))
        self.dim = pygame.Surface((ds.SCREEN_WIDTH, ds.SCREEN_HEIGHT),
                                  pygame.SRCALPHA)
        self.dim.fill((4, 22, 30, 175))
        self.panel = wood_panel((700, 500), 34, ds.CREAM, ds.WOOD, seed=9)
        self.bubble = SpeechBubble(assets)
        self.bump = ds.COUNTER_BUMP_TIME
        self.glow = build_glow(120, ds.GOLD, 200)
        self.head_big = pygame.transform.smoothscale(assets.head, (176, 127))
        self.buttons = {
            "skin_back": Button(assets, "Готово", (640, 555), 260),
            "start": Button(assets, "Играть", (640, 566)),
            "resume": Button(assets, "Продолжить", (485, 550), 270),
            "again": Button(assets, "Ещё раз", (485, 550), 270),
            "menu": Button(assets, "Выбор режима", (800, 550), 300),
        }
        self.skins_button = pygame.Rect(354, 305, 272, 48)
        self.skin_rects = {key: pygame.Rect(315 + i * 165, 235, 155, 214)
                           for i, key in enumerate(SKINS)}
        self.skin_previews = {key: pygame.transform.smoothscale(make_head(skin=key), (150, 120))
                              for key in SKINS}
        self.mode_rects = {
            "village": pygame.Rect(320, 370, 305, 114),
            "endless": pygame.Rect(655, 370, 305, 114),
        }
        self.texts: Dict[Tuple[str, int, Color], pygame.Surface] = {}

    def set_skin(self, skin):
        self.head_big = pygame.transform.smoothscale(make_head(skin=skin), (176, 127))

    def draw_skins(self, screen, mouse, selected, unlocked, focus):
        self._panel_with_title(screen, "Выбрать змейку")
        for index, (key, box) in enumerate(self.skin_rects.items()):
            active = key == selected
            available = key in unlocked
            pygame.draw.rect(screen, ds.DEEP_TEAL if active else (231, 215, 179), box, border_radius=18)
            pygame.draw.rect(screen, ds.GOLD if active else ds.WOOD,
                             box, 3 if index == focus or box.collidepoint(mouse) else 1,
                             border_radius=18)
            color = ds.CREAM if active else ds.TEXT_DARK
            label = self._text(SKINS[key]["name"], 21, color)
            screen.blit(label, label.get_rect(center=(box.centerx, box.y + 25)))
            preview = self.skin_previews[key]
            screen.blit(preview, preview.get_rect(center=(box.centerx, box.y + 100)))
            lines = (["Выбрано"] if active else [f"{index + 1} · Выбрать"] if available else
                     ["Спаси деревню", "чтобы открыть"] if key == "firefly" else
                     ["Собери 24", "в бесконечном"])
            for n, text in enumerate(lines):
                label = self._text(text, 16, color)
                screen.blit(label, label.get_rect(center=(box.centerx, box.y + 170 + n * 22)))
        key = list(SKINS)[focus]
        note = "Все змейки одинаково быстрые. Выбери любимую!"
        if key not in unlocked:
            note = ("Светлячок: собери все 12 выключателей в деревне."
                    if key == "firefly" else "Дракончик: собери 24 за одну бесконечную игру.")
        self._lines(screen, [note], 478, 19)
        self._lines(screen, ["1–4 — выбор · стрелки — просмотр · Esc — назад"], 509, 16)
        button = self.buttons["skin_back"]
        button.draw(screen, button.rect.collidepoint(mouse))

    def _level_panel(self) -> pygame.Surface:
        panel = pygame.Surface((200, 50), pygame.SRCALPHA)
        pygame.draw.rect(panel, (36, 86, 52), (0, 0, 200, 50), border_radius=24)
        pygame.draw.rect(panel, (196, 214, 150), (0, 0, 200, 50), 2, border_radius=24)
        for x in range(14, 186, 14):
            pygame.draw.line(panel, (196, 214, 150), (x, 5), (x + 7, 5), 2)
            pygame.draw.line(panel, (196, 214, 150), (x, 44), (x + 7, 44), 2)
        return panel

    def _text(self, text: str, size: int, color: Color) -> pygame.Surface:
        key = (text, size, color)
        if key not in self.texts:
            self.texts[key] = self.assets.font(size).render(text, True, color)
        return self.texts[key]

    def pop_counter(self) -> None:
        """Анимация счётчика при подборе выключателя."""
        self.bump = 0.0

    def update(self, dt: float) -> None:
        """Продвинуть анимации интерфейса."""
        self.tip.update(dt)
        self.bubble.update(dt)
        self.click_banner.update(dt)
        if self.bump < ds.COUNTER_BUMP_TIME:
            self.bump += dt

    def draw_hud(self, screen: pygame.Surface, score: int, level: int,
                 hover_pause: bool, light: LightController, mode: str = "village",
                 best: int = 0, village: int = 1) -> None:
        """Верхняя панель, индикатор света, подсказка и кнопка паузы."""
        screen.blit(self.leaf_big, (26, 24))
        screen.blit(self.title, (84, 22))

        rect = self.counter_panel.get_rect(center=(ds.SCREEN_WIDTH // 2, 48))
        screen.blit(self.counter_panel, rect)
        counter = f"Выключатели: {score} / {ds.WIN_SCORE}" if mode == "village" else f"Выключатели: {score}"
        label = self._text(counter, 23, ds.TEXT_DARK)
        screen.blit(label, label.get_rect(center=rect.center))
        if mode == "endless":
            record = self._text(f"Личный рекорд: {best}", 20, ds.CREAM)
            screen.blit(record, record.get_rect(center=(640, 94)))

        level_rect = self.level_panel.get_rect(topright=(ds.SCREEN_WIDTH - 36, 22))
        screen.blit(self.level_panel, level_rect)
        level_label = self._text(f"ДЕРЕВНЯ {village}" if mode == "endless" else f"УРОВЕНЬ {level}", 23, ds.CREAM)
        screen.blit(level_label, level_label.get_rect(center=level_rect.center))

        self.tip.draw(screen)
        image = self.pause_image
        if hover_pause:
            image = pygame.transform.smoothscale(image, (72, 74))
        screen.blit(image, image.get_rect(center=self.pause_rect.center))

    def _panel_with_title(self, screen: pygame.Surface, title: str,
                          center_y: int = 360) -> pygame.Rect:
        screen.blit(self.dim, (0, 0))
        rect = self.panel.get_rect(center=(ds.SCREEN_WIDTH // 2, center_y))
        screen.blit(self.panel, rect)
        heading = outlined_text(self.assets.font(50), title, ds.CREAM,
                                ds.WOOD_DARK, 4)
        screen.blit(heading, heading.get_rect(center=(rect.centerx, rect.y + 62)))
        return rect

    def _lines(self, screen: pygame.Surface, lines: List[str], top: int,
               size: int = 30, color: Color = ds.TEXT_DARK) -> None:
        for i, line in enumerate(lines):
            image = self._text(line, size, color)
            screen.blit(image, image.get_rect(center=(ds.SCREEN_WIDTH // 2,
                                                      top + i * (size + 12))))

    def draw_start(self, screen: pygame.Surface, now: float,
                   mouse: Tuple[int, int], mode: str = "village", best: int = 0) -> None:
        """Выбор цели перед началом игры, мышью или клавишами 1 / 2."""
        rect = self._panel_with_title(screen, ds.GAME_TITLE)
        bob = 4 * math.sin(now * 3)
        screen.blit(self.head_big, self.head_big.get_rect(center=(490, 255 + bob)))
        screen.blit(self.switch_big, self.switch_big.get_rect(center=(790, 275 - bob)))
        box = self.skins_button
        pygame.draw.rect(screen, ds.LEAF_GREEN if box.collidepoint(mouse) else ds.DEEP_TEAL,
                         box, border_radius=16)
        label = self._text("Выбрать змейку · C", 22, ds.CREAM)
        screen.blit(label, label.get_rect(center=box.center))
        for key, box in self.mode_rects.items():
            selected = mode == key
            fill = ds.DEEP_TEAL if selected else (228, 211, 171)
            pygame.draw.rect(screen, fill, box, border_radius=18)
            pygame.draw.rect(screen, ds.GOLD if selected else ds.WOOD,
                             box, 3 if selected or box.collidepoint(mouse) else 1,
                             border_radius=18)
            color = ds.CREAM if selected else ds.TEXT_DARK
            title = "Спасти деревню" if key == "village" else "Бесконечная ночь"
            detail = "Собери 12 выключателей" if key == "village" else "До самоукуса · на рекорд"
            footer = "1 · " if key == "village" else "2 · "
            footer += "Выбрано" if selected else "Выбрать"
            for text, y, size in ((title, box.y + 26, 25), (detail, box.y + 61, 19),
                                  (footer, box.y + 92, 16)):
                label = self._text(text, size, color)
                screen.blit(label, label.get_rect(center=(box.centerx, y)))
        hint = "Стрелки / WASD / свайпы · Enter — играть"
        if mode == "endless":
            hint = f"Рекорд: {best} · 12 выключателей — новая деревня"
        self._lines(screen, [hint], 508, 19)
        self.buttons["start"].draw(screen, self.buttons["start"].rect.collidepoint(mouse))

    def draw_pause(self, screen: pygame.Surface, mouse: Tuple[int, int]) -> None:
        """Экран паузы."""
        rect = self._panel_with_title(screen, "Пауза")
        screen.blit(self.head_big, self.head_big.get_rect(
            center=(rect.centerx, rect.y + 190)))
        self._lines(screen, ["Питоша отдыхает.", "Нажми «Продолжить»!"], 392, 30)
        button = self.buttons["resume"]
        button.draw(screen, button.rect.collidepoint(mouse))
        self.buttons["menu"].draw(screen, self.buttons["menu"].rect.collidepoint(mouse))

    def draw_win(self, screen: pygame.Surface, score: int, now: float,
                 mouse: Tuple[int, int], state: str = "won", best: int = 0, new_skin: str = "") -> None:
        """Итог обычной или бесконечной партии."""
        title = "Ура! Ты победил!" if state == "won" else "Всё поле твоё!" if state == "full" else "Хорошая попытка!"
        rect = self._panel_with_title(screen, title)
        screen.blit(self.switch_off_big, self.switch_off_big.get_rect(
            center=(rect.centerx + 120, rect.y + 188)))
        bounce = abs(math.sin(now * 4)) * 10
        screen.blit(self.head_big, self.head_big.get_rect(
            center=(rect.centerx - 130, rect.y + 190 - bounce)))
        lines = (["Вся деревня бережёт энергию!", f"Выключатели: {score} из {ds.WIN_SCORE}"]
                 if state == "won" else
                 [f"Выключатели: {score}", f"Личный рекорд: {best}"])
        self._lines(screen, lines, 390, 29, (52, 86, 40))
        if new_skin:
            self._lines(screen, [f"Новая змейка: {new_skin}! Выбери её в меню."], 480, 20)
        button = self.buttons["again"]
        button.draw(screen, button.rect.collidepoint(mouse))
        self.buttons["menu"].draw(screen, self.buttons["menu"].rect.collidepoint(mouse))
