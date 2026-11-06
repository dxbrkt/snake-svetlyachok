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
        self.head = load("characters/snake_head.png")
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
    """Состояние света в мире: выключается на 5 секунд, затем включается сам.

    Время считается по dt (а не sleep), поэтому игра не зависает, а на паузе
    отсчёт замирает. Повторный выключатель заново запускает 5 секунд.
    """

    def __init__(self) -> None:
        """Свет включён."""
        self.remaining = 0.0   # сколько секунд свет ещё будет выключен
        self.darkness = 0.0    # 0 — светло, 1 — ночь (меняется плавно)

    @property
    def is_off(self) -> bool:
        """Идёт ли сейчас отсчёт выключенного света."""
        return self.remaining > 0

    @property
    def countdown(self) -> int:
        """Целые секунды для индикатора: 5, 4, 3, 2, 1, 0."""
        return max(0, min(5, math.ceil(self.remaining - 1e-9)))

    @property
    def fraction(self) -> float:
        """Какая доля времени выключения осталась (1.0 → 0.0)."""
        return clamp01(self.remaining * 1000 / ds.LIGHT_OFF_MS)

    def switch_off(self) -> None:
        """Выключить свет (или продлить выключение заново на 5 секунд)."""
        self.remaining = ds.LIGHT_OFF_MS / 1000

    def force_on(self) -> None:
        """Сразу начать возвращать свет."""
        self.remaining = 0.0

    def reset(self) -> None:
        """Мгновенно вернуть дневное состояние (новая партия)."""
        self.remaining = 0.0
        self.darkness = 0.0

    def update(self, dt: float) -> Optional[str]:
        """Продвинуть время; вернуть "on", когда свет только что включился."""
        event = None
        if self.remaining > 0:
            self.remaining = max(0.0, self.remaining - dt)
            if self.remaining == 0:
                event = "on"
        if self.remaining > 0:
            self.darkness = min(1.0, self.darkness + dt / ds.LIGHT_FADE_OUT)
        else:
            self.darkness = max(0.0, self.darkness - dt / ds.LIGHT_FADE_IN)
        return event


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
        self._cool = build_glow(80, (150, 205, 255), 200)
        self._spark = build_glow(5, (255, 244, 190), 255)
        self.born = 0.0
        self.particles = particles

    def respawn(self, now: float) -> None:
        """Выключатель появился в новом месте — запустить анимацию появления."""
        self.born = now

    def draw(self, field: pygame.Surface, cell: Tuple[int, int], now: float,
             darkness: float = 0.0) -> None:
        """Нарисовать выключатель в клетке поля (в темноте он светится ярче)."""
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

        if darkness > 0.01:
            cool = scaled(self._cool)
            cool.set_alpha(int(255 * darkness * (0.65 + 0.35 * wave)))
            field.blit(cool, cool.get_rect(center=(cx, cy)))
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
class SnakeRenderer:
    """Рисует змейку Питошу: голова крупнее тела, плавное движение."""

    def __init__(self, assets: Assets) -> None:
        """Заранее повернуть спрайты во все стороны."""
        def variants(image: pygame.Surface) -> Dict[Tuple[int, int], pygame.Surface]:
            return {
                (1, 0): image,
                (-1, 0): pygame.transform.flip(image, True, False),
                (0, -1): pygame.transform.rotate(image, 90),
                (0, 1): pygame.transform.rotate(image, -90),
            }

        self.head = variants(assets.head)
        self.body = variants(assets.body)
        self.tail = variants(assets.tail)
        self.bounce_t = ds.HEAD_BOUNCE_TIME

    def react(self) -> None:
        """Радостное подпрыгивание головы."""
        self.bounce_t = 0.0

    def update(self, dt: float) -> None:
        """Продвинуть анимацию реакции."""
        if self.bounce_t < ds.HEAD_BOUNCE_TIME:
            self.bounce_t += dt

    @staticmethod
    def _unwrap(delta: int, size: int) -> int:
        if delta > 1:
            return delta - size
        if delta < -1:
            return delta + size
        return delta

    def pixel_position(self, snake, index: int, progress: float) -> Point:
        """Плавная позиция сегмента между двумя шагами игры (в пикселях поля)."""
        cur = snake.positions[index]
        prev = (
            snake.previous_positions[index]
            if index < len(snake.previous_positions)
            else cur
        )
        dx = self._unwrap(cur[0] - prev[0], ds.GRID_WIDTH)
        dy = self._unwrap(cur[1] - prev[1], ds.GRID_HEIGHT)
        remain = 1 - progress
        return (
            (cur[0] + 0.5 - dx * remain) * ds.GRID_SIZE,
            (cur[1] + 0.5 - dy * remain) * ds.GRID_SIZE,
        )

    def _direction_to(self, snake, index: int) -> Tuple[int, int]:
        """Направление от сегмента к предыдущему (ближе к голове)."""
        a, b = snake.positions[index], snake.positions[index - 1]
        dx = self._unwrap(b[0] - a[0], ds.GRID_WIDTH)
        dy = self._unwrap(b[1] - a[1], ds.GRID_HEIGHT)
        return (dx, dy) if (dx, dy) in self.body else snake.direction

    def draw(self, field: pygame.Surface, snake, progress: float) -> None:
        """Нарисовать змейку от хвоста к голове."""
        count = len(snake.positions)
        for index in range(count - 1, 0, -1):
            cx, cy = self.pixel_position(snake, index, progress)
            direction = self._direction_to(snake, index)
            if index == count - 1 and count >= 3:
                away = (-direction[0], -direction[1])
                sprite = self.tail[away]
                cx += away[0] * 14
                cy += away[1] * 14
            else:
                sprite = self.body[direction]
            field.blit(sprite, sprite.get_rect(center=(cx, cy)))

        cx, cy = self.pixel_position(snake, 0, progress)
        direction = snake.direction
        sprite = self.head[direction]
        if self.bounce_t < ds.HEAD_BOUNCE_TIME:
            factor = 1 + 0.28 * math.sin(math.pi * self.bounce_t / ds.HEAD_BOUNCE_TIME)
            sprite = pygame.transform.smoothscale(
                sprite,
                (int(sprite.get_width() * factor), int(sprite.get_height() * factor)),
            )
        cx += direction[0] * 6
        cy += direction[1] * 6
        field.blit(sprite, sprite.get_rect(center=(cx, cy)))


