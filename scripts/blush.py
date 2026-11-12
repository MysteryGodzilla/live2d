"""Her blush: the marks on her cheeks that fade in with ParamCheek. numpy and Pillow only, so both
parts.py and rig.py can load it whichever Python each is run with.

A blush is placed from her eyes: one mark under each, on the line her eyes make, so a tilted head
gets a tilted blush and both are turned upright together when she is rigged. Every size is in eye
widths, so it fits a big-eyed face and a small-eyed one alike.

The styles, by number (`live2d.py parts blush-sheet <name>` shows them on her face):
  1  a soft oval with three short strokes over it: the usual anime blush (the default)
  2  the soft oval alone
  3  the three strokes alone
  4  a flush across her nose, cheek to cheek, with the strokes
  5  round spots, firmer at the edge: a doll's cheeks

image2live2d paints a blush of its own when a character has none: two tall ovals set outward of
her eyes, which came out too big and too far apart (its first user, 2026-11-12: "a little big and
separated too far, they should come in more"), and with a hard edge (see soft_mesh in rig.py).
This one is smaller, flatter and under the middle of each eye.
"""
import math

import numpy as np
from PIL import Image, ImageDraw

STYLES = {1: "soft, with strokes", 2: "soft", 3: "strokes", 4: "across her nose", 5: "round spots"}
DEFAULT = 1

# In eye widths. An eye here is everything of one eye: lashes, white and iris.
DROP = 0.20          # the middle of a cheek's mark, below her eye's lower edge
INWARD = 0.04        # ...and toward her nose from the middle of her eye
WIDE, HIGH = 0.50, 0.27   # the oval: half its width and half its height, where it has faded to nothing
PEAK = 0.62          # the oval's strength at its middle (0 to 1), before ParamCheek fades it in
STROKES = (-1, 0, 1)
STROKE_GAP = 0.15    # between one stroke and the next
STROKE_LONG = 0.21   # a stroke's length (the outer two are a little shorter)
STROKE_WIDE = 0.026
STROKE_LEAN = 60     # degrees from level: they lean like "/"
STROKE_PEAK = 0.80
SPOT = 0.23          # style 5: a spot's radius
PINK = np.array([246, 120, 132], np.float32) / 255   # her skin is mixed toward this for the oval
DEEP = np.array([226, 84, 104], np.float32) / 255    # ...and toward this for the strokes
MIX, STROKE_MIX = 0.70, 0.85
FLOOR = 9 / 255      # fainter than this is left out: the model's texture atlas drops it anyway
SS = 4               # strokes are drawn this many times bigger, then shrunk


def eyes_of(eye_alphas, face_alpha=None):
    """Her two eyes as boxes (x0, y0, x1, y1), the one on the left of the picture first, from the
    alpha (0 to 1) of her eye layers. None unless there is one on each side of her face."""
    mask = np.zeros(eye_alphas[0].shape, bool)
    for a in eye_alphas:
        mask |= a >= 0.25
    cols = np.nonzero((face_alpha > 0.5).any(axis=0))[0] if face_alpha is not None else np.nonzero(mask.any(axis=0))[0]
    if not len(cols) or not mask.any():
        return None
    middle = int(round((cols.min() + cols.max()) / 2))
    boxes = []
    for half, x in ((mask[:, :middle], 0), (mask[:, middle:], middle)):
        ys, xs = np.nonzero(half)
        if not len(xs):
            return None
        boxes.append((x + xs.min(), ys.min(), x + xs.max() + 1, ys.max() + 1))
    return boxes


def skin_of(face):
    """Her skin's colour: the middle one of her face layer's solid pixels."""
    solid = face[..., 3] > 0.5
    return np.median(face[..., :3][solid], axis=0) if solid.any() else np.array([1.0, 0.88, 0.82], np.float32)


