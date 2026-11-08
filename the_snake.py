"""Игра «Изгиб Питона» — Питоша собирает выключатели и гасит свет.

Игровая механика классическая: змейка собирает выключатели, растёт и не должна
кусать свой хвост. Оформление и эффекты вынесены в visuals.py, а настройки
дизайна — в design.py.
"""

from __future__ import annotations

import asyncio
import sys
from random import choice
from typing import ClassVar, Dict, Optional, Tuple

import pygame

import design as ds
from music import MusicPlayer
from design import (
    BOARD_BACKGROUND_COLOR,
    FPS,
    GRID_HEIGHT,
    GRID_SIZE,
    GRID_WIDTH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from visuals import (
    Assets,
    BackgroundRenderer,
    GameUI,
    LightController,
    LightRayEffect,
    ParticleSystem,
    SnakeRenderer,
    SwitchClickEffect,
    SwitchRenderer,
)


SCREEN_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)
SWIPE_DISTANCE = 28  # на сколько пикселей нужно провести пальцем

GREEN = (104, 201, 59)
GOLD = ds.GOLD

UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

START_LENGTH = 1
START_DIRECTION = RIGHT
WINDOW_TITLE = ds.WINDOW_TITLE
CENTER_POSITION = (GRID_WIDTH // 2, GRID_HEIGHT // 2)

ALL_CELLS = {
    (x, y)
    for x in range(GRID_WIDTH)
    for y in range(GRID_HEIGHT)
}
# Выключатель не появляется на самом краю, чтобы рамка поля не обрезала его.
INNER_CELLS = {
    (x, y)
    for x in range(1, GRID_WIDTH - 1)
    for y in range(1, GRID_HEIGHT - 1)
}

KEY_ALIASES = {
    pygame.K_w: pygame.K_UP,
    pygame.K_s: pygame.K_DOWN,
    pygame.K_a: pygame.K_LEFT,
    pygame.K_d: pygame.K_RIGHT,
}
ARROW_KEYS = (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT)

pygame.init()
IS_WEB = sys.platform == "emscripten"
try:
    screen = pygame.display.set_mode(
        SCREEN_SIZE, 0 if IS_WEB else pygame.SCALED
    )
except pygame.error:
    screen = pygame.display.set_mode(SCREEN_SIZE)
clock = pygame.time.Clock()


class GameObject:
    """Базовый класс игровых объектов."""

    def __init__(
        self,
        position: Tuple[int, int] = CENTER_POSITION,
        body_color: Tuple[int, int, int] = BOARD_BACKGROUND_COLOR,
    ) -> None:
        """Инициализировать игровой объект.

        Args:
            position: Позиция объекта на игровом поле.
            body_color: Цвет объекта в формате RGB.
        """
        self.position = position
        self.body_color = body_color

    @staticmethod
    def _get_cell_rect(position: Tuple[int, int]) -> pygame.Rect:
        """Преобразовать координаты клетки в прямоугольник Pygame.

        Args:
            position: Координаты клетки на игровом поле.

        Returns:
            Прямоугольник для отрисовки клетки.
        """
        return pygame.Rect(
            position[0] * GRID_SIZE,
            position[1] * GRID_SIZE,
            GRID_SIZE,
            GRID_SIZE,
        )

    def draw_cell(
        self,
        surface: pygame.Surface,
        position: Tuple[int, int],
        color: Tuple[int, int, int],
    ) -> None:
        """Отрисовать одну клетку игрового поля.

        Args:
            surface: Поверхность Pygame для рисования.
            position: Координаты клетки.
            color: Цвет клетки.
        """
        pygame.draw.rect(surface, color, self._get_cell_rect(position),
                         border_radius=8)

    def draw(self, surface: pygame.Surface) -> None:
        """Отрисовать объект на поверхности.

        Args:
            surface: Поверхность Pygame для рисования.
        """
        pass


class Apple(GameObject):
    """Лампочка — то, что собирает змейка (бывшее яблоко)."""

    def __init__(
        self,
        occupied_positions: Optional[set[Tuple[int, int]]] = None,
    ) -> None:
        """Создать лампочку в случайной свободной клетке.

        Args:
            occupied_positions: Клетки, занятые змейкой.
        """
        super().__init__(body_color=GOLD)
        self.randomize_position(occupied_positions)

    def randomize_position(
        self,
        occupied_positions: Optional[set[Tuple[int, int]]] = None,
    ) -> None:
        """Установить лампочку в случайную свободную клетку.

        Args:
            occupied_positions: Клетки, занятые змейкой.
        """
        occupied = occupied_positions or set()
        free_cells = tuple(INNER_CELLS - occupied) or tuple(ALL_CELLS - occupied)
        self.position = choice(free_cells) if free_cells else CENTER_POSITION

    def draw(self, surface: pygame.Surface) -> None:
        """Нарисовать простую лампочку-кружок (запасной вариант без графики).

        Args:
            surface: Поверхность Pygame для рисования.
        """
        pygame.draw.circle(
            surface, self.body_color,
            self._get_cell_rect(self.position).center, GRID_SIZE // 2,
        )


class Snake(GameObject):
    """Класс змейки."""

    DIRECTION_MAP: ClassVar[
        Dict[Tuple[int, int, int], Tuple[int, int]]
    ] = {
        (pygame.K_UP, *UP): UP,
        (pygame.K_UP, *DOWN): DOWN,
        (pygame.K_UP, *LEFT): UP,
        (pygame.K_UP, *RIGHT): UP,
        (pygame.K_DOWN, *UP): UP,
        (pygame.K_DOWN, *DOWN): DOWN,
        (pygame.K_DOWN, *LEFT): DOWN,
        (pygame.K_DOWN, *RIGHT): DOWN,
        (pygame.K_LEFT, *UP): LEFT,
        (pygame.K_LEFT, *DOWN): LEFT,
        (pygame.K_LEFT, *LEFT): LEFT,
        (pygame.K_LEFT, *RIGHT): RIGHT,
        (pygame.K_RIGHT, *UP): RIGHT,
        (pygame.K_RIGHT, *DOWN): RIGHT,
        (pygame.K_RIGHT, *LEFT): LEFT,
        (pygame.K_RIGHT, *RIGHT): RIGHT,
    }

    def __init__(self) -> None:
        """Инициализировать змейку."""
        super().__init__(position=CENTER_POSITION, body_color=GREEN)
        self.length = START_LENGTH
        self.positions = [self.position]
        self.previous_positions = list(self.positions)
        self.direction = START_DIRECTION
        self.next_direction: Optional[Tuple[int, int]] = None
        self.record_length = START_LENGTH

    def _set_initial_state(self, head_position: Tuple[int, int]) -> None:
        """Установить начальное состояние змейки.

        Args:
            head_position: Позиция головы змейки.
        """
        self.position = head_position
        self.length = START_LENGTH
        self.positions = [head_position]
        self.previous_positions = list(self.positions)
        self.direction = START_DIRECTION
        self.next_direction = None

    def set_next_direction(self, key: int) -> None:
        """Сохранить следующее направление движения по нажатой клавише.

        Args:
            key: Код клавиши Pygame.
        """
        self.next_direction = self.DIRECTION_MAP.get(
            (key, *self.direction),
            self.direction,
        )

    def update_direction(self) -> None:
        """Обновить направление движения змейки."""
        if self.next_direction is not None:
            self.direction = self.next_direction
            self.next_direction = None

    def move(self) -> Optional[Tuple[int, int]]:
        """Переместить змейку на одну клетку.

        Returns:
            Координаты стёртой клетки хвоста, если хвост был сдвинут.
            Иначе возвращает None.
        """
        new_head = tuple(
            (position + delta) % size
            for position, delta, size in zip(
                self.get_head_position(),
                self.direction,
                (GRID_WIDTH, GRID_HEIGHT),
            )
        )

        self.positions.insert(0, new_head)
        self.position = new_head

        tail = None
        if len(self.positions) > self.length:
            tail = self.positions.pop()

        # Откуда пришёл каждый сегмент — нужно для плавной отрисовки.
        self.previous_positions = self.positions[1:] + [
            tail if tail is not None else self.positions[-1]
        ]

        return tail

    def draw(self, surface: pygame.Surface) -> None:
        """Нарисовать простую змейку из клеток (запасной вариант).

        Args:
            surface: Поверхность Pygame для рисования.
        """
        for segment in self.positions:
            self.draw_cell(surface, segment, self.body_color)

    def get_head_position(self) -> Tuple[int, int]:
        """Вернуть позицию головы змейки.

        Returns:
            Координаты головы змейки.
        """
        return self.positions[0]

    def get_positions_set(self) -> set[Tuple[int, int]]:
        """Вернуть множество клеток, занятых змейкой.

        Returns:
            Множество координат сегментов змейки.
        """
        return set(self.positions)

    def grow(self) -> None:
        """Увеличить длину змейки на один сегмент."""
        self.length += 1
        self.record_length = max(self.record_length, self.length)

    def has_self_collision(self) -> bool:
        """Проверить, столкнулась ли змейка сама с собой.

        Returns:
            True, если произошло столкновение, иначе False.
        """
        if self.length <= 2:
            return False
        return self.get_head_position() in self.positions[1:]

    def reset(self) -> None:
        """Сбросить змейку после самоукуса, оставив только голову."""
        self._set_initial_state(self.get_head_position())


def update_caption(snake: Snake, score: int = 0) -> None:
    """Обновить заголовок окна.

    Args:
        snake: Экземпляр змейки.
        score: Сколько выключателей собрано.
    """
    pygame.display.set_caption(
        f"{WINDOW_TITLE} | Выключатели: {score} | Длина: {snake.length}"
    )


class Game:
    """Партия: состояния, счёт, реакции персонажа и вся отрисовка."""

    def __init__(self) -> None:
        """Загрузить графику и подготовить партию на стартовом экране."""
        self.assets = Assets()
        self.background = BackgroundRenderer(self.assets)
        self.particles = ParticleSystem(self.assets.star)
        self.light_effect = LightRayEffect(self.assets, self.particles)
        self.switch_renderer = SwitchRenderer(self.assets, self.particles)
        self.click_effect = SwitchClickEffect(self.assets)
        self.light = LightController()
        self.snake_renderer = SnakeRenderer(self.assets)
        self.ui = GameUI(self.assets)
        self.music = MusicPlayer(self.assets)
        self.field_surface: Optional[pygame.Surface] = None
        self.now = 0.0
        self.swipe_from: Optional[Tuple[int, int]] = None
        self.state = "start"
        self.praise_index = 0
        self.tip_index = 0
        self.new_game()

    def new_game(self) -> None:
        """Подготовить новую партию (экран не меняется)."""
        self.snake = Snake()
        self.apple = Apple(occupied_positions=self.snake.get_positions_set())
        self.switch_renderer.respawn(self.now)
        self.score = 0
        self.level = 1
        self.step_acc = 0.0
        self.progress = 1.0
        self.idle_timer = 0.0
        self.finish_timer = 0.0
        self.light_effect.active = False
        self.light.reset()
        self.background.set_lit(len(self.background.windows))
        self.background.ramp[:] = self.background.target
        self.ui.tip.set_text(ds.DEFAULT_TIP)
        update_caption(self.snake, self.score)

    # --- Управление состояниями --------------------------------------------
    def start(self) -> None:
        """Начать игру со стартового экрана."""
        self.state = "playing"
        self.ui.bubble.say(ds.START_SPEECH, 2.4)

    def toggle_pause(self) -> None:
        """Поставить игру на паузу или продолжить."""
        if self.state == "playing":
            self.state = "paused"
        elif self.state == "paused":
            self.state = "playing"

    def restart(self) -> None:
        """Сыграть ещё раз."""
        self.new_game()
        self.state = "playing"
        self.ui.bubble.say(ds.START_SPEECH, 2.4)

    # --- Игровая логика -----------------------------------------------------
    @property
    def step_ms(self) -> int:
        """Сколько миллисекунд занимает один шаг змейки."""
        return ds.STEP_MS_BY_LEVEL[min(self.level, len(ds.STEP_MS_BY_LEVEL)) - 1]

    def head_pixel(self) -> Tuple[float, float]:
        """Позиция головы в пикселях поля."""
        return self.snake_renderer.pixel_position(self.snake, 0, self.progress)

    def step(self) -> None:
        """Сделать один шаг: движение, выключатель, укус хвоста."""
        snake = self.snake
        snake.update_direction()
        snake.move()

        if snake.get_head_position() == self.apple.position:
            self.collect_switch()

        if snake.has_self_collision():
            snake.reset()
            self.apple.randomize_position(snake.get_positions_set())
            self.switch_renderer.respawn(self.now)
            self.ui.bubble.say(ds.OOPS_SPEECH)
            update_caption(snake, self.score)

    def collect_switch(self) -> None:
        """Собрать выключатель и навсегда погасить ещё одно окно в партии."""
        snake = self.snake
        switch_px = (
            (self.apple.position[0] + 0.5) * GRID_SIZE,
            (self.apple.position[1] + 0.5) * GRID_SIZE,
        )
        snake.grow()
        self.score += 1
        self.light.switch_off()
        self.background.set_lit(ds.WIN_SCORE - self.score)
        self.level = min(
            len(ds.STEP_MS_BY_LEVEL), 1 + self.score // ds.LAMPS_PER_LEVEL
        )
        self.idle_timer = 0.0

        self.ui.pop_counter()
        self.snake_renderer.react()
        self.click_effect.trigger(switch_px)
        self.particles.burst(switch_px[0], switch_px[1], 14)
        self.light_effect.active = False
        self.ui.click_banner.show()

        self.praise_index = (self.praise_index + 1) % len(ds.PRAISES)
        self.ui.bubble.say(ds.PRAISES[self.praise_index])
        update_caption(snake, self.score)

        if self.score >= ds.WIN_SCORE:
            self.state = "celebrating"
            self.finish_timer = 2.4
            self.ui.tip.set_text(ds.WIN_TIP)
            return

        self.ui.tip.set_text(ds.PICK_TIPS[self.tip_index % len(ds.PICK_TIPS)])
        self.tip_index += 1
        self.apple.randomize_position(snake.get_positions_set())
        self.switch_renderer.respawn(self.now)

    def update(self, dt: float) -> None:
        """Обновить игру и все анимации за кадр длиной dt секунд."""
        self.now += dt
        self.music.update(dt)
        if self.state == "playing":
            self.step_acc += dt * 1000
            if self.step_acc >= self.step_ms:
                self.step_acc = (
                    self.step_acc - self.step_ms
                    if self.step_acc < self.step_ms * 2 else 0.0
                )
                self.step()
            self.progress = min(1.0, self.step_acc / self.step_ms)
            self.idle_timer += dt
            if self.idle_timer > ds.IDLE_SPEECH_AFTER:
                self.idle_timer = 0.0
                self.ui.bubble.say(ds.LOST_SPEECH)
        elif self.state == "celebrating":
            self.finish_timer -= dt
            if self.finish_timer <= 0:
                self.state = "won"

        self.background.update(dt)
        self.click_effect.update(dt)
        self.snake_renderer.update(dt)
        self.light_effect.update(dt, self.head_pixel())
        self.particles.update(dt)
        self.ui.update(dt)

    # --- Отрисовка ----------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        """Нарисовать кадр."""
        if self.field_surface is None:
            self.field_surface = surface.subsurface(ds.FIELD_RECT)
        field = self.field_surface
        mouse = pygame.mouse.get_pos()

        self.background.draw(surface)
        self.background.draw_mist(field)
        self.light_effect.draw_under(field)
        if self.state not in ("celebrating", "won"):
            self.switch_renderer.draw(field, self.apple.position, self.now)
        self.click_effect.draw(field)
        self.snake_renderer.draw(field, self.snake, self.progress)
        self.particles.draw(field)

        hover_pause = (
            self.state in ("playing", "paused")
            and self.ui.pause_rect.collidepoint(mouse)
        )
        self.ui.draw_hud(surface, self.score, self.level, hover_pause, self.light)
        self.light_effect.draw_banner(surface)
        self.ui.click_banner.draw(surface)
        head = self.head_pixel()
        self.ui.bubble.draw(surface, head)

        if self.state == "start":
            self.ui.draw_start(surface, self.now, mouse)
        elif self.state == "paused":
            self.ui.draw_pause(surface, mouse)
        elif self.state == "won":
            self.ui.draw_win(surface, self.score, self.now, mouse)

        self.music.draw(surface, mouse)


def quit_game() -> None:
    """Закрыть игру."""
    pygame.quit()
    raise SystemExit


def handle_keys(game: Game) -> None:
    """Обработать клавиатуру, мышь и закрытие окна.

    Args:
        game: Текущая партия.
    """
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            quit_game()

        if game.music.handle_event(event):
            if event.type == pygame.MOUSEBUTTONDOWN:
                game.swipe_from = None
            continue

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            handle_click(game, event.pos)
            game.swipe_from = event.pos
        elif event.type == pygame.MOUSEBUTTONUP:
            game.swipe_from = None
        elif event.type == pygame.MOUSEMOTION:
            handle_swipe(game, event.pos)

        if event.type != pygame.KEYDOWN:
            continue

        key = KEY_ALIASES.get(event.key, event.key)
        confirm = event.key in (pygame.K_RETURN, pygame.K_SPACE)

        if event.key == pygame.K_ESCAPE:
            if game.state == "playing":
                game.toggle_pause()
            else:
                quit_game()
        elif game.state == "start":
            if confirm or key in ARROW_KEYS:
                game.start()
                if key in ARROW_KEYS:
                    game.snake.set_next_direction(key)
        elif game.state == "playing":
            if event.key in (pygame.K_p, pygame.K_SPACE):
                game.toggle_pause()
            elif key in ARROW_KEYS:
                game.snake.set_next_direction(key)
        elif game.state == "paused":
            if confirm or event.key == pygame.K_p:
                game.toggle_pause()
        elif game.state == "won":
            if confirm:
                game.restart()


def handle_swipe(game: Game, position: Tuple[int, int]) -> None:
    """Повернуть змейку свайпом пальца (или мыши с зажатой кнопкой).

    Args:
        game: Текущая партия.
        position: Текущие координаты касания.
    """
    if game.swipe_from is None or game.state != "playing":
        return
    dx = position[0] - game.swipe_from[0]
    dy = position[1] - game.swipe_from[1]
    if max(abs(dx), abs(dy)) < SWIPE_DISTANCE:
        return
    if abs(dx) > abs(dy):
        key = pygame.K_RIGHT if dx > 0 else pygame.K_LEFT
    else:
        key = pygame.K_DOWN if dy > 0 else pygame.K_UP
    game.snake.set_next_direction(key)
    game.swipe_from = position


def handle_click(game: Game, position: Tuple[int, int]) -> None:
    """Обработать щелчок мышью по кнопкам.

    Args:
        game: Текущая партия.
        position: Координаты щелчка.
    """
    buttons = game.ui.buttons
    if game.state == "start" and buttons["start"].rect.collidepoint(position):
        game.start()
    elif game.state == "paused" and buttons["resume"].rect.collidepoint(position):
        game.toggle_pause()
    elif game.state == "won" and buttons["again"].rect.collidepoint(position):
        game.restart()
    elif game.state in ("playing", "paused") and game.ui.pause_rect.collidepoint(
        position
    ):
        game.toggle_pause()


def run_frame(game: Game) -> None:
    """Обработать ввод, обновить и нарисовать один кадр."""
    handle_keys(game)
    game.update(min(clock.get_time() / 1000, 0.05))
    game.draw(screen)
    pygame.display.update()


def main() -> None:
    """Запустить игру."""
    pygame.display.set_caption(WINDOW_TITLE)
    game = Game()

    while True:
        run_frame(game)
        clock.tick(FPS)


async def main_web() -> None:
    """Запустить игру в браузере (pygbag): цикл отдаёт управление браузеру."""
    pygame.display.set_caption(WINDOW_TITLE)
    game = Game()

    while True:
        run_frame(game)
        clock.tick(FPS)
        await asyncio.sleep(0)


if __name__ == "__main__":
    main()
