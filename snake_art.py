"""Мягкая рисованная Питоша: сглаженное тело и живая мордочка."""

import math

import pygame

import design as ds


OUTLINE = (54, 105, 43)
GREEN = (133, 197, 67)
BELLY = (249, 222, 135)


def make_head(blink=False):
    """Рисовать мордочку в тройном разрешении для чётких краёв."""
    surface = pygame.Surface((180, 144), pygame.SRCALPHA)

    def oval(color, box):
        pygame.draw.ellipse(surface, color, tuple(round(v * 3) for v in box))

    def line(color, points, width=1):
        pygame.draw.lines(surface, color, False,
                          [(round(x * 3), round(y * 3)) for x, y in points],
                          round(width * 3))

    # Большой округлый затылок, мягкая щёчка и короткая мордочка.
    oval(OUTLINE, (5, 8, 44, 34))
    oval(OUTLINE, (22, 20, 33, 23))
    oval(GREEN, (7, 10, 40, 30))
    oval(BELLY, (12, 28, 41, 13))
    oval(GREEN, (23, 21, 30, 16))
    oval((164, 218, 91), (11, 11, 24, 13))
    # Пятнышки остаются крупными и читаемыми даже в масштабе игры.
    for box in ((10, 23, 7, 6), (17, 14, 7, 5), (8, 17, 5, 4)):
        oval((107, 166, 53), box)
    # Два открытых глаза с тёплыми зрачками и бликами.
    for x, y, w, h in ((32, 8, 12, 17), (21, 12, 14, 19)):
        if blink:
            line(OUTLINE, [(x + 1, y + 10), (x + w / 2, y + 12),
                           (x + w - 1, y + 10)], 1.5)
        else:
            oval(OUTLINE, (x - 1, y - 1, w + 2, h + 2))
            oval((255, 252, 227), (x, y, w, h))
            oval((86, 67, 37), (x + w * .4, y + 4, w * .55, h * .69))
            oval((38, 49, 30), (x + w * .55, y + 6, w * .36, h * .49))
            oval((255, 255, 250), (x + w * .48, y + 4, 3.2, 4.2))
    oval((236, 163, 112), (32, 30, 8, 4))
    oval(OUTLINE, (46, 25, 2, 2))
    line((79, 107, 41), [(38, 35), (42, 36), (47, 35), (50, 32)], 1)
    return surface