def cheeks(eyes, inward=0.0, down=0.0):
    """Where the marks go: each cheek's middle, an eye's width, and the two directions of her face
    (along her eyes, and down it)."""
    (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = eyes
    a = np.array([(ax0 + ax1) / 2, (ay0 + ay1) / 2])
    b = np.array([(bx0 + bx1) / 2, (by0 + by1) / 2])
    along = (b - a) / max(np.linalg.norm(b - a), 1e-6)
    downward = np.array([-along[1], along[0]])
    wide = ((ax1 - ax0) + (bx1 - bx0)) / 2
    high = ((ay1 - ay0) + (by1 - by0)) / 2
    drop = high / 2 + (DROP + down) * wide
    centres = [a + downward * drop + along * (INWARD + inward) * wide,
               b + downward * drop - along * (INWARD + inward) * wide]
    return centres, wide, along, downward


def draw(shape, eyes, skin, style=DEFAULT, size=1.0, inward=0.0, down=0.0):
    """The blush as a layer as big as her frame: RGBA from 0 to 1, shape (H, W, 4)."""
    if style not in STYLES:
        raise ValueError(f"blush style {style}: there are {', '.join(str(k) for k in STYLES)}")
    H, W = shape[:2]
    centres, eye, along, downward = cheeks(eyes, inward, down)
    unit = eye * size
    reach = int(math.ceil(1.2 * unit)) + 2
    x0 = max(0, int(min(c[0] for c in centres)) - reach)
    x1 = min(W, int(max(c[0] for c in centres)) + reach + 1)
    y0 = max(0, int(min(c[1] for c in centres)) - reach)
    y1 = min(H, int(max(c[1] for c in centres)) + reach + 1)
    ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)

    def oval(centre, half_wide, half_high, peak, firm=1):
        u = ((xs - centre[0]) * along[0] + (ys - centre[1]) * along[1]) / half_wide
        v = ((xs - centre[0]) * downward[0] + (ys - centre[1]) * downward[1]) / half_high
        q = np.clip(u * u + v * v, 0, 1) ** firm
        return peak * (1 - q) ** 2 if firm == 1 else peak * (1 - q)

    glow = np.zeros(xs.shape, np.float32)
    if style in (1, 2, 4):
        for c in centres:
            glow = np.maximum(glow, oval(c, WIDE * unit, HIGH * unit, PEAK))
    if style == 4:  # and between them, over her nose
        middle = (centres[0] + centres[1]) / 2
        half = np.linalg.norm(centres[1] - centres[0]) / 2 + 0.25 * unit
        glow = np.maximum(glow, oval(middle, half, HIGH * 0.85 * unit, PEAK * 0.9))
    if style == 5:
        for c in centres:
            glow = np.maximum(glow, oval(c, SPOT * unit, SPOT * unit, PEAK, firm=3))

    strokes = np.zeros(xs.shape, np.float32)
    if style in (1, 3, 4):
        im = Image.new("L", ((x1 - x0) * SS, (y1 - y0) * SS))
        d = ImageDraw.Draw(im)
        lean = math.radians(STROKE_LEAN)
        way = along * math.cos(lean) - downward * math.sin(lean)  # up and to the right
        thick = max(1.0, STROKE_WIDE * unit * SS)
        for c in centres:
            for k in STROKES:
                mid = c + along * k * STROKE_GAP * unit
                half = STROKE_LONG * unit / 2 * (1.0 if k == 0 else 0.86)
                ends = [((p[0] - x0) * SS, (p[1] - y0) * SS) for p in (mid - way * half, mid + way * half)]
                d.line(ends, fill=255, width=int(round(thick)))
                for ex, ey in ends:  # round ends
                    d.ellipse([ex - thick / 2, ey - thick / 2, ex + thick / 2, ey + thick / 2], fill=255)
        strokes = np.asarray(im.reduce(SS), np.float32) / 255 * (STROKE_PEAK if style != 3 else 0.9)

    glow_colour = skin * (1 - MIX) + PINK * MIX
    stroke_colour = skin * (1 - STROKE_MIX) + DEEP * STROKE_MIX
    alpha = strokes + glow * (1 - strokes)
    rgb = (stroke_colour * strokes[..., None] + glow_colour * (glow * (1 - strokes))[..., None]) / np.maximum(alpha, 1e-6)[..., None]
    alpha[alpha < FLOOR] = 0
    out = np.zeros((H, W, 4), np.float32)
    out[y0:y1, x0:x1, :3] = np.where(alpha[..., None] > 0, rgb, 0)
    out[y0:y1, x0:x1, 3] = alpha
    return out


def from_picture(shape, eyes, picture, size=1.0, inward=0.0, down=0.0, mirror=False):
    """A blush from your own picture of ONE cheek's mark (RGBA from 0 to 1, clear round it): put
    under each eye, as wide as the kit's own oval, turned with her face. mirror flips it for the
    cheek on the right of the picture."""
    H, W = shape[:2]
    centres, eye, along, _ = cheeks(eyes, inward, down)
    mark = Image.fromarray((np.clip(picture, 0, 1) * 255).round().astype(np.uint8), "RGBA")
    box = mark.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if not box:
        raise ValueError("the picture is clear all over")
    mark = mark.crop(box)
    wide = max(2, round(2 * WIDE * eye * size))
    mark = mark.resize((wide, max(2, round(mark.height * wide / mark.width))), Image.LANCZOS)
    turn = -math.degrees(math.atan2(along[1], along[0]))  # Pillow turns the other way
    whole = Image.new("RGBA", (W, H))
    for i, c in enumerate(centres):
        one = mark.transpose(Image.FLIP_LEFT_RIGHT) if mirror and i == 1 else mark
        one = one.rotate(turn, resample=Image.BICUBIC, expand=True)
        whole.alpha_composite(one, (int(round(c[0] - one.width / 2)), int(round(c[1] - one.height / 2))))
    out = np.asarray(whole, np.float32) / 255
    out[out[..., 3] < FLOOR] = 0
    return out


def as_image(rgba):
    return Image.fromarray((np.clip(rgba, 0, 1) * 255).round().astype(np.uint8), "RGBA")
