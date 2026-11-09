"""Облики меняют внешность, сохраняют правила и открываются за достижения."""

import pygame
import pytest
from snake_art import SKINS, make_head


@pytest.fixture
def game(_the_snake):
    return _the_snake.Game()


def test_free_skins_and_locked_selection(game):
    assert game.unlocked_skins == {'classic', 'berry'}
    game.open_skins()
    game.choose_skin('dragon')
    assert game.skin == 'classic'
    speed = game.step_ms
    game.choose_skin('berry')
    assert game.skin == game.snake_renderer.skin == 'berry'
    assert game.step_ms == speed
    game.show_menu()
    game.restart()
    assert game.skin == 'berry'
    game.choose_skin('classic')
    assert game.skin == 'berry'  # No cosmetic mutation during a run.


def test_village_reward_is_permanent_and_separate_from_endless(game):
    game.start()
    for _ in range(12):
        game.collect_switch()
    assert game.new_skin == 'Светлячок'
    assert 'firefly' in game.unlocked_skins
    assert 'dragon' not in game.unlocked_skins
    game.show_menu()
    assert game.village_won
    game.open_skins()
    game.choose_skin('firefly')
    assert game.skin == 'firefly'


def test_dragon_unlocks_at_24_in_one_endless_run(game):
    game.select_mode('endless')
    game.start()
    for _ in range(23):
        game.collect_switch()
    assert 'dragon' not in game.unlocked_skins
    game.restart()
    game.collect_switch()
    assert 'dragon' not in game.unlocked_skins
    for _ in range(23):
        game.collect_switch()
    assert 'dragon' in game.unlocked_skins
    assert 'firefly' not in game.unlocked_skins
    assert game.new_skin == 'Дракончик'


def test_skin_input_does_not_start_game_and_keeps_radio(game, _the_snake):
    radio = game.music
    _the_snake.handle_click(game, game.ui.skins_button.center)
    assert game.state == 'skins'
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))
    _the_snake.handle_keys(game)
    assert game.skin == 'berry' and game.state == 'skins'
    _the_snake.handle_click(game, game.ui.buttons['skin_back'].rect.center)
    assert game.state == 'start' and game.music is radio


@pytest.mark.parametrize('skin', SKINS)
def test_skin_has_blink_and_wraps_without_streaks(game, skin):
    assert pygame.image.tobytes(make_head(False, skin), 'RGBA') != pygame.image.tobytes(make_head(True, skin), 'RGBA')
    game.snake_renderer.set_skin(skin)
    game.snake.positions = [(0, 8), (30, 8), (29, 8)]
    game.snake.previous_positions = game.snake.positions[:]
    field = pygame.Surface((868, 476), pygame.SRCALPHA)
    game.snake_renderer.draw(field, game.snake, 1)
    assert field.get_at((434, 238)).a == 0
