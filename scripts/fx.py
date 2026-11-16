"""Her expression marks: the small drawn signs an anime face shows a feeling with. numpy and Pillow
only, so both parts.py and rig.py can load it whichever Python each is run with.

Each mark is a layer of its own that the build draws for every character, hidden until its
parameter fades it in (rig.py's `marks`); her expressions set them (acting.py):

  fx_sweat      ParamFxSweat     a sweat drop beside her brow
  fx_anger      ParamFxAnger     an anger mark (four red arcs round a cross) on her head
  fx_tears      ParamFxTears     tears gathered along the bottom of each eye, a bead of them at its outer end
  fx_sparkle_l, fx_sparkle_r
                ParamFxSparkle   star-shaped lights in her irises, which follow them
  fx_gloom      ParamFxGloom     a blue shade over her brow with lines hanging in it

They are placed from her eyes, as her blush is: every size is in eye widths and every place is along
and down the line her eyes make, so a tilted face gets tilted marks. Her layers' live2d.json can
change one: "fx": {"sweat": {"size": 1.3, "right": 0.2, "down": -0.1}} makes her sweat drop bigger
and moves it right and up, in eye widths. A layer of her own with a mark's name is used instead of
the drawn one.

They are drawn twice as big as her frame, in a cut round her head, and the build puts that copy in
her texture, as it does her head's sharp copies; her frame's layer is the copy shrunk.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import blush as B

MARKS = {"sweat": ("ParamFxSweat", ("fx_sweat",)), "anger": ("ParamFxAnger", ("fx_anger",)),
         "tears": ("ParamFxTears", ("fx_tears",)), "sparkle": ("ParamFxSparkle", ("fx_sparkle_l", "fx_sparkle_r")),
         "gloom": ("ParamFxGloom", ("fx_gloom",))}
LAYERS = {layer: mark for mark, (_, layers) in MARKS.items() for layer in layers}
PLAIN = {"size": 1.0, "right": 0.0, "down": 0.0}
SHARP = 2          # drawn this many times her frame's size
SS = 3             # ...and that many times bigger again while drawing, then shrunk: smooth edges
ROOM = 0.7         # the cut round her head: her face's box and this share of it more each way

WATER = np.array([0.80, 0.92, 1.00], np.float32)
WATER_EDGE = np.array([0.32, 0.52, 0.88], np.float32)
TEAR = np.array([0.93, 0.97, 1.00], np.float32)  # gathered tears are nearly white
ANGER = np.array([0.90, 0.16, 0.22], np.float32)
ANGER_EDGE = np.array([0.52, 0.05, 0.10], np.float32)
GLOOM = np.array([0.20, 0.22, 0.42], np.float32)
WHITE = np.ones(3, np.float32)


class Sheet:
    """One mark's layer in the cut round her head, SHARP times her frame's size. Points are given in
    her frame's pixels."""

    def __init__(self, box):
        self.x0, self.y0, x1, y1 = box
        self.w, self.h = (x1 - self.x0) * SHARP, (y1 - self.y0) * SHARP
        self.rgba = np.zeros((self.h, self.w, 4), np.float32)

    def local(self, pts):
        return (np.asarray(pts, np.float32) - (self.x0, self.y0)) * SHARP

    def over(self, lo, colour, a):
        """A colour laid over what is there, a being how solid at each pixel of the patch at lo."""
        d = self.rgba[lo[1]:lo[1] + a.shape[0], lo[0]:lo[0] + a.shape[1]]
        both = a + d[..., 3] * (1 - a)
        d[..., :3] = (np.asarray(colour) * a[..., None] + d[..., :3] * (d[..., 3] * (1 - a))[..., None]) / np.maximum(both, 1e-6)[..., None]
        d[..., 3] = both

    def fill(self, poly, colour, alpha=1.0, blur=0.0):
        """A filled shape through these points, `blur` of her frame's pixels soft at its edge."""
        p = self.local(poly)
        pad = 2 + 3 * blur * SHARP
        lo = np.maximum(np.floor(p.min(axis=0) - pad).astype(int), 0)
        hi = np.minimum(np.ceil(p.max(axis=0) + pad).astype(int), [self.w, self.h])
        if (hi <= lo).any():
            return
        mask = Image.new("L", tuple(int(v) for v in (hi - lo) * SS), 0)
        ImageDraw.Draw(mask).polygon([tuple(q) for q in (p - lo) * SS], fill=255)
        if blur:
            mask = mask.filter(ImageFilter.GaussianBlur(blur * SHARP * SS))
        self.over(lo, colour, np.asarray(mask.reduce(SS), np.float32) / 255 * alpha)

    def line(self, pts, widths, colour, alpha=1.0):
        """A stroke through these points, widths across (her frame's pixels)."""
        pts = np.asarray(pts, np.float32)
        d = np.gradient(pts, axis=0)
        n = np.stack([-d[:, 1], d[:, 0]], 1)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
        half = (np.broadcast_to(np.asarray(widths, np.float32), (len(pts),)) / 2)[:, None]
        self.fill(np.concatenate([pts + n * half, (pts - n * half)[::-1]]), colour, alpha)

    def shade(self, how, colour):
        """A colour over the whole cut, how(x, y) -> how solid, x and y in her frame's pixels."""
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        self.over((0, 0), colour, np.clip(how(xx / SHARP + self.x0, yy / SHARP + self.y0), 0, 1))

    def pictures(self, frame):
        """(her frame's layer, the sharp copy, its corner in her frame, a pixel of it in hers)."""
        self.rgba[self.rgba[..., 3] < B.FLOOR] = 0
        sharp = B.as_image(self.rgba)
        small = sharp.convert("RGBa").reduce(SHARP).convert("RGBA")
        whole = Image.new("RGBA", frame, (0, 0, 0, 0))
        whole.paste(small, (self.x0, self.y0))
        return whole, sharp, [float(self.x0), float(self.y0)], [1 / SHARP, 1 / SHARP]