# --- Фон с домиками ---------------------------------------------------------
class BackgroundRenderer:
    """Ночной мир с домиками: окна светятся, пока свет включён."""

    def __init__(self, assets: Assets) -> None:
        """Подготовить фон, окна, мерцающие звёзды и лёгкий туман."""
        self.background = assets.background
        self.windows = assets.windows
        self.ramp = [0.0] * len(self.windows)
        self.target = [0.0] * len(self.windows)
        self.starlight = pygame.transform.smoothscale(assets.star, (18, 20))
        self.stars = [
            (90, 76), (1160, 64), (1236, 214), (60, 250), (1100, 300),
            (500, 40), (860, 70), (330, 56),
        ]
        self.time = 0.0
        self.fog = pygame.transform.smoothscale(
            build_glow(150, (150, 205, 195), 46), (440, 150)
        )
        self.spill = build_glow(46, (255, 196, 80), 140)
        self._night = pygame.Surface((ds.SCREEN_WIDTH, ds.SCREEN_HEIGHT))
        self._night.fill(ds.NIGHT_COLOR)
        self._cool = pygame.Surface((ds.FIELD_WIDTH, ds.FIELD_HEIGHT))

    def set_lit(self, count: int) -> None:
        """Сколько окон должно гореть."""
        for i in range(len(self.target)):
            self.target[i] = 1.0 if i < count else 0.0

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
        """Нарисовать фон, мерцание звёзд и светящиеся окна (гаснут в темноте)."""
        screen.blit(self.background, (0, 0))
        daylight = 1 - darkness
        for i, pos in enumerate(self.stars):
            alpha = int(90 + 120 * math.sin(self.time * 1.4 + i * 1.7) ** 2)
            self.starlight.set_alpha(alpha)
            screen.blit(self.starlight, pos)
        for i, (image, pos, center) in enumerate(self.windows):
            ramp = self.ramp[i] * daylight
            if ramp <= 0.01:
                continue
            self.spill.set_alpha(int(255 * clamp01(ramp)))
            screen.blit(self.spill, self.spill.get_rect(center=center))
            glow = 1 + 0.4 * math.sin(clamp01(ramp) * math.pi) * (ramp < 1)
            image.set_alpha(int(min(255, 255 * ramp * min(glow, 1.0))
                                * (0.93 + 0.07 * math.sin(self.time * 2.3 + i))))
            screen.blit(image, pos)

    def draw_night(self, screen: pygame.Surface, darkness: float) -> None:
        """Полупрозрачный холодный синий слой ночи (не чёрная заливка)."""
        if darkness <= 0.01:
            return
        self._night.set_alpha(int(ds.NIGHT_ALPHA * darkness))
        screen.blit(self._night, (0, 0))
        self._cool.fill(tuple(int(c * darkness) for c in ds.NIGHT_COOL_ADD))
        screen.blit(self._cool, ds.FIELD_RECT[:2], special_flags=pygame.BLEND_RGB_ADD)

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
        self.panel_off = wood_panel(self.SIZE, 22, (52, 84, 124), ds.WOOD, seed=21)
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
        """Нарисовать индикатор в левом нижнем углу."""
        rect = self.rect
        screen.blit(self.panel_on, rect)
        if light.darkness > 0.01:
            self.panel_off.set_alpha(int(255 * light.darkness))
            screen.blit(self.panel_off, rect)

        night = light.darkness > 0.45
        icon = self.icon_off if night else self.icon_on
        screen.blit(icon, icon.get_rect(center=(rect.x + 40, rect.centery - 3)))

        if not night:
            label = self._text("СВЕТ ВКЛЮЧЁН", 18, (52, 86, 40))
            screen.blit(label, label.get_rect(midleft=(rect.x + 74, rect.centery - 4)))
            return

        label = self._text("СВЕТ ВЫКЛЮЧЕН", 18, ds.CREAM)
        screen.blit(label, label.get_rect(midleft=(rect.x + 74, rect.y + 26)))
        bar = pygame.Rect(rect.x + 74, rect.y + 44, 150, 10)
        pygame.draw.rect(screen, (30, 52, 88), bar, border_radius=5)
        fill = bar.copy()
        fill.width = int(bar.width * light.fraction)
        if fill.width > 2:
            pygame.draw.rect(screen, ds.GOLD, fill, border_radius=5)
        badge = (rect.right - 30, rect.centery - 2)
        pygame.draw.circle(screen, ds.WOOD, badge, 22)
        pygame.draw.circle(screen, ds.CREAM, badge, 18)
        number = self._text(str(light.countdown), 28, (150, 70, 10))
        screen.blit(number, number.get_rect(center=(badge[0], badge[1] - 2)))


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
        self.light_indicator = LightIndicator(assets)
        self.click_banner = Banner(assets, ds.CLICK_BANNER, ds.CLICK_BANNER_TIME,
                                   (14, 30, 66))
        self.switch_big = pygame.transform.smoothscale(assets.switch_on, (96, 107))
        self.pause_image = pygame.transform.smoothscale(assets.pause, (66, 68))
        self.pause_rect = self.pause_image.get_rect(center=(1196, 660))
        self.dim = pygame.Surface((ds.SCREEN_WIDTH, ds.SCREEN_HEIGHT),
                                  pygame.SRCALPHA)
        self.dim.fill((4, 22, 30, 175))
        self.panel = wood_panel((700, 500), 34, ds.CREAM, ds.WOOD, seed=9)
        self.bubble = SpeechBubble(assets)
        self.bump = ds.COUNTER_BUMP_TIME
        self.glow = build_glow(120, ds.GOLD, 200)
        self.bulb_big = pygame.transform.smoothscale(assets.bulb, (110, 120))
        self.head_big = pygame.transform.smoothscale(assets.head, (176, 127))
        self.buttons = {
            "start": Button(assets, "Играть", (640, 566)),
            "resume": Button(assets, "Продолжить", (640, 566)),
            "again": Button(assets, "Играть снова", (640, 566), 340),
        }
        self.texts: Dict[Tuple[str, int, Color], pygame.Surface] = {}

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
        """Анимация счётчика при подборе лампочки."""
        self.bump = 0.0

    def update(self, dt: float) -> None:
        """Продвинуть анимации интерфейса."""
        self.tip.update(dt)
        self.bubble.update(dt)
        self.click_banner.update(dt)
        if self.bump < ds.COUNTER_BUMP_TIME:
            self.bump += dt

    def draw_hud(self, screen: pygame.Surface, score: int, level: int,
                 hover_pause: bool, light: LightController) -> None:
        """Верхняя панель, индикатор света, подсказка и кнопка паузы."""
        screen.blit(self.leaf_big, (26, 24))
        screen.blit(self.title, (84, 22))

        rect = self.counter_panel.get_rect(center=(ds.SCREEN_WIDTH // 2, 48))
        screen.blit(self.counter_panel, rect)
        label = self._text("ВЫКЛЮЧАТЕЛИ", 27, ds.TEXT_DARK)
        screen.blit(label, label.get_rect(midleft=(rect.x + 26, rect.centery - 3)))
        number = self._text(f"{score}", 40, (150, 70, 10))
        if self.bump < ds.COUNTER_BUMP_TIME:
            k = 1 + 0.35 * math.sin(math.pi * self.bump / ds.COUNTER_BUMP_TIME)
            number = pygame.transform.smoothscale(
                number, (int(number.get_width() * k), int(number.get_height() * k))
            )
        screen.blit(number, number.get_rect(center=(rect.right - 52, rect.centery - 3)))

        level_rect = self.level_panel.get_rect(topright=(ds.SCREEN_WIDTH - 36, 22))
        screen.blit(self.level_panel, level_rect)
        level_label = self._text(f"УРОВЕНЬ {level}", 27, ds.CREAM)
        screen.blit(level_label, level_label.get_rect(center=level_rect.center))

        self.light_indicator.draw(screen, light)
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
                   mouse: Tuple[int, int]) -> None:
        """Стартовый экран: знакомство со змейкой."""
        rect = self._panel_with_title(screen, ds.GAME_TITLE)
        bob = 4 * math.sin(now * 3)
        screen.blit(self.head_big, self.head_big.get_rect(
            center=(rect.centerx - 150, rect.y + 188 + bob)))
        screen.blit(self.glow, self.glow.get_rect(center=(rect.centerx + 140,
                                                         rect.y + 190)))
        screen.blit(self.switch_big, self.switch_big.get_rect(
            center=(rect.centerx + 140, rect.y + 190 - bob)))
        self._lines(screen, [f"Привет! Я {ds.SNAKE_NAME}.",
                             "Собирай выключатели —",
                             "выключай свет и береги энергию!"], 392, 28)
        hint = self._text("Управление: стрелки на клавиатуре", 22, (110, 80, 40))
        screen.blit(hint, hint.get_rect(center=(rect.centerx, rect.bottom - 100)))
        self.buttons["start"].draw(screen, self.buttons["start"].rect.collidepoint(mouse))

    def draw_pause(self, screen: pygame.Surface, mouse: Tuple[int, int]) -> None:
        """Экран паузы."""
        rect = self._panel_with_title(screen, "Пауза")
        screen.blit(self.head_big, self.head_big.get_rect(
            center=(rect.centerx, rect.y + 190)))
        self._lines(screen, ["Питоша отдыхает.", "Нажми «Продолжить»!"], 392, 30)
        button = self.buttons["resume"]
        button.draw(screen, button.rect.collidepoint(mouse))

    def draw_win(self, screen: pygame.Surface, score: int, now: float,
                 mouse: Tuple[int, int]) -> None:
        """Экран победы."""
        rect = self._panel_with_title(screen, "Ура! Ты победил!")
        pulse = 1 + 0.06 * math.sin(now * 3)
        glow = pygame.transform.smoothscale(
            self.glow, (int(240 * pulse), int(240 * pulse)))
        screen.blit(glow, glow.get_rect(center=(rect.centerx + 120, rect.y + 190)))
        screen.blit(self.bulb_big, self.bulb_big.get_rect(
            center=(rect.centerx + 120, rect.y + 188)))
        bounce = abs(math.sin(now * 4)) * 10
        screen.blit(self.head_big, self.head_big.get_rect(
            center=(rect.centerx - 130, rect.y + 190 - bounce)))
        self._lines(screen, ["Ты настоящий друг энергии!",
                             f"Собрано выключателей: {score}"], 390, 32,
                    (52, 86, 40))
        button = self.buttons["again"]
        button.draw(screen, button.rect.collidepoint(mouse))
