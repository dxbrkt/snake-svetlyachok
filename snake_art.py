"""Мягкая рисованная Питоша: сглаженное тело и живая мордочка."""

import math

import pygame

import design as ds


OUTLINE = (54, 105, 43)
GREEN = (133, 197, 67)
BELLY = (249, 222, 135)


SKINS = {
    "classic": {"name": "Питоша", "body": GREEN, "outline": OUTLINE,
                "belly": BELLY, "light": (164, 218, 91), "spot": (107, 166, 53)},
    "berry": {"name": "Клубничка", "body": (225, 75, 91), "outline": (139, 48, 69),
              "belly": (255, 209, 165), "light": (249, 123, 126), "spot": (255, 225, 139)},
    "firefly": {"name": "Светлячок", "body": (58, 136, 128), "outline": (27, 79, 83),
                "belly": (255, 224, 133), "light": (104, 181, 152), "spot": (255, 221, 91)},
    "dragon": {"name": "Дракончик", "body": (112, 156, 224), "outline": (53, 79, 139),
               "belly": (255, 221, 161), "light": (156, 194, 247), "spot": (255, 194, 104)},
}


def make_head(blink=False, skin="classic"):
    """Рисовать мордочку в тройном разрешении для чётких краёв."""
    palette = SKINS[skin]
    outline, body, belly = palette["outline"], palette["body"], palette["belly"]
    surface = pygame.Surface((180, 144), pygame.SRCALPHA)

    def oval(color, box):
        pygame.draw.ellipse(surface, color, tuple(round(v * 3) for v in box))

    def line(color, points, width=1):
        pygame.draw.lines(surface, color, False,
                          [(round(x * 3), round(y * 3)) for x, y in points],
                          round(width * 3))

    # Большой округлый затылок, мягкая щёчка и короткая мордочка.
    oval(outline, (5, 8, 44, 34))
    oval(outline, (22, 20, 33, 23))
    oval(body, (7, 10, 40, 30))
    oval(belly, (12, 28, 41, 13))
    oval(body, (23, 21, 30, 16))
    oval(palette["light"], (11, 11, 24, 13))
    # Пятнышки остаются крупными и читаемыми даже в масштабе игры.
    for box in ((10, 23, 7, 6), (17, 14, 7, 5), (8, 17, 5, 4)):
        oval(palette["spot"], box)
    # Два открытых глаза с тёплыми зрачками и бликами.
    for x, y, w, h in ((32, 8, 12, 17), (21, 12, 14, 19)):
        if blink:
            line(outline, [(x + 1, y + 10), (x + w / 2, y + 12),
                           (x + w - 1, y + 10)], 1.5)
        else:
            oval(outline, (x - 1, y - 1, w + 2, h + 2))
            oval((255, 252, 227), (x, y, w, h))
            oval((86, 67, 37), (x + w * .4, y + 4, w * .55, h * .69))
            oval((38, 49, 30), (x + w * .55, y + 6, w * .36, h * .49))
            oval((255, 255, 250), (x + w * .48, y + 4, 3.2, 4.2))
    oval((236, 163, 112), (32, 30, 8, 4))
    oval(outline, (46, 25, 2, 2))
    line(outline, [(38, 35), (42, 36), (47, 35), (50, 32)], 1)
    def polygon(color, points):
        pygame.draw.polygon(surface, color, [(int(x * 3), int(y * 3)) for x, y in points])

    if skin == "berry":
        for points in ([(16, 14), (7, 6), (18, 8)],
                       [(17, 13), (19, 1), (24, 13)],
                       [(19, 13), (31, 5), (27, 15)]):
            polygon((57, 126, 58), points)
        line((97, 169, 69), [(18, 13), (20, 5)], 1.5)
    elif skin == "dragon":
        for points in ([(6, 19), (1, 13), (10, 15)],
                       [(8, 14), (5, 6), (14, 11)]):
            polygon((255, 190, 99), points)
        for points in ([(12, 12), (13, 2), (20, 11)],
                       [(24, 10), (27, 1), (31, 10)]):
            polygon(outline, points)
            polygon((255, 216, 131), [(x, y + 1) for x, y in points])
        polygon(outline, [(8, 28), (1, 22), (2, 39), (15, 39)])
        polygon((169, 204, 250), [(8, 30), (3, 26), (4, 36), (13, 37)])
        line(outline, [(4, 28), (8, 36), (11, 33)], 1)
    elif skin == "firefly":
        for x in (12, 23):
            line(outline, [(x + 2, 12), (x, 5)], 1.4)
            oval((255, 222, 100), (x - 2, 1, 5, 5))
    return surface


class SnakeRenderer:
    """Цельная округлая змейка с плавными изгибами и тонким хвостом."""

    def __init__(self, assets):
        self.set_skin("classic")
        self.bounce_t = ds.HEAD_BOUNCE_TIME
        self.time = 0.0
        self.angle = None
        self.dt = 1 / ds.FPS

    def set_skin(self, skin):
        """Обновить только рисунок: правила движения остаются прежними."""
        self.skin = skin
        self.palette = SKINS[skin]
        self.heads = [pygame.transform.smoothscale(make_head(blink, skin), (50, 40))
                      for blink in (False, True)]

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

        palette = self.palette
        if self.skin == "firefly":
            for x, y, radius, distance in samples[::12]:
                dot((255, 218, 83, 22), x, y, radius + 5)
        # Непрерывные слои, поэтому на стыках нет швов или квадратов.
        for color, offset, shrink in (((21, 49, 33, 45), 4, -2),
                                      (palette["outline"], 0, -1),
                                      (palette["belly"], 1, .5),
                                      (palette["body"], -2, 1.2),
                                      (palette["light"], -4, 4.3)):
            for x, y, radius, _ in reversed(samples):
                dot(color, x, y + offset * radius / 10.5,
                    max(.5, radius - shrink))
        last_spot = -20
        for x, y, radius, distance in samples:
            if distance - last_spot >= 19 and radius > 6 and distance > 17:
                dot(palette["spot"], x, y - 1, radius * .29)
                dot(palette["belly"], x - 2, y - 3, radius * .11)
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