def circle(c, r, n=48):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.asarray(c) + r * np.stack([np.cos(t), np.sin(t)], 1)


def drop(c, r, tip, long=2.5):
    """A drop: a round of radius r at c, drawn out to a point `long` radii away toward `tip` (a unit way)."""
    tip = np.asarray(tip, np.float32)
    side = np.array([-tip[1], tip[0]])
    t = np.radians(np.linspace(-35, 215, 40))  # round the far side from the point
    body = np.asarray(c) + r * (np.cos(t)[:, None] * side - np.sin(t)[:, None] * tip)
    return np.concatenate([[np.asarray(c) + tip * r * long], body])


def star(c, r, turn=0.0, waist=0.2):
    """A four-pointed star, its points r from c."""
    t = np.radians(turn) + np.arange(8) * np.pi / 4
    far = np.where(np.arange(8) % 2 == 0, r, r * waist)
    return np.asarray(c) + far[:, None] * np.stack([np.sin(t), -np.cos(t)], 1)


def arc(c, r, across, up, a0, a1, n=40):
    """Points on a round about c from a0 to a1 degrees, measured from `across` toward `up`."""
    t = np.radians(np.linspace(a0, a1, n))
    return np.asarray(c) + r * (np.cos(t)[:, None] * np.asarray(across) + np.sin(t)[:, None] * np.asarray(up))


