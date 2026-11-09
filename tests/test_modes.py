"""Правила двух режимов и переходы между экранами."""

import pygame
import pytest


@pytest.fixture
def game(_the_snake):
    return _the_snake.Game()


def test_endless_continues_to_next_village_and_keeps_best(game):
    game.select_mode('endless')
    game.start()
    for _ in range(12):
        game.collect_switch()
    assert game.state == 'playing'
    assert game.score == game.best == 12
    assert game.village == 2
    assert sum(game.background.target) == 12
    assert game.snake.length == 13
    game.collect_switch()
    assert sum(game.background.target) == 11
    game.restart()
    assert game.mode == 'endless'
    assert game.score == 0 and game.best == 13
    assert game.village == 1


@pytest.mark.parametrize('mode, state', [('endless', 'lost'), ('village', 'playing')])
def test_self_collision_ends_only_endless(game, mode, state):
    game.select_mode(mode)
    game.start()
    game.snake.positions = [(2, 2), (2, 3), (3, 3), (3, 2), (4, 2)]
    game.snake.length = 5
    game.snake.direction = (1, 0)
    game.apple.position = (10, 10)
    game.step()
    assert game.state == state
    if mode == 'endless':
        positions = game.snake.positions.copy()
        game.update(1)
        assert game.snake.positions == positions
    else:
        assert game.snake.length == 1


def test_full_board_finishes_without_spawning(game, _the_snake, monkeypatch):
    game.select_mode('endless')
    game.start()
    game.snake.positions = list(_the_snake.ALL_CELLS)
    monkeypatch.setattr(game.snake, 'move', lambda: None)
    game.step()
    assert game.state == 'full'


def test_menu_and_keyboard_preserve_music_and_select_mode(game, _the_snake):
    music = game.music
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))
    _the_snake.handle_keys(game)
    assert game.mode == 'endless' and game.state == 'start'
    _the_snake.handle_click(game, game.ui.buttons['start'].rect.center)
    game.toggle_pause()
    _the_snake.handle_click(game, game.ui.buttons['menu'].rect.center)
    assert game.state == 'start' and game.music is music
    _the_snake.handle_click(game, game.ui.mode_rects['village'].center)
    assert game.mode == 'village'


def test_speed_is_capped_and_village_does_not_affect_record(game):
    game.start()
    game.collect_switch()
    assert game.best == 0
    game.level = 999
    assert game.step_ms == 112
