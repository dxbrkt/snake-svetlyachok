"""Проверки непрерывного тела при переходах через границы поля."""

import math

import pygame
import pytest


@pytest.mark.parametrize('positions,direction', [
    ([(0, 8), (30, 8), (29, 8)], (1, 0)),
    ([(15, 0), (15, 16), (15, 15)], (0, 1)),
    ([(30, 8), (0, 8), (1, 8)], (-1, 0)),
    ([(15, 16), (15, 0), (15, 1)], (0, -1)),
])
def test_wrap_does_not_draw_across_board(_the_snake, positions, direction):
    from visuals import Assets, SnakeRenderer
    import design as ds

    snake = _the_snake.Snake()
    snake.positions = positions
    snake.previous_positions = positions[:]
    snake.direction = direction
    renderer = SnakeRenderer(Assets())
    path = renderer._path(snake, 1)
    assert sum(math.dist(a, b) for a, b in zip(path, path[1:])) < 100
    field = pygame.Surface((ds.FIELD_WIDTH, ds.FIELD_HEIGHT), pygame.SRCALPHA)
    renderer.draw(field, snake, 1)
    assert field.get_at((ds.FIELD_WIDTH // 2, ds.FIELD_HEIGHT // 2)).a == 0
    assert pygame.mask.from_surface(field).count() > 100
