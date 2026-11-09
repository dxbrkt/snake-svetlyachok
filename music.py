"""Лесное радио: потоковое воспроизведение и компактный плеер Pygame."""

import math
import json
import sys
import pygame
import design as ds
from visuals import wood_panel, wrap_text

TRACKS = (
    ("Змейка", "snake.ogg", 102.36),
    ("Змейка и выключатель", "snake-and-switch.ogg", 132.432),
    ("Песня игры", "game-song.ogg", 174.984),
)

class MusicPlayer:
    """Плеер живёт независимо от паузы и перезапуска партии."""

    def __init__(self, assets):
        self.assets = assets
        self.rect = pygame.Rect(1090, 238, 174, 350)
        self.panel = wood_panel(self.rect.size, 24, ds.DEEP_TEAL, ds.WOOD, 31)
        self.index = 0
        self.playing = False
        self.loaded = False
        self.error = False
        self.volume = 0.55
        self.elapsed = 0.0
        self.started_at = 0
        self.phase = 0.0
        self.dragging = False
        
        # Переменные для контроля автоперехода без использования end_event
        self.track_duration = TRACKS[self.index][2]
        
        self.buttons = {
            "previous": pygame.Rect(1104, 440, 44, 44),
            "play": pygame.Rect(1153, 437, 48, 50),
            "next": pygame.Rect(1206, 440, 44, 44),
        }
        self.volume_rect = pygame.Rect(1110, 539, 134, 24)
        self.texts = {}
        self.web_audio = None
        if sys.platform == "emscripten":
            import platform
            self.web_audio = platform.window.snakeRadio
            self.web_audio.configure(json.dumps({
                "tracks": ["audio/" + track[1] for track in TRACKS],
                "buttons": {name: list(rect) for name, rect in self.buttons.items()},
                "volume": self.volume,
            }))

    @property
    def position(self):
        """Время трека, включая уже проигранное перед паузой."""
        if self.web_audio is not None:
            return float(self.web_audio.position)
        if not self.playing:
            return min(self.track_duration, self.elapsed)
        running = (pygame.time.get_ticks() - self.started_at) / 1000
        return min(self.track_duration, self.elapsed + running)

    def _prepare(self):
        if not pygame.mixer.get_init():
            # Буфер настольного SDL-плеера; веб использует HTMLAudioElement.
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        pygame.mixer.music.set_volume(self.volume)

    def play(self):
        """Запустить выбранный трек или продолжить после паузы."""
        if self.web_audio is not None:
            self.web_audio.play()
            return
        try:
            self._prepare()
            self.track_duration = TRACKS[self.index][2]
            
            if self.loaded:
                pygame.mixer.music.unpause()
            else:
                path = ds.ASSETS_DIR / "music" / TRACKS[self.index][1]
                pygame.mixer.music.load(str(path))
                pygame.mixer.music.play()
                self.loaded = True
                self.elapsed = 0.0
                
            self.started_at = pygame.time.get_ticks()
            self.playing = True
            self.error = False
        except (pygame.error, OSError):
            self.playing = False
            self.loaded = False
            self.error = True

    def toggle(self):
        """Пауза музыки не ставит на паузу саму игру."""
        if self.web_audio is not None:
            self.web_audio.toggle()
            return
        if self.playing:
            self.elapsed = self.position
            pygame.mixer.music.pause()
            self.playing = False
        else:
            self.play()

    def change_track(self, step):
        """Переключить трек по кругу и начать его с начала."""
        if self.web_audio is not None:
            self.web_audio.change(step)
            return
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
        
        self.playing = False
        self.loaded = False
        self.elapsed = 0.0
        
        self.index = (self.index + step) % len(TRACKS)
        self.play()

    def set_volume(self, value):
        """Изменить громкость от нуля до единицы."""
        self.volume = max(0.0, min(1.0, value))
        if self.web_audio is not None:
            self.web_audio.setVolume(self.volume)
        elif pygame.mixer.get_init():
            pygame.mixer.music.set_volume(self.volume)

    def handle_event(self, event):
        """Поглотить ввод плеера, чтобы он не управлял змейкой."""
        if self.web_audio is not None and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_m, pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
                return True  # Handled synchronously by the browser gesture listener.
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_m:
                self.toggle()
                return True
            elif event.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
                self.change_track(-1 if event.key == pygame.K_LEFTBRACKET else 1)
                return True
            elif event.key in (pygame.K_MINUS, pygame.K_EQUALS):
                self.set_volume(self.volume + (-0.05 if event.key == pygame.K_MINUS else 0.05))
                return True
                
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                return False
            for name, rect in self.buttons.items():
                if rect.collidepoint(event.pos):
                    if self.web_audio is not None:
                        return True
                    if name == "play":
                        self.toggle()
                    else:
                        self.change_track(-1 if name == "previous" else 1)
                    return True
            if self.volume_rect.collidepoint(event.pos):
                self.dragging = True
                self._drag_volume(event.pos[0])
                return True
                
        if event.type == pygame.MOUSEMOTION and self.dragging:
            self._drag_volume(event.pos[0])
            return True
            
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_dragging = self.dragging
            self.dragging = False
            return was_dragging
            
        return False

    def _drag_volume(self, x):
        self.set_volume((x - self.volume_rect.x) / self.volume_rect.width)

    def update(self, dt):
        """Двигать пластинку и проверять завершение трека по времени."""
        if self.web_audio is not None:
            self.index = int(self.web_audio.index)
            self.playing = bool(self.web_audio.playing)
            self.error = bool(self.web_audio.error)
            self.track_duration = TRACKS[self.index][2]
            if self.playing:
                self.phase += dt
            return
        if self.playing:
            self.phase += dt
            # Безопасный автопереход: если текущее время превысило длину трека, переключаем дальше
            if self.position >= self.track_duration:
                self.change_track(1)

    def _label(self, surface, text, size, color, center):
        key = (text, size, color)
        if key not in self.texts:
            self.texts[key] = self.assets.font(size).render(text, True, color)
        label = self.texts[key]
        surface.blit(label, label.get_rect(center=center))

    @staticmethod
    def _time(seconds):
        return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"

    def draw(self, surface, mouse):
        """Нарисовать радио за пределами поля и поверх экранов игры."""
        surface.blit(self.panel, self.rect)
        cx = self.rect.centerx
        self._label(surface, "ЛЕСНОЕ РАДИО", 15, ds.GOLD, (cx, 263))
        
        center = (cx, 316)
        pygame.draw.circle(surface, ds.NIGHT_TEAL, center, 35)
        for radius in (23, 28, 33):
            pygame.draw.circle(surface, (39, 89, 96), center, radius, 1)
        pygame.draw.circle(surface, ds.LEAF_GREEN, center, 14)
        pygame.draw.circle(surface, ds.CREAM, center, 4)
        
        angle = self.phase * 1.8
        dot = (cx + int(28 * math.cos(angle)), 316 + int(28 * math.sin(angle)))
        pygame.draw.circle(surface, ds.GOLD, dot, 3)
        
        title = TRACKS[self.index][0]
        for i, line in enumerate(wrap_text(title, self.assets.font(19), 148)):
            self._label(surface, line, 19, ds.CREAM, (cx, 374 + i * 24))
            
        status = "Звук недоступен" if self.error else f"{self.index + 1:02d} / 03"
        self._label(surface, status, 13, ds.LIGHT_GREEN, (cx, 416))
        
        for name, rect in self.buttons.items():
            hovered = rect.collidepoint(mouse)
            fill = ds.LIGHT_GREEN if hovered else (ds.LEAF_GREEN if name == "play" else (36, 86, 74))
            pygame.draw.rect(surface, ds.NIGHT_TEAL, rect.move(0, 3), border_radius=15)
            pygame.draw.rect(surface, fill, rect, border_radius=15)
            x, y = rect.center
            ink = ds.NIGHT_TEAL if name == "play" else ds.CREAM
            
            if name == "play" and self.playing:
                for dx in (-7, 3):
                    pygame.draw.rect(surface, ink, (x + dx, y - 9, 5, 18), border_radius=2)
            elif name == "play":
                pygame.draw.polygon(surface, ink, [(x - 5, y - 10), (x - 5, y + 10), (x + 9, y)])
            else:
                direction = -1 if name == "previous" else 1
                pygame.draw.polygon(surface, ink, [(x - direction * 5, y - 8), (x - direction * 5, y + 8), (x + direction * 6, y)])
                pygame.draw.line(surface, ink, (x + direction * 9, y - 8), (x + direction * 9, y + 8), 3)
                
        position = self.position
        progress = pygame.Rect(1110, 500, 134, 4)
        pygame.draw.rect(surface, ds.NIGHT_TEAL, progress, border_radius=2)
        fill = progress.copy()
        fill.width = int(progress.width * position / self.track_duration)
        if fill.width:
            pygame.draw.rect(surface, ds.GOLD, fill, border_radius=2)
            
        self._label(surface, self._time(position), 12, ds.CREAM, (1125, 516))
        self._label(surface, self._time(self.track_duration), 12, ds.CREAM, (1228, 516))
        
        bar = pygame.Rect(1110, 549, 134, 5)
        pygame.draw.rect(surface, ds.NIGHT_TEAL, bar, border_radius=3)
        fill = bar.copy()
        fill.width = int(bar.width * self.volume)
        if fill.width:
            pygame.draw.rect(surface, ds.LIGHT_GREEN, fill, border_radius=3)
        pygame.draw.circle(surface, ds.CREAM, (bar.x + fill.width, bar.centery), 6)
        
        self._label(surface, f"ГРОМКОСТЬ · {round(self.volume * 100)}%", 12, ds.CREAM, (cx, 535))
        self._label(surface, "M · музыка [ ] · трек", 11, ds.LIGHT_GREEN, (cx, 574))
