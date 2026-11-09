"""Проверки музыки с реальным декодированием треков SDL mixer."""

import pygame
import pytest


@pytest.fixture
def game(_the_snake):
    instance = _the_snake.Game()
    yield instance
    if pygame.mixer.get_init():
        pygame.mixer.music.stop()
        pygame.mixer.music.set_endevent()
    pygame.event.clear()


def test_all_tracks_decode_and_playlist_wraps(game):
    player = game.music
    assert not player.playing
    for expected in (1, 2, 0):
        player.change_track(1)
        assert player.index == expected
        assert player.playing and not player.error
        assert pygame.mixer.music.get_busy()
    player.change_track(-1)
    assert player.index == 2


def test_music_pause_preserves_time_and_game_state(game, monkeypatch):
    tick = [1000]
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: tick[0])
    player = game.music
    player.play()
    tick[0] += 2000
    player.toggle()
    assert player.position == 2
    tick[0] += 5000
    assert player.position == 2
    player.toggle()
    tick[0] += 1000
    assert player.position == 3
    assert game.state == "start"
    game.start()
    game.toggle_pause()
    assert player.playing
    game.restart()
    assert player.position == 3


def test_track_advances_only_while_playing(game, monkeypatch):
    tick = [1000]
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: tick[0])
    player = game.music
    player.play()
    tick[0] += int(player.track_duration * 1000) + 1
    player.update(0.016)
    assert player.index == 1 and player.playing
    player.toggle()
    tick[0] += 999999
    player.update(0.016)
    assert player.index == 1 and not player.playing


def test_player_click_does_not_start_game_or_swipe(game, _the_snake):
    pygame.event.post(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1,
        pos=game.music.buttons["next"].center,
    ))
    _the_snake.handle_keys(game)
    assert game.state == "start"
    assert game.swipe_from is None
    assert game.music.index == 1 and game.music.playing
    player = game.music
    player.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=player.volume_rect.center,
    ))
    player.handle_event(pygame.event.Event(
        pygame.MOUSEMOTION, pos=(0, 0),
    ))
    assert player.volume == 0
    player.handle_event(pygame.event.Event(
        pygame.MOUSEMOTION, pos=(2000, 0),
    ))
    assert player.volume == 1
    player.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONUP, button=1, pos=(2000, 0),
    ))
    assert not player.dragging


def test_missing_track_keeps_game_running(game, monkeypatch, tmp_path):
    import design

    monkeypatch.setattr(design, "ASSETS_DIR", tmp_path)
    game.music.play()
    assert game.music.error and not game.music.playing
    game.update(0.016)
    game.draw(pygame.display.get_surface())
