"""Fonts, cached text, buttons, sliders and small drawing helpers."""
import pygame

from . import settings

_fonts = {}
_text_cache = {}
_shape_cache = {}


def font(size):
    f = _fonts.get(size)
    if f is None:
        if not settings.WEB:
            try:
                f = pygame.font.SysFont("arialrounded,arialroundedmtbold,trebuchetms,verdana,arial", size, bold=True)
            except Exception:
                f = None
        if f is None:
            f = pygame.font.Font(None, int(size * 1.3))
        _fonts[size] = f
    return f


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_col(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease_out_back(t):
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    return 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2


def text(s, size, color=(255, 255, 255), outline=(40, 15, 5), ow=2):
    """Cached text with a dark outline: readable on any background."""
    key = (s, size, color, outline, ow)
    surf = _text_cache.get(key)
    if surf is None:
        if len(_text_cache) > 600:
            _text_cache.clear()
        base = font(size).render(s, True, color)
        if outline and ow:
            w, h = base.get_size()
            surf = pygame.Surface((w + ow * 2, h + ow * 2 + 2), pygame.SRCALPHA)
            dark = font(size).render(s, True, outline)
            for dx in (-ow, 0, ow):
                for dy in (-ow, 0, ow, ow + 2):
                    if dx or dy:
                        surf.blit(dark, (ow + dx, ow + dy))
            surf.blit(base, (ow, ow))
        else:
            surf = base
        _text_cache[key] = surf
    return surf


def blit_text(dst, s, size, pos, color=(255, 255, 255), anchor="center", outline=(40, 15, 5), ow=2, alpha=None,
              scale=1.0):
    t = text(s, size, color, outline, ow)
    if scale != 1.0:
        t = pygame.transform.smoothscale(t, (max(1, int(t.get_width() * scale)), max(1, int(t.get_height() * scale))))
    if alpha is not None:
        t = t.copy()
        t.set_alpha(max(0, min(255, int(alpha))))
    r = t.get_rect(**{anchor: pos})
    dst.blit(t, r)
    return r


def pill(w, h, col, radius=None):
    """Cached glossy rounded rectangle."""
    key = ("pill", w, h, col)
    s = _shape_cache.get(key)
    if s is None:
        radius = radius if radius is not None else min(h // 2, 26)
        s = pygame.Surface((w, h + 5), pygame.SRCALPHA)
        pygame.draw.rect(s, (*lerp_col(col, (0, 0, 0), 0.55), 255), (0, 5, w, h), border_radius=radius)
        body = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            body.fill((*lerp_col(lerp_col(col, (255, 255, 255), 0.28), col, min(1.0, y / (h * 0.7))), 255),
                      (0, y, w, 1))
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=radius)
        body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        s.blit(body, (0, 0))
        pygame.draw.rect(s, (255, 255, 255, 120), (3, 3, w - 6, h - 6), 2, border_radius=max(2, radius - 3))
        _shape_cache[key] = s
    return s


def panel(w, h, fill=(30, 16, 8, 210), border=(255, 210, 74), radius=22):
    key = ("panel", w, h, fill, border, radius)
    s = _shape_cache.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(s, fill, (0, 0, w, h), border_radius=radius)
        pygame.draw.rect(s, border, (0, 0, w, h), 3, border_radius=radius)
        _shape_cache[key] = s
    return s


class Button:
    def __init__(self, label, cx, cy, cb, w=200, h=48, col=(214, 70, 40), size=24):
        self.label, self.cb, self.col, self.size = label, cb, col, size
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.center = (cx, cy)
        self.hover = 0.0
        self.press = 0.0
        self.enabled = True

    def update(self, dt, mouse):
        target = 1.0 if self.rect.collidepoint(mouse) and self.enabled else 0.0
        self.hover += (target - self.hover) * min(1.0, dt * 14)
        self.press = max(0.0, self.press - dt * 5)

    def hit(self, pos):
        if self.enabled and self.rect.collidepoint(pos):
            self.press = 1.0
            self.cb()
            return True
        return False

    def draw(self, surf):
        w, h = self.rect.size
        k = 1.0 + 0.06 * self.hover - 0.05 * self.press
        spr = pill(w, h, self.col if self.enabled else (110, 100, 95))
        if abs(k - 1.0) > 0.003:
            spr = pygame.transform.smoothscale(spr, (int(spr.get_width() * k), int(spr.get_height() * k)))
        c = self.rect.center
        surf.blit(spr, spr.get_rect(center=(c[0], c[1] + 2)))
        blit_text(surf, self.label, self.size, c)


class Slider:
    def __init__(self, label, x, y, w, value):
        self.label, self.rect, self.value, self.drag = label, pygame.Rect(x, y, w, 12), value, False

    def event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.inflate(30, 44).collidepoint(e.pos):
            self.drag = True
        if e.type == pygame.MOUSEBUTTONUP:
            self.drag = False
        if self.drag and e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            self.value = min(1.0, max(0.0, (e.pos[0] - self.rect.x) / self.rect.w))
            return True
        return False

    def draw(self, surf):
        blit_text(surf, self.label, 26, (self.rect.x - 20, self.rect.centery), anchor="midright")
        pygame.draw.rect(surf, (40, 20, 8), self.rect.inflate(4, 4), border_radius=8)
        fill = self.rect.copy()
        fill.w = int(self.rect.w * self.value)
        if fill.w:
            pygame.draw.rect(surf, (155, 227, 74), fill, border_radius=6)
        x = self.rect.x + int(self.rect.w * self.value)
        pygame.draw.circle(surf, (255, 210, 74), (x, self.rect.centery), 14)
        pygame.draw.circle(surf, (255, 255, 255), (x, self.rect.centery), 14, 3)


def heart(size, filled=True):
    key = ("heart", size, filled)
    s = _shape_cache.get(key)
    if s is None:
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        col = (255, 70, 90) if filled else (70, 40, 40)
        r = size // 4
        cy = size // 2 - r // 2
        pygame.draw.circle(s, col, (size // 2 - r, cy), r + 1)
        pygame.draw.circle(s, col, (size // 2 + r, cy), r + 1)
        pygame.draw.polygon(s, col, [(size // 2 - 2 * r + 1, cy + 2), (size // 2 + 2 * r - 1, cy + 2),
                                     (size // 2, size - 2)])
        if filled:
            pygame.draw.circle(s, (255, 190, 200), (size // 2 - r, cy - r // 3), max(2, r // 3))
        _shape_cache[key] = s
    return s