def ease(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def her_face(images):
    """What the marks are placed from, out of her layers ({layer: an RGBA picture as big as her frame}):
    None unless she has a face and an eye on each side of it."""
    alpha = lambda layer: np.asarray(images[layer].getchannel("A"), np.float32) / 255
    if "face" not in images:
        return None
    face = alpha("face")
    eyes = [alpha(layer) for layer in ("eyewhite", "eyelash", "irides") if layer in images]
    found = B.eyes_of(eyes, face) if eyes else None
    if not found:
        return None
    ys, xs = np.nonzero(face > 0.5)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    _, wide, along, down = B.cheeks(found)
    a, b = (np.array([(e[0] + e[2]) / 2, (e[1] + e[3]) / 2]) for e in found)
    irises = []
    if "irides" in images:
        iris = alpha("irides") > 0.5
        middle = (box[0] + box[2]) // 2
        for half, x in ((iris[:, :middle], 0), (iris[:, middle:], middle)):
            iy, ix = np.nonzero(half)
            irises.append((x + ix.min(), iy.min(), x + ix.max() + 1, iy.max() + 1) if len(ix) > 20 else None)
    # Each eye's lower lid: the lowest drawn pixel of her eye in each column (xs, ys), smoothed.
    drawn = np.zeros(face.shape, bool)
    for layer in eyes:
        drawn |= layer >= 0.25
    lids = []
    for x0, y0, x1, y1 in found:
        part = drawn[y0:y1, x0:x1]
        cols = np.nonzero(part.any(axis=0))[0]
        low = y0 + part.shape[0] - 1 - part[::-1, cols].argmax(axis=0)
        pad = max(1, len(cols) // 12)
        low = np.convolve(np.pad(low.astype(float), pad, mode="edge"), np.ones(2 * pad + 1) / (2 * pad + 1), mode="valid")
        lids.append((x0 + cols.astype(float), low))
    H, W = face.shape
    room = ROOM * max(box[2] - box[0], box[3] - box[1])
    cut = (max(0, int(box[0] - room)), max(0, int(box[1] - room)), min(W, int(box[2] + room)), min(H, int(box[3] + room)))
    return {"frame": (W, H), "cut": cut, "box": box, "eyes": found, "a": a, "b": b, "wide": float(wide), "along": along,
            "down": down, "irises": irises, "lids": lids}


def placed(f, adjust, at):
    """A mark's own eye width and middle, with what her live2d.json asks of it."""
    wide = f["wide"] * adjust["size"]
    return wide, np.asarray(at) + (f["along"] * adjust["right"] + f["down"] * adjust["down"]) * f["wide"]


def sweat(f, adjust):
    w, c = placed(f, adjust, f["b"] + f["along"] * 1.0 * f["wide"] - f["down"] * 0.45 * f["wide"])
    s, r = Sheet(f["cut"]), 0.17 * w
    tip = -f["down"] * math.cos(0.3) + f["along"] * math.sin(0.3) * -1  # its point up, leaning in a little
    tip /= np.linalg.norm(tip)
    s.fill(drop(c, r * 1.2, tip, 2.4), WATER_EDGE)
    s.fill(drop(c, r, tip, 2.45), WATER)
    s.fill(circle(c - f["along"] * 0.35 * r + tip * 0.25 * r, 0.3 * r), WHITE, 0.95)
    return {"fx_sweat": s}


def anger(f, adjust):
    w, c = placed(f, adjust, f["a"] - f["along"] * 0.3 * f["wide"] - f["down"] * 1.7 * f["wide"])
    s, d, r = Sheet(f["cut"]), 0.24 * w, 0.17 * w
    t = np.linspace(-1, 1, 40)
    thin = 0.55 + 0.45 * np.cos(np.pi * t / 2) ** 0.5
    for edge, colour, wide in ((True, ANGER_EDGE, 0.115 * w), (False, ANGER, 0.07 * w)):
        for sx in (-1, 1):
            for sy in (-1, 1):  # each corner's arc bulges toward the middle, leaving a cross between them
                pts = arc(c + d * (sx * f["along"] + sy * f["down"]), r, -sx * f["along"], -sy * f["down"], -25, 115)
                s.line(pts, wide * thin, colour)
    return {"fx_anger": s}


def tears(f, adjust):
    """Tears gathered along the bottom of each eye: a pool lying on her lower lid, thin at the inner
    corner and swelling toward the outer one, where a bead of it hangs a little under the lid. (A
    stream running down each cheek was too much: the first user, 2026-11-15.)"""
    s = Sheet(f["cut"])
    for i, (x0, y0, x1, y1) in enumerate(f["eyes"]):
        out = -1 if i == 0 else 1  # the outer corner is away from her nose
        w = f["wide"] * adjust["size"]
        shift = (f["along"] * adjust["right"] * out + f["down"] * adjust["down"]) * f["wide"]
        lid = f["lids"][i]
        u = np.linspace(0.14, 0.88, 60)  # along her eye, from its inner corner to its outer one
        xs = (x1 - u * (x1 - x0)) if i == 0 else (x0 + u * (x1 - x0))
        edge = np.stack([xs, np.interp(xs, lid[0], lid[1])], 1) + shift
        deep = w * (0.02 + 0.055 * ease((u - 0.15) / 0.55)) * np.sin(np.pi * np.clip((u - 0.14) / 0.74, 0, 1)) ** 0.5
        wobble = 1 + 0.18 * np.sin(u * 9.0)  # the pool's top isn't a ruled line
        top = edge - np.outer(deep * wobble, f["down"]) * 0.8
        low = edge + np.outer(deep, f["down"]) * 0.2
        bead = edge[int(0.8 * len(u))] + f["down"] * 0.03 * w
        for colour, grow, alpha in ((WATER_EDGE, 0.012 * w, 0.6), (TEAR, 0.0, 0.93)):
            s.fill(np.concatenate([top - f["down"] * grow, (low + f["down"] * grow)[::-1]]), colour, alpha)
            s.fill(drop(bead, 0.05 * w + grow, -f["down"], 1.4), colour, alpha)
        s.fill(circle(bead - f["along"] * 0.015 * w - f["down"] * 0.015 * w, 0.016 * w), WHITE, 0.95)
    return {"fx_tears": s}


def sparkle(f, adjust):
    out = {}
    for name, iris in zip(("fx_sparkle_l", "fx_sparkle_r"), f["irises"]):
        if iris is None:
            continue
        x0, y0, x1, y1 = iris
        size = (x1 - x0) * adjust["size"]
        c = np.array([(x0 + x1) / 2, (y0 + y1) / 2]) + (f["along"] * adjust["right"] + f["down"] * adjust["down"]) * f["wide"]
        s = Sheet(f["cut"])
        for at, r, turn in (((-0.16, -0.14), 0.34, 0.0), ((0.20, 0.20), 0.17, 45.0), ((0.26, -0.24), 0.09, 0.0)):
            p = c + f["along"] * at[0] * size + f["down"] * at[1] * size
            s.fill(star(p, r * size * 1.25, turn), WHITE, 0.35, blur=0.03 * size)  # a glow round it
            s.fill(star(p, r * size, turn), WHITE, 0.97)
        s.fill(circle(c + f["along"] * -0.27 * size + f["down"] * 0.26 * size, 0.045 * size), WHITE, 0.95)
        out[name] = s
    return out


def gloom(f, adjust):
    s = Sheet(f["cut"])
    x0, y0, x1, y1 = f["box"]
    wide = f["wide"]
    # The shade is gone at her eyes' lower edge: its last faint step is lost in her lashes there, where
    # on her bare cheek it showed as a line.
    low = max(e[3] for e in f["eyes"]) + (0.08 + adjust["down"]) * wide
    soft = 0.12 * (x1 - x0)  # it comes in softly at the top and the sides: no edge where her face's layer ends
    s.shade(lambda x, y: 0.45 * adjust["size"] * ease((y - y0) / (0.3 * max(low - y0, 1))) * (1 - ease((y - y0) / max(low - y0, 1)))
            * ease((x - x0) / soft) * ease((x1 - x) / soft) * 1.6, GLOOM)
    brow = min(e[1] for e in f["eyes"])
    middle = (f["a"][1] + f["b"][1]) / 2
    for i in range(9):  # lines hanging from the top of her face, each its own length
        x = x0 + (0.14 + 0.72 * i / 8) * (x1 - x0)
        top = y0 + 0.12 * (brow - y0)
        long = (middle - top) * (0.6 + 0.4 * ((i * 0.618) % 1))  # none reaches past the middle of her eyes
        u = np.linspace(0, 1, 30)
        s.line(np.stack([np.full_like(u, x), top + u * long], 1), 0.05 * wide * adjust["size"] * np.sin(np.pi * (0.15 + 0.85 * u)) ** 0.7,
               GLOOM, 0.72)
    return {"fx_gloom": s}


DRAW = {"sweat": sweat, "anger": anger, "tears": tears, "sparkle": sparkle, "gloom": gloom}


def adjusted(given, mark):
    """A mark's size and place from her live2d.json's "fx", checked: {"size", "right", "down"}."""
    asked = (given or {}).get(mark) if isinstance(given, dict) else None
    out = dict(PLAIN)
    for key in PLAIN:
        v = asked.get(key) if isinstance(asked, dict) else None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = float(min(3.0, max(0.3, v)) if key == "size" else min(2.0, max(-2.0, v)))
    return out


def for_her(images, given=None):
    """Every mark for her, drawn from her layers: {layer: (her frame's layer, its sharp copy, that
    copy's corner in her frame, a pixel of it in hers)}. Nothing if her eyes can't be found."""
    f = her_face(images)
    if f is None:
        return {}
    out = {}
    for mark, draw in DRAW.items():
        for layer, sheet in draw(f, adjusted(given, mark)).items():
            if sheet.rgba[..., 3].max() > B.FLOOR:
                out[layer] = sheet.pictures(f["frame"])
    return out