class SnakeRenderer:
    """Цельная округлая змейка с плавными изгибами и тонким хвостом."""

    def __init__(self, assets):
        self.heads = [pygame.transform.smoothscale(image, (50, 40))
                      for image in (assets.head, make_head(True))]
        self.bounce_t = ds.HEAD_BOUNCE_TIME
        self.time = 0.0
        self.angle = None
        self.dt = 1 / ds.FPS

    def react(self):
        self.bounce_t = 0.0

    def update(self, dt):
        self.dt = dt
        self.time += dt
        self.bounce_t = min(ds.HEAD_BOUNCE_TIME, self.bounce_t + dt)

    @staticmethod
    def _unwrap(delta, size):
        if delta > size / 2:
            return delta - size
        if delta < -size / 2:
            return delta + size
        return delta

    def pixel_position(self, snake, index, progress):
        cur = snake.positions[index]
        prev = (snake.previous_positions[index]
                if index < len(snake.previous_positions) else cur)
        dx = self._unwrap(cur[0] - prev[0], ds.GRID_WIDTH)
        dy = self._unwrap(cur[1] - prev[1], ds.GRID_HEIGHT)
        return ((cur[0] + .5 - dx * (1 - progress)) * ds.GRID_SIZE,
                (cur[1] + .5 - dy * (1 - progress)) * ds.GRID_SIZE)

    def _path(self, snake, progress):
        points = [self.pixel_position(snake, 0, progress)]
        for i in range(1, len(snake.positions)):
            x, y = self.pixel_position(snake, i, progress)
            px, py = points[-1]
            points.append((px + self._unwrap(x - px, ds.FIELD_WIDTH),
                           py + self._unwrap(y - py, ds.FIELD_HEIGHT)))
        if len(points) == 1:
            x, y = points[0]
            dx, dy = snake.direction
            points.append((x - dx * 17, y - dy * 17))
        x, y = points[-1]
        px, py = points[-2]
        length = math.hypot(x - px, y - py) or 1
        points.append((x + (x - px) / length * 13,
                       y + (y - py) / length * 13))
        # Срезаем углы кривой, сохраняя голову и самый кончик хвоста.
        for _ in range(3):
            smooth = [points[0]]
            for a, b in zip(points, points[1:]):
                smooth.extend(((.75*a[0]+.25*b[0], .75*a[1]+.25*b[1]),
                               (.25*a[0]+.75*b[0], .25*a[1]+.75*b[1])))
            points = smooth + [points[-1]]
        return points

    def draw(self, field, snake, progress):
        points = self._path(snake, progress)
        left = math.floor(min(p[0] for p in points) - 34)
        top = math.floor(min(p[1] for p in points) - 34)
        width = math.ceil(max(p[0] for p in points) - left + 34)
        height = math.ceil(max(p[1] for p in points) - top + 34)
        layer = pygame.Surface((width * 2, height * 2), pygame.SRCALPHA)
        lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
        total = sum(lengths)
        samples, distance = [], 0.0
        for a, b, length in zip(points, points[1:], lengths):
            steps = max(1, math.ceil(length / 1.5))
            for i in range(steps):
                t = i / steps
                remaining = total - distance - length * t
                radius = 10.5 * min(1.0, max(.09, remaining / 32)) ** .65
                samples.append((a[0] + (b[0]-a[0])*t,
                                a[1] + (b[1]-a[1])*t, radius,
                                distance + length*t))
            distance += length

        def dot(color, x, y, radius):
            pygame.draw.circle(layer, color,
                               (round((x-left)*2), round((y-top)*2)),
                               max(1, round(radius*2)))

        # Непрерывные слои, поэтому на стыках нет швов или квадратов.
        for color, offset, shrink in (((21, 49, 33, 45), 4, -2),
                                      (OUTLINE, 0, -1),
                                      (BELLY, 1, .5),
                                      (GREEN, -2, 1.2),
                                      ((161, 213, 87), -4, 4.3)):
            for x, y, radius, _ in reversed(samples):
                dot(color, x, y + offset * radius / 10.5,
                    max(.5, radius - shrink))
        last_spot = -20
        for x, y, radius, distance in samples:
            if distance - last_spot >= 19 and radius > 6 and distance > 17:
                dot((111, 175, 55), x, y - 1, radius * .29)
                dot((185, 225, 109), x - 2, y - 3, radius * .11)
                last_spot = distance

        target = math.degrees(math.atan2(-snake.direction[1], snake.direction[0]))
        if self.angle is None:
            self.angle = target
        delta = (target - self.angle + 180) % 360 - 180
        self.angle += delta * min(1, self.dt * 18)
        blink = self.time % 4.3 > 4.13
        head = self.heads[int(blink)]
        face_angle = self.angle
        if math.cos(math.radians(self.angle)) < 0:
            head = pygame.transform.flip(head, True, False)
            face_angle -= 180
        bounce = math.sin(math.pi * self.bounce_t / ds.HEAD_BOUNCE_TIME)
        head = pygame.transform.rotozoom(head, face_angle, 2 * (1 + .08 * bounce))
        cx, cy = points[0]
        layer.blit(head, head.get_rect(center=(round((cx-left)*2), round((cy-top)*2))))
        image = pygame.transform.smoothscale(layer, (width, height))
        # Перенос через край поля остаётся бесшовным, без длинных перемычек.
        bounds = field.get_rect()
        for dx in (-ds.FIELD_WIDTH, 0, ds.FIELD_WIDTH):
            for dy in (-ds.FIELD_HEIGHT, 0, ds.FIELD_HEIGHT):
                rect = image.get_rect(topleft=(left+dx, top+dy))
                if rect.colliderect(bounds):
                    field.blit(image, rect)
