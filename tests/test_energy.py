"""Проверки смысла игры: свет выключается и остаётся выключенным."""

import pytest


@pytest.fixture
def game(_the_snake):
    return _the_snake.Game()


def test_party_starts_with_all_windows_lit(game):
    assert game.score == game.light.off_count == 0
    assert all(value == 1 for value in game.background.ramp)
    assert all(value == 1 for value in game.background.target)


def test_each_switch_turns_off_one_window_until_restart(game):
    game.start()
    for count in range(1, 13):
        previous = game.background.target.copy()
        game.collect_switch()
        assert game.score == game.light.off_count == count
        assert sum(game.background.target) == 12 - count
        assert all(new <= old for new, old in zip(game.background.target, previous))
        game.background.update(1)
        assert game.background.ramp == game.background.target

    assert game.state == "celebrating"
    assert game.light.is_off
    game.update(3)
    assert game.state == "won"
    game.update(60)
    assert sum(game.background.ramp) == 0
    assert game.light.is_off
    assert not game.light_effect.active

    game.restart()
    assert game.score == game.light.off_count == 0
    assert sum(game.background.ramp) == 12


def test_light_does_not_return_after_five_seconds(game):
    game.start()
    game.collect_switch()
    # Keep the next switch away from the straight path during this lighting test.
    game.apple.position = (0, 0)
    for _ in range(120):
        game.update(0.05)
    assert game.light.off_count == 1
    assert sum(game.background.ramp) == 11
    assert not game.light_effect.active
    assert "сбережено" in game.ui.tip.text


def test_day_night_morning_cycle_repeats(game):
    light = game.light
    assert light.darkness == 0
    for count in (1, 2):
        game.collect_switch()
        light.update(0.8)
        assert light.darkness == 1
        light.update(4.2)
        assert light.darkness == 1
        light.update(0.75)
        assert 0 < light.darkness < 1
        light.update(0.75)
        assert light.darkness == 0
        assert light.off_count == count


def test_pause_freezes_night_and_restart_returns_day(game):
    game.start()
    game.collect_switch()
    game.light.update(1)
    game.toggle_pause()
    remaining = game.light.remaining
    game.update(10)
    assert game.light.remaining == remaining
    assert game.light.darkness == 1
    game.restart()
    assert game.light.darkness == 0
    assert game.light.remaining == 0
