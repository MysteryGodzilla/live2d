"""Face parts the avatar rig needs and See-through didn't give us, made from each character's own
drawing and layers (see layers.py for the layers themselves).

`live2d.py parts <command> <name>` runs it. By hand, with See-through's Python, as layers.py is:
  <see-through python> -I parts.py <command> <name>

  eyewhite <name>
      the whites of her eyes as their own layer, cut from the drawing: the near-white inside each
      eye's lash outline, together with the iris, and reaching a little under the lashes so no gap
      shows as the lids close. The rig closes an eye only if it has an eye-white layer, and clips
      the iris to it. Her lashes go above her irises too, as a drawing has them
  closed-eyes <name>
      eye_close: her closed eyes, drawn as a lid line from corner to corner of each eye, sagging a
      little as a sleeping eye does, as thick as half her upper lash and in her own lash colours.
      With this the rig shows her own closed eyes instead of its stock black ones
  mouth <name> [--style <number> | --file <picture>] [--width <share>] [--flip]
      her own small mouth becomes mouth_close (the rig shows it while the mouth is shut), and
      mouth_open is drawn for her. With nothing more it is the kit's style 1, as it always was.
      --style picks another of the kit's open mouths by number (mouth-sheet shows them): each is a
      set of masks in mouths/, beside this script, sized to her face and coloured from her own
      mouth's line. --file takes your own picture of an open mouth instead, colours and all: a PNG
      that is clear round the mouth, or one on a plain background, which is taken out. --width is
      how wide it is, as a share of her face's width (0.09 for most styles, 0.11 for a picture);
      --flip mirrors it (a fang on her other side)
  mouth-sheet [<name>]
      the kit's open mouths, numbered: with a name, each one on her own face, in her colours, as
      <out>/parts/<name>-mouths.png; with none, on plain skin as mouths/sheet.png. Each picture is
      also saved by itself, <number>-<name>.png, in a folder beside the sheet (the GUI shows those)
  blush <name> [--style <number> | --file <picture>] [--size <times>] [--in <eye widths>]
               [--down <eye widths>] [--mirror]
      her blush as a layer of her own, in place of the one build draws when she has none (the
      kit's style 1). --style is one of blush.py's (blush-sheet shows them); --file is your own
      picture of ONE cheek's mark, put under each eye (--mirror flips it for the other cheek).
      --size makes it bigger or smaller, --in moves the marks toward her nose (or apart, with a
      minus) and --down lower. `layers remove <name> blush "why"` goes back to build's own
  blush-sheet [<name>]
      the blush styles, numbered, each on her own face: <out>/parts/<name>-blushes.png; with no
      name, on a plain drawn face as blushes/sheet.png beside this script. Each picture is also
      saved by itself, as the mouths are
  grin <name> [--no-tongue]
      for a character drawn with her mouth open (a grin): her drawn mouth is kept as
      layers/mouth-drawn.png and is mouth_close until w-mouth draws one; mouth_open is that mouth
      drawn taller from its top edge, a bigger laugh when the rig opens her mouth (--no-tongue:
      with its tongue the colour of the inside). The rig shows mouth_open at half height, growing
      to full as the mouth opens, so at 0.54 open it's her grin's own size: her rig.json's "rest"
      can hold her there, so she rests grinning as drawn
  mouth-from <name> <other>
      her mouth layer replaced by her drawn mouth from another of her drawings (its
      layers/mouth-drawn.png, from grin), turned and scaled so its top corners land on this
      drawing's: one whose working drawing has her tongue out takes her idle grin
      (mimi/working from mimi). This drawing's own mouth is kept as mouth-own.png. Then grin
      and w-mouth as usual
  w-mouth <name>
      after grin: mouth_close becomes a drawn ω (a cat's mouth), on her drawn mouth's top line and
      tilted with it, in her mouth's own dark colour: what she shows with her mouth shut (dozing,
      working)
  mouth-masters
      draws the kit's open mouths' masks (mouths/<number>-line.png, -inside, -tongue, -teeth:
      white on clear, 240 by 180) where they aren't there yet. Redraw one in any paint program and
      run mouth again for each character. A style of your own is a new number: its -line and
      -inside masks at least, in the same place and size as the others

Each command saves the part into layers/parts/, puts it in layers/layers.json's order and notes
what it did there; then run layers.py check and build as usual."""
import os, sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blush as B  # noqa: E402
import kit  # noqa: E402
import layers as L  # noqa: E402

MOUTHS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mouths")

WHITE = 0.93     # eye whites: green and blue at least this (skin has less green)
UNDER = 2        # eye whites reach this many pixels under the lashes
SAG = 0.2        # closed eyes: the lid line sags this share of the eye's height at the middle
MOUTH_W = 0.09   # open mouth: a mask's whole span is this share of her face's width
FILE_W = 0.11    # ...and your own picture of one is this share
SS = 8           # drawn parts are drawn this many times bigger than they're used, then shrunk

# The shared open mouth's masters: 240 x 180, the mouth from x 20 to 220 with its top corners at
# y 34. The point (120, 38), the middle of its top edge, goes where her closed mouth is.
MASTER = (240, 180)
MASTER_SPAN = (20, 220)
MASTER_PIN = (120, 38)
INSIDE = np.array([0.55, 0.20, 0.27], np.float32)  # a dark rose, mixed with her line colour
TONGUE = np.array([0.95, 0.62, 0.66], np.float32)
TEETH = np.array([0.99, 0.97, 0.95], np.float32)
# The kit's open mouths: number -> (name, how wide its span is next to style 1's). A number with
# masks in mouths/ and no line here is one of your own, as wide as style 1.
MOUTH_STYLES = {1: ("classic", 1.0), 2: ("small", 1.0), 3: ("smile", 1.3), 4: ("laugh", 1.3),
                5: ("triangle", 1.1), 6: ("cat", 1.1), 7: ("fang", 1.3), 8: ("oh", 1.0)}
MOUTH_PARTS = ("inside", "tongue", "teeth", "line")  # painted in this order; inside and line are needed
PLAIN_SKIN = np.array([0.99, 0.90, 0.86], np.float32)   # mouth-sheet with no name
PLAIN_LINE = np.array([0.42, 0.20, 0.20], np.float32)
KEY = 0.13       # a picture with no clear part: this close to its border's colour is background


def place(info, layer, above):
    """Put layer just above another in the stacking order."""
    if layer in info["order"]:
        info["order"].remove(layer)
    info["order"].insert(info["order"].index(above) + 1, layer)


def eyes(iris):
    """The two eyes: masks of the two biggest iris pieces, left one first."""
    labels, n = ndimage.label(iris > 0.5, structure=np.ones((3, 3)))
    if n < 2:
        sys.exit("irides: fewer than two pieces; can't tell the eyes apart")
    sizes = ndimage.sum(np.ones(iris.shape), labels, range(1, n + 1))
    two = 1 + np.argsort(sizes)[-2:]
    two = sorted(two, key=lambda k: ndimage.center_of_mass(labels == k)[1])
    return [labels == k for k in two]


def sides(shape, eye_masks):
    """Split the frame down the middle between the two eyes."""
    xl = ndimage.center_of_mass(eye_masks[0])[1]
    xr = ndimage.center_of_mass(eye_masks[1])[1]
    mid = int(round((xl + xr) / 2))
    cols = np.arange(shape[1])
    return [np.broadcast_to(cols < mid, shape), np.broadcast_to(cols >= mid, shape)]


def do_eyewhite(name):
    info = L.load(name)
    for need in ("eyelash", "irides"):
        if need not in info["order"]:
            sys.exit(f"{need}: she has no such layer")
    orig, _ = L.drawing(name, info["frame"])
    lash = L.read_part(name, "eyelash")[..., 3]
    iris = L.read_part(name, "irides")[..., 3]
    white = (orig[..., 1] > WHITE) & (orig[..., 2] > WHITE)
    opening = np.zeros(iris.shape, bool)
    two = eyes(iris)
    for eye, side in zip(two, sides(iris.shape, two)):
        ys, xs = np.nonzero((lash > 0.15) & side)
        box = np.zeros(iris.shape, bool)
        box[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = True
        seed = (white & box) | eye
        # Only the white that joins the iris: not highlights on the skin nearby.
        labels, _ = ndimage.label(seed, structure=np.ones((3, 3)))
        keep = np.unique(labels[ndimage.binary_dilation(eye, iterations=2) & seed])
        seed = np.isin(labels, keep[keep > 0])
        seed = ndimage.binary_fill_holes(ndimage.binary_closing(seed, np.ones((3, 3)), iterations=2))
        opening |= seed
    under = ndimage.binary_dilation(opening, np.ones((3, 3)), iterations=UNDER) & (lash > 0.15)
    shape = opening | under
    # Colour: the drawing's own white where it shows; under the iris and lashes, the nearest white.
    shown = shape & white
    _, (iy, ix) = ndimage.distance_transform_edt(~shown, return_indices=True)
    rgb = orig[iy, ix] if shown.any() else np.ones_like(orig)
    # Soften the edge a little, inside the shape only.
    alpha = np.clip(ndimage.gaussian_filter(shape.astype(np.float32), 0.6) * 1.5, 0, 1) * shape
    part = np.dstack([rgb, alpha]).astype(np.float32)
    L.write_part(name, "eyewhite", part)
    above = "mouth" if "mouth" in info["order"] else "face"
    for later in ("mouth_close", "mouth_open"):
        if later in info["order"]:
            above = later
    place(info, "eyewhite", above)
    # The lashes go over the irises, as in the drawing.
    order = info["order"]
    if order.index("eyelash") < order.index("irides"):
        place(info, "eyelash", "irides")
        L.note(info, "eyelash moved above irides: the drawing has her lashes over her irises")
    L.note(info, f"eyewhite cut from the drawing: {int(opening.sum())} px of eye, "
                 f"reaching {UNDER} px under the lashes")
    L.save(name, info)
    print(f"{name}: eyewhite, {int(shape.sum())} px; order {', '.join(info['order'])}")


def runs_above(col_alpha, mid):
    """The run of lash pixels nearest above row mid in one column: (top, bottom) or None."""
    on = col_alpha > 0.15
    y = int(np.floor(mid))
    while y >= 0 and not on[y]:
        y -= 1
    if y < 0:
        return None
    bottom = y
    while y >= 0 and on[y]:
        y -= 1
    return y + 1, bottom


def lash_colours(lash_rgba, side):
    """Her lashes' darkest colour and a middle one, for the closed eye's two ends."""
    rgb = lash_rgba[..., :3][(lash_rgba[..., 3] > 0.9) & side]
    order = np.argsort(rgb @ np.array([0.3, 0.59, 0.11], np.float32))
    n = len(order)
    return rgb[order[:max(1, n // 5)]].mean(0), rgb[order[n // 2:max(n // 2 + 1, n * 4 // 5)]].mean(0)


def stroke(draw, pts, widths, origin):
    """A filled stroke through pts, widths across, onto a mask drawn SS times bigger."""
    d = np.gradient(pts, axis=0)
    n = np.stack([-d[:, 1], d[:, 0]], 1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
    edge = np.concatenate([pts + n * widths[:, None] / 2, (pts - n * widths[:, None] / 2)[::-1]])
    draw.polygon([tuple(p) for p in (edge - origin) * SS], fill=255)


def do_closed_eyes(name):
    info = L.load(name)
    if "eyewhite" not in info["order"]:
        sys.exit("make her eyewhite first: parts.py eyewhite " + name)
    lash_rgba = L.read_part(name, "eyelash")
    lash = lash_rgba[..., 3]
    white = L.read_part(name, "eyewhite")[..., 3] > 0.5
    iris = L.read_part(name, "irides")[..., 3]
    H, W = lash.shape
    out = np.zeros_like(lash_rgba)
    two = eyes(iris)
    middle = sum(ndimage.center_of_mass(e)[1] for e in two) / 2
    for side in sides(lash.shape, two):
        open_ = white & side & ~(lash > 0.5)
        ys, xs = np.nonzero(open_)
        ends = [np.array([x, ys[np.abs(xs - x) <= 1].mean()], np.float32) for x in (xs.min(), xs.max())]
        p_in, p_out = sorted(ends, key=lambda p: abs(p[0] - middle))
        height = max(open_[:, x].sum() for x in range(xs.min(), xs.max() + 1))
        # How thick her upper lash is: the closed lid is drawn about half that.
        runs = [runs_above(lash[:, x], (np.nonzero(open_[:, x])[0].mean()))
                for x in range(xs.min(), xs.max() + 1) if open_[:, x].any()]
        thick = float(np.clip(0.5 * np.median([r[1] - r[0] + 1 for r in runs if r]), 2, 6))
        dark, light = lash_colours(lash_rgba, side)
        out_dir = np.sign(p_out[0] - p_in[0])

        # The lid: corner to corner, sagging, thickest at the outer end, with a short droop past it.
        u = np.linspace(0, 1.15, 120)
        pts = p_in + np.outer(u, p_out - p_in)
        pts[:, 1] += SAG * height * np.sin(np.pi * np.minimum(u, 1))
        pts[:, 1] += np.where(u > 1, (u - 1) / 0.15 * 0.3 * height, 0)
        widths = np.where(u <= 1, thick * (1 - (1 - np.minimum(u, 1)) ** 6) * (0.35 + 0.65 * u ** 0.8),
                          thick * (1 - (u - 1) / 0.15))
        lo = np.floor(np.minimum(p_in, p_out) - height).astype(int)
        hi = np.ceil(np.maximum(p_in, p_out) + height).astype(int)
        lo, hi = np.maximum(lo, 0), np.minimum(hi, [W, H])
        mask = Image.new("L", tuple((hi - lo) * SS))
        draw = ImageDraw.Draw(mask)
        stroke(draw, pts, widths, lo)
        # Two lashes hanging from the outer part of the lid.
        for at, length in ((0.72, 0.30), (0.88, 0.24)):
            k = int(np.argmin(np.abs(u - at)))
            root = pts[k] + np.array([0, widths[k] * 0.3])
            way = np.array([out_dir * 0.7, 1.0]) / np.hypot(0.7, 1.0)
            v = np.linspace(0, 1, 20)
            stroke(draw, root + np.outer(v * length * height, way), thick * 0.6 * (1 - v), lo)
        a = np.asarray(mask.reduce(SS), np.float32) / 255
        # Colour: her lighter lash colour at the inner end, her darkest at the outer end.
        gy, gx = np.mgrid[lo[1]:hi[1], lo[0]:hi[0]]
        axis = p_out - p_in
        t = ((gx - p_in[0]) * axis[0] + (gy - p_in[1]) * axis[1]) / (axis @ axis)
        t = np.clip((t - 0.15) / 0.6, 0, 1)
        t = t * t * (3 - 2 * t)
        rgb = light + (dark - light) * t[..., None]
        region = out[lo[1]:hi[1], lo[0]:hi[0]]
        region[..., :3] = np.where(a[..., None] > region[..., 3:4], rgb, region[..., :3])
        region[..., 3] = np.maximum(region[..., 3], a)
    L.write_part(name, "eye_close", out)
    place(info, "eye_close", "eyelash")
    L.note(info, f"eye_close drawn: a lid line from corner to corner of each eye, sagging "
                 f"{SAG:.0%} of the eye's height, in her own lash colours")
    L.save(name, info)
    print(f"{name}: eye_close; order {', '.join(info['order'])}")


def mouth_master(style):
    """One open mouth's masks (inside, tongue, teeth, line: those it has), drawn SS times bigger and
    shrunk so the edges are smooth. Each is two edges between its corners (or a ring), with a
    heavier upper line, as a mouth is drawn."""
    W, H = MASTER
    u = np.linspace(0, 1, 240)
    s = 2 * u - 1
    lobe = lambda p: np.clip(1 - np.abs(s) ** p, 0, 1)

    def span(x0, x1, top, bottom, top_w=16.0, bottom_w=9.0):
        x = x0 + (x1 - x0) * u
        return {"x": x, "top": top, "inside": np.concatenate([np.stack([x, top], 1), np.stack([x, bottom], 1)[::-1]]),
                "lines": [(np.stack([x, top], 1), np.full(len(x), top_w)), (np.stack([x, bottom], 1), np.full(len(x), bottom_w))],
                "dots": [(x0, top[0], top_w * 0.5625), (x1, top[-1], top_w * 0.5625)]}

    def ring(cx, cy, rx, up, down, top_w=12.0, bottom_w=8.0):
        t = np.linspace(0, 2 * np.pi, 361)
        pts = np.stack([cx + rx * np.cos(t), cy + np.where(np.sin(t) < 0, up, down) * np.sin(t)], 1)
        return {"inside": pts, "lines": [(pts, bottom_w + (top_w - bottom_w) * (0.5 - 0.5 * np.sin(t)))], "dots": []}

    def strip(m, depth):  # upper teeth: a band under the top edge
        return np.concatenate([np.stack([m["x"], m["top"]], 1), np.stack([m["x"], m["top"] + depth], 1)[::-1]])

    teeth, tongue = [], None
    if style == 1:    # round and deep, the upper lip a little low in the middle
        m = span(20, 220, 34 + 8 * (1 - s ** 2), 34 + 120 * lobe(2.5) ** 0.7)
        tongue = (120, 150, 62, 38)
    elif style == 2:  # a small oval: talking quietly
        m = ring(120, 66, 36, 28, 32)
        tongue = (120, 94, 24, 14)
    elif style == 3:  # an open smile: wide and shallow, upper teeth showing
        m = span(20, 220, 34 + 10 * (1 - s ** 2), 34 + 80 * lobe(2.2) ** 0.75)
        teeth, tongue = [strip(m, 22 * lobe(2.5))], (120, 118, 58, 26)
    elif style == 4:  # a laugh: wide and deep
        m = span(24, 216, 34 + 5 * (1 - s ** 2), 34 + 128 * lobe(3.2) ** 0.8)
        teeth, tongue = [strip(m, 24 * lobe(3.0))], (120, 152, 64, 40)
    elif style == 5:  # a triangle, point down: a shout
        m = span(30, 210, 34 + 3 * (1 - s ** 2), 34 + 120 * lobe(1.3))
        teeth, tongue = [strip(m, 16 * lobe(2.0))], (120, 146, 36, 30)
    elif style == 6:  # a cat's mouth, open: the upper lip in two curves
        m = span(30, 210, 34 + 20 * np.sin(np.pi * s) ** 2, 34 + 100 * lobe(2.6) ** 0.75)
        tongue = (120, 128, 50, 26)
    elif style == 7:  # the open smile with one fang
        m = span(20, 220, 34 + 10 * (1 - s ** 2), 34 + 80 * lobe(2.2) ** 0.75)
        at = lambda v: (np.interp(v, s, m["x"]), np.interp(v, s, m["top"]))
        teeth = [np.array([at(-0.64), at(-0.36), (at(-0.5)[0], at(-0.5)[1] + 34)])]
        tongue = (120, 118, 58, 26)
    elif style == 8:  # a tall oval: "oh"
        m = ring(120, 88, 40, 50, 54, top_w=12.0, bottom_w=9.0)
        tongue = (120, 132, 26, 14)
    else:
        sys.exit(f"mouth style {style}: the kit draws {', '.join(str(k) for k in MOUTH_STYLES)}")

    def canvas():
        im = Image.new("L", (W * SS, H * SS))
        return im, ImageDraw.Draw(im)
    scaled = lambda pts: [(a * SS, b * SS) for a, b in pts]
    inside, d = canvas()
    d.polygon(scaled(m["inside"]), fill=255)
    out = {"inside": inside}
    if tongue:
        im, d = canvas()
        cx, cy, rx, ry = tongue
        d.ellipse([(cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS], fill=255)
        out["tongue"] = Image.fromarray(np.minimum(np.asarray(im), np.asarray(inside)))
    if teeth:
        im, d = canvas()
        for shape in teeth:
            d.polygon(scaled(shape), fill=255)
        out["teeth"] = Image.fromarray(np.minimum(np.asarray(im), np.asarray(inside)))
    line, d = canvas()
    for pts, widths in m["lines"]:
        stroke(d, pts, widths, 0)
    for cx, cy, r in m["dots"]:
        d.ellipse([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS], fill=255)
    out["line"] = line
    return {k: im.reduce(SS) for k, im in out.items()}


def mask_path(style, part):
    return os.path.join(MOUTHS, f"{style}-{part}.png")


def mouth_styles():
    """The numbers there are masks for: the kit's, and any you added."""
    there = {int(f.split("-")[0]) for f in os.listdir(MOUTHS) if f.endswith("-line.png") and f.split("-")[0].isdigit()}
    return sorted(there)


def style_name(style):
    return MOUTH_STYLES.get(style, ("yours", 1.0))[0]


def do_mouth_masters():
    os.makedirs(MOUTHS, exist_ok=True)
    for style in MOUTH_STYLES:
        made = []
        masks = None
        for part in MOUTH_PARTS:
            if os.path.exists(mask_path(style, part)):
                continue
            masks = masks or mouth_master(style)
            if part in masks:
                masks[part].save(mask_path(style, part), optimize=True)
                made.append(part)
        print(f"{style} {style_name(style)}: " + (", ".join(made) + " drawn" if made else "already there, left alone"))


def styled_mouth(style, line, unit, flip=False):
    """A style's masks as a mouth in her colours: RGBA from 0 to 1, and where its pin is in it. unit
    is how many pixels the masks' whole span takes."""
    if not os.path.exists(mask_path(style, "line")) or not os.path.exists(mask_path(style, "inside")):
        sys.exit(f"mouth style {style}: no masks in {MOUTHS} (there are {', '.join(str(k) for k in mouth_styles())}; "
                 "`parts mouth-masters` draws the kit's)")
    k = unit / (MASTER_SPAN[1] - MASTER_SPAN[0])
    size = (max(1, round(MASTER[0] * k)), max(1, round(MASTER[1] * k)))
    inside = INSIDE * 0.7 + line * 0.3
    rgb = np.zeros(size[::-1] + (3,), np.float32)
    alpha = np.zeros(size[::-1], np.float32)
    for part, colour in (("inside", inside), ("tongue", TONGUE), ("teeth", TEETH), ("line", line)):
        if not os.path.exists(mask_path(style, part)):
            continue
        im = Image.open(mask_path(style, part)).convert("L")
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        m = np.asarray(im.resize(size, Image.BOX), np.float32) / 255
        rgb = colour * m[..., None] + rgb * (1 - m[..., None])
        alpha = m + alpha * (1 - m)
    # rgb was built over black (colour times alpha): divide to get each pixel's own colour.
    rgb = np.where(alpha[..., None] > 0, rgb / np.maximum(alpha[..., None], 1e-6), 0)
    return np.dstack([rgb, alpha]), (MASTER_PIN[0] * k, MASTER_PIN[1] * k)


def cut_out(picture):
    """Your own picture as RGBA from 0 to 1, clear round what it shows. A picture with no clear
    part has its background taken out: everything joined to its border that is close to the
    border's colour. A dark outline stops it, so a mouth or a mark drawn on plain skin comes out
    whole. A clear PNG is still the better thing to give."""
    im = np.asarray(Image.open(picture).convert("RGBA"), np.float32) / 255
    if im[..., 3].min() < 0.5:
        return im
    edge = np.concatenate([im[0, :, :3], im[-1, :, :3], im[:, 0, :3], im[:, -1, :3]])
    near = np.abs(im[..., :3] - np.median(edge, axis=0)).max(axis=2) < KEY
    labels, _ = ndimage.label(near)
    outer = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    back = np.isin(labels, outer[outer > 0])
    im[..., 3] = ndimage.uniform_filter((~back).astype(np.float32), 3)  # a soft edge, not a stair
    if not (im[..., 3] > 0.5).any():
        sys.exit(f"{picture}: nothing left once its background is out; give a PNG that is clear round the part")
    return im


def file_mouth(picture, wide, flip=False):
    """Your own open mouth, wide pixels across, and its pin: the middle of its top edge."""
    im = cut_out(picture)
    ys, xs = np.nonzero(im[..., 3] > 0.1)
    part = Image.fromarray((im[ys.min():ys.max() + 1, xs.min():xs.max() + 1] * 255).round().astype(np.uint8), "RGBA")
    if flip:
        part = part.transpose(Image.FLIP_LEFT_RIGHT)
    size = (max(1, round(wide)), max(1, round(part.height * wide / part.width)))
    part = np.asarray(part.resize(size, Image.LANCZOS), np.float32) / 255
    return part, (size[0] / 2, 0.03 * size[1])


def mouth_fit(name, info):
    """What an open mouth is fitted to: where her closed mouth is, its line's colour, her face's width."""
    if "mouth_close" not in info["order"]:
        sys.exit("she has no mouth layer to fit the open mouth to")
    shut = L.read_part(name, "mouth_close")
    a = shut[..., 3]
    cy, cx = ndimage.center_of_mass(a)
    # Her line colour: the most solid of her mouth's own pixels, darker, as an open mouth's
    # outline is drawn firmer than a faint closed one.
    strong = a >= np.quantile(a[a > 0], 0.8)
    line = shut[..., :3][strong].mean(0) * 0.7
    face = L.read_part(name, "face")[..., 3] > 0.5
    fx = np.nonzero(face.any(axis=0))[0]
    return (cx, cy), line, float(fx.max() - fx.min())


def face_turn(name, info):
    """How far her face is turned in her drawing, in degrees (clockwise on the screen), read from
    her eyes: what is put on her face is turned with it. 0 when her eyes can't be told apart."""
    eyes = [L.read_part(name, layer)[..., 3] for layer in ("eyewhite", "eyelash", "irides") if layer in info["order"]]
    found = B.eyes_of(eyes, L.read_part(name, "face")[..., 3]) if eyes and "face" in info["order"] else None
    if not found:
        return 0.0
    along = B.cheeks(found)[2]
    return float(np.degrees(np.arctan2(along[1], along[0])))


def in_frame(frame, small, pin, at, turn=0.0):
    """A small picture as a layer as big as her frame, its pin at the point `at`, turned about its
    pin by `turn` degrees (clockwise on the screen)."""
    if abs(turn) >= 0.5:
        im = Image.fromarray((np.clip(small, 0, 1) * 255).round().astype(np.uint8), "RGBA")
        h, w = small.shape[:2]
        im = im.rotate(-turn, resample=Image.BICUBIC, expand=True)  # Pillow turns the other way
        t = np.radians(turn)
        dx, dy = pin[0] - w / 2, pin[1] - h / 2
        pin = (im.width / 2 + dx * np.cos(t) - dy * np.sin(t), im.height / 2 + dx * np.sin(t) + dy * np.cos(t))
        small = np.asarray(im, np.float32) / 255
    W, H = frame
    part = np.zeros((H, W, 4), np.float32)
    left, top = int(round(at[0] - pin[0])), int(round(at[1] - pin[1]))
    h, w = small.shape[:2]
    x0, y0, x1, y1 = max(0, left), max(0, top), min(W, left + w), min(H, top + h)
    part[y0:y1, x0:x1] = small[y0 - top:y1 - top, x0 - left:x1 - left]
    return part, (left, top, w, h)


def do_mouth(name, style=None, file=None, width=None, flip=False):
    info = L.load(name)
    order = info["order"]
    if "mouth" in order:
        os.replace(L.part_path(name, "mouth"), L.part_path(name, "mouth_close"))
        L.rename_sharp(name, "mouth", "mouth_close")
        order[order.index("mouth")] = "mouth_close"
        L.note(info, "mouth renamed mouth_close: her own small mouth, shown while it's shut")
    at, line, face_w = mouth_fit(name, info)
    if file:
        wide = (width or FILE_W) * face_w
        small, pin = file_mouth(file, wide, flip)
        what = f"mouth_open from {os.path.basename(file)}, {wide:.0f} px wide"
    else:
        style = style or 1
        unit = (width or MOUTH_W * MOUTH_STYLES.get(style, ("", 1.0))[1]) * face_w
        small, pin = styled_mouth(style, line, unit, flip)
        what = (f"mouth_open from the kit's open mouth {style} ({style_name(style)}), {unit:.0f} px wide, line colour "
                f"#{''.join(f'{round(v * 255):02x}' for v in line)}")
    turn = face_turn(name, info)
    part, (left, top, w, h) = in_frame(info["frame"], small, pin, at, turn)
    L.write_part(name, "mouth_open", part)
    place(info, "mouth_open", "mouth_close")
    L.note(info, what + (", mirrored" if flip else "") + (f", turned {turn:+.1f} degrees with her face" if abs(turn) >= 0.5 else ""))
    L.save(name, info)
    print(f"{name}: mouth_open {w}x{h} at {left},{top}; order {', '.join(order)}")


# ---- Her blush, and the sheets to choose from ----------------------------------------------------

def her_eyes(name, info):
    """Her two eyes' boxes and her face layer, for the blush."""
    face = L.read_part(name, "face")
    eyes = [L.read_part(name, layer)[..., 3] for layer in ("eyewhite", "eyelash", "irides") if layer in info["order"]]
    found = B.eyes_of(eyes, face[..., 3]) if eyes else None
    if not found:
        sys.exit(f"{name}: no eye found on each side of her face (her eyewhite, eyelash and irides layers)")
    return found, face


def do_blush(name, style=None, file=None, size=1.0, inward=0.0, down=0.0, mirror=False):
    info = L.load(name)
    eyes, face = her_eyes(name, info)
    if file:
        part = B.from_picture(face.shape, eyes, cut_out(file), size, inward, down, mirror)
        what = f"blush from {os.path.basename(file)}, under each eye" + (", mirrored for the second" if mirror else "")
    else:
        style = style or B.DEFAULT
        if style not in B.STYLES:
            sys.exit(f"blush style {style}: there are " + ", ".join(f"{k} ({v})" for k, v in B.STYLES.items()))
        part = B.draw(face.shape, eyes, B.skin_of(face), style, size, inward, down)
        what = f"blush drawn: the kit's style {style} ({B.STYLES[style]})"
    moved = "".join(f", {word} {v:g}" for word, v, rest in (("size", size, 1.0), ("in", inward, 0.0), ("down", down, 0.0)) if v != rest)
    L.write_part(name, "blush", part)
    place(info, "blush", "face")
    L.note(info, what + moved)
    L.save(name, info)
    ys, xs = np.nonzero(part[..., 3] > 0)
    print(f"{name}: blush, {xs.max() - xs.min() + 1}x{ys.max() - ys.min() + 1} at {xs.min()},{ys.min()}; order {', '.join(info['order'])}")


def label_font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # an older Pillow
        return ImageFont.load_default()


def tile_name(label):
    """A sheet's label as a file name: "3  smile" -> 3-smile, "hers now" -> now."""
    words = label.replace("hers now", "now").split()
    return "-".join(w.strip(",.").lower() for w in words)


def sheet(cells, path, wide=340, cols=4):
    """Numbered pictures side by side: cells are (label, RGB from 0 to 1). Each picture is also saved
    by itself in a folder beside the sheet, named for its label (the GUI shows them as choices)."""
    font, bar = label_font(22), 34
    pics = []
    tiles = os.path.splitext(path)[0] if os.path.basename(path) != "sheet.png" else os.path.join(os.path.dirname(path), "previews")
    os.makedirs(tiles, exist_ok=True)
    for old in os.listdir(tiles):
        if old.endswith(".png"):
            os.remove(os.path.join(tiles, old))
    for label, rgb in cells:
        im = Image.fromarray((np.clip(rgb, 0, 1) * 255).round().astype(np.uint8), "RGB")
        im.resize((wide, max(1, round(im.height * wide / im.width))), Image.LANCZOS).save(
            os.path.join(tiles, tile_name(label) + ".png"), optimize=True)
        im = im.resize((wide, max(1, round(im.height * wide / im.width))), Image.LANCZOS)
        cell = Image.new("RGB", (wide, im.height + bar), (32, 32, 36))
        cell.paste(im, (0, bar))
        ImageDraw.Draw(cell).text((8, 4), label, fill=(255, 255, 255), font=font)
        pics.append(cell)
    cols = min(cols, len(pics))
    rows = -(-len(pics) // cols)
    high = max(p.height for p in pics)
    out = Image.new("RGB", (cols * wide + (cols + 1) * 6, rows * high + (rows + 1) * 6), (255, 255, 255))
    for i, p in enumerate(pics):
        out.paste(p, (6 + (i % cols) * (wide + 6), 6 + (i // cols) * (high + 6)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path, optimize=True)
    print(path)


def face_box(name, lower=False):
    """A cut round her face (or its lower half, for mouths), with a little room."""
    face = L.read_part(name, "face")[..., 3] > 0.5
    ys, xs = np.nonzero(face)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    w, h = x1 - x0, y1 - y0
    if lower:
        return (max(0, int(x0 + 0.12 * w)), int(y0 + 0.50 * h), int(x1 - 0.12 * w), min(face.shape[0], int(y1 + 0.04 * h)))
    return (max(0, int(x0 - 0.05 * w)), int(y0 + 0.22 * h), min(face.shape[1], int(x1 + 0.05 * w)), min(face.shape[0], int(y1 + 0.04 * h)))


def out_path(name, what):
    return kit.out("parts", f"{L.slug(name)}-{what}.png")


def do_mouth_sheet(name=None):
    if name is None:  # on plain skin, for the kit's README
        cells = []
        for style in mouth_styles():
            small, _ = styled_mouth(style, PLAIN_LINE, 180 * MOUTH_STYLES.get(style, ("", 1.0))[1])
            pad = np.full((250, 340, 3), PLAIN_SKIN, np.float32)
            h, w = small.shape[:2]
            y, x = (250 - h) // 2, (340 - w) // 2
            a = small[..., 3:4]
            pad[y:y + h, x:x + w] = small[..., :3] * a + pad[y:y + h, x:x + w] * (1 - a)
            cells.append((f"{style}  {style_name(style)}", pad))
        return sheet(cells, os.path.join(MOUTHS, "sheet.png"))
    info = L.load(name)
    if "mouth_close" not in info["order"]:
        sys.exit(f"{name}: run `parts mouth {name}` once first, so her own mouth is mouth_close")
    at, line, face_w = mouth_fit(name, info)
    turn = face_turn(name, info)
    x0, y0, x1, y1 = face_box(name, lower=True)
    hidden = L.SHUT | {"mouth_close", "blush"}
    base, _ = L.composite([(layer, L.read_part(name, layer)[y0:y1, x0:x1]) for layer in info["order"] if layer not in hidden])
    cells = []
    if "mouth_open" in info["order"]:
        now = L.read_part(name, "mouth_open")[y0:y1, x0:x1]
        cells.append(("hers now", now[..., :3] * now[..., 3:4] + base * (1 - now[..., 3:4])))
    for style in mouth_styles():
        small, pin = styled_mouth(style, line, MOUTH_W * MOUTH_STYLES.get(style, ("", 1.0))[1] * face_w)
        part = in_frame(info["frame"], small, pin, at, turn)[0][y0:y1, x0:x1]
        cells.append((f"{style}  {style_name(style)}", part[..., :3] * part[..., 3:4] + base * (1 - part[..., 3:4])))
    sheet(cells, out_path(name, "mouths"))


BLUSHES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blushes")


def plain_face():
    """A plain drawn face, for showing the blush styles before any character has one: skin, a jaw
    line, two eyes and a small mouth. RGB from 0 to 1, and the two eyes' boxes."""
    W, H = 340, 250
    im = Image.new("RGB", (W * SS, H * SS), tuple(round(v * 255) for v in PLAIN_SKIN))
    d = ImageDraw.Draw(im)
    eyes = [(92, 62, 142, 112), (198, 62, 248, 112)]
    for x0, y0, x1, y1 in eyes:
        d.ellipse([x0 * SS, y0 * SS, x1 * SS, y1 * SS], fill=(255, 255, 255))
        d.ellipse([(x0 + 12) * SS, (y0 + 6) * SS, (x1 - 12) * SS, (y1 - 2) * SS], fill=(92, 60, 48))
        d.arc([(x0 - 4) * SS, (y0 - 2) * SS, (x1 + 4) * SS, (y1 + 30) * SS], 200, 340, fill=(52, 34, 34), width=5 * SS)
    d.arc([150 * SS, 168 * SS, 190 * SS, 186 * SS], 20, 160, fill=(120, 60, 60), width=3 * SS)
    rgb = np.asarray(im.reduce(SS), np.float32) / 255
    return rgb, eyes


def do_blush_sheet(name=None):
    if name is None:  # on a plain face, for the GUI and the README
        face, eyes = plain_face()
        cells = []
        for style, words in B.STYLES.items():
            mark = B.draw(face.shape, eyes, PLAIN_SKIN, style)
            a = mark[..., 3:4]
            cells.append((f"{style}  {words}", mark[..., :3] * a + face * (1 - a)))
        os.makedirs(BLUSHES, exist_ok=True)
        return sheet(cells, os.path.join(BLUSHES, "sheet.png"), cols=3)
    info = L.load(name)
    eyes, face = her_eyes(name, info)
    x0, y0, x1, y1 = face_box(name)
    skin = B.skin_of(face)
    shown = [layer for layer in info["order"] if layer not in L.SHUT | {"blush"}]
    stack = [(layer, L.read_part(name, layer)[y0:y1, x0:x1]) for layer in shown]
    over = shown.index("face") + 1
    cells = []
    for style, words in B.STYLES.items():
        mark = B.draw(face.shape, eyes, skin, style)[y0:y1, x0:x1]
        mark[..., 3] *= face[y0:y1, x0:x1, 3] > 0.5  # as the rig cuts it off at her face
        rgb, _ = L.composite(stack[:over] + [("blush", mark)] + stack[over:])
        cells.append((f"{style}  {words}", rgb))
    sheet(cells, out_path(name, "blushes"), cols=3)


GRIN = 1.3      # grin: mouth_open is her drawn mouth this many times as tall, from its top edge
DRAWN = "mouth-drawn.png"  # grin: her drawn open mouth, kept beside layers.json (not a layer)
W_WIDTH = 0.11  # w-mouth: the ω this share of her face's width
W_DEPTH = 0.25  # w-mouth: each of its two dips this share of its width deep
W_LINE = 2.4    # w-mouth: its line this thick, in the frame's pixels, thinner at the ends


def drawn_mouth(name, info):
    """Her drawn open mouth. The first time, See-through's mouth layer is kept as layers/mouth-drawn.png
    and becomes mouth_close (what she shows with her mouth shut, until w-mouth draws one)."""
    keep = os.path.join(L.folder(name), DRAWN)
    order = info["order"]
    if "mouth" in order:
        Image.open(L.part_path(name, "mouth")).save(keep, optimize=True)
        os.replace(L.part_path(name, "mouth"), L.part_path(name, "mouth_close"))
        order[order.index("mouth")] = "mouth_close"
        L.note(info, f"mouth renamed mouth_close: her own open mouth as drawn (kept as {DRAWN})")
    if not os.path.exists(keep):
        sys.exit(f"{keep}: missing, and she has no mouth layer to take it from")
    return np.asarray(Image.open(keep).convert("RGBA"), np.float32) / 255


def mouth_colours(rgba):
    """Her open mouth's inside (its darkest solid colour) and tongue (its pink), as drawn."""
    solid = rgba[..., 3] > 0.9
    rgb = rgba[..., :3][solid]
    luma = rgb @ np.array([0.3, 0.59, 0.11], np.float32)
    inside = np.median(rgb[luma <= np.quantile(luma, 0.25)], 0)
    pink = (rgb[:, 0] > 0.75) & (rgb[:, 1] > 0.3) & (rgb[:, 1] < 0.7) & (rgb[:, 2] < 0.8)
    if pink.sum() < 20:
        return inside, None
    return inside, np.median(rgb[pink], 0)


def no_tongue(rgba):
    """The mouth with its tongue the colour of the inside: every pixel on the way from the inside's
    colour to the tongue's taken back to the inside's (the fang and the edges keep theirs)."""
    inside, tongue = mouth_colours(rgba)
    if tongue is None:
        return rgba, 0
    out = rgba.copy()
    axis = tongue - inside
    c = rgba[..., :3]
    t = np.clip(((c - inside) @ axis) / (axis @ axis), 0, 1)
    off = np.linalg.norm(c - (inside + t[..., None] * axis), axis=-1)
    w = t * np.clip(1 - off / 0.2, 0, 1)
    out[..., :3] = c - w[..., None] * axis
    return out, int(((w > 0.5) & (rgba[..., 3] > 0.5)).sum())


def do_grin(name, tongue=True):
    info = L.load(name)
    order = info["order"]
    drawn = drawn_mouth(name, info)
    if "mouth_close" not in order:
        sys.exit("she has no mouth_close layer")
    shut, gone = (drawn, 0) if tongue else no_tongue(drawn)
    ys, xs = np.nonzero(shut[..., 3] > 0)
    top, bottom, left, right = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    piece = Image.fromarray(np.clip(shut[top:bottom, left:right] * 255, 0, 255).round().astype(np.uint8), "RGBA")
    tall = round((bottom - top) * GRIN)
    # Stretched premultiplied, so the soft edges don't pick up the clear pixels' colour.
    pre = np.asarray(piece, np.float32) / 255
    pre[..., :3] *= pre[..., 3:4]
    planes = [Image.fromarray(pre[..., c]).resize((right - left, tall), Image.BICUBIC) for c in range(4)]
    big = np.clip(np.dstack([np.asarray(p) for p in planes]), 0, 1)
    big[..., :3] = np.where(big[..., 3:4] > 1e-4, big[..., :3] / np.maximum(big[..., 3:4], 1e-4), 0)
    W, H = info["frame"]
    part = np.zeros((H, W, 4), np.float32)
    part[top:top + tall, left:right] = big[:H - top]
    L.write_part(name, "mouth_open", part)
    place(info, "mouth_open", "mouth_close")
    what = "her drawn mouth" if tongue else f"her drawn mouth without its tongue ({gone} px)"
    L.note(info, f"mouth_open: {what}, {GRIN} times as tall from its top edge, a bigger laugh")
    L.save(name, info)
    print(f"{name}: mouth_open {right - left}x{tall} at {left},{top}"
          f"{'' if tongue else f', tongue gone ({gone} px)'}; order {', '.join(order)}")


def do_w_mouth(name):
    info = L.load(name)
    drawn = drawn_mouth(name, info)
    a = drawn[..., 3]
    ys, xs = np.nonzero(a > 0.5)
    # Her drawn mouth's top corners: the line her shut mouth takes, tilted as her face is.
    left = np.array([xs.min(), ys[xs <= xs.min() + 1].min()], np.float32)
    right = np.array([xs.max(), ys[xs >= xs.max() - 1].min()], np.float32)
    along = (right - left) / np.linalg.norm(right - left)
    down = np.array([-along[1], along[0]], np.float32)
    if down[1] < 0:
        down = -down
    face = L.read_part(name, "face")[..., 3] > 0.5
    fx = np.nonzero(face.any(axis=0))[0]
    width = W_WIDTH * (fx.max() - fx.min())
    mid = (left + right) / 2 + down * 2
    # ω: down, up to a point in the middle, down, up; a little thinner at the ends.
    u = np.linspace(-1, 1, 200)
    pts = mid + np.outer(u * width / 2, along) + np.outer(W_DEPTH * width * np.abs(np.sin(np.pi * u)), down)
    widths = W_LINE * (0.55 + 0.45 * np.sin(np.pi * (u + 1) / 2) ** 0.5)
    lo = np.floor(pts.min(0) - 6).astype(int)
    hi = np.ceil(pts.max(0) + 6).astype(int)
    mask = Image.new("L", tuple((hi - lo) * SS))
    stroke(ImageDraw.Draw(mask), pts, widths, lo)
    m = np.asarray(mask.reduce(SS), np.float32) / 255
    inside, _ = mouth_colours(drawn)
    W, H = info["frame"]
    part = np.zeros((H, W, 4), np.float32)
    part[lo[1]:hi[1], lo[0]:hi[0], :3] = inside * 0.85
    part[lo[1]:hi[1], lo[0]:hi[0], 3] = m
    L.write_part(name, "mouth_close", part)
    if "mouth_close" not in info["order"]:
        sys.exit("she has no mouth_close layer to replace")
    L.note(info, f"mouth_close drawn: a ω {width:.0f} px wide, on her drawn mouth's top line, in its "
                 f"inside colour darkened")
    L.save(name, info)
    print(f"{name}: mouth_close, a w {width:.0f} px wide at {mid.round(1)}")


def mouth_corners(alpha):
    """A drawn mouth's two top corners, left one first."""
    ys, xs = np.nonzero(alpha > 0.5)
    left = np.array([xs.min(), ys[xs <= xs.min() + 1].min()], np.float64)
    right = np.array([xs.max(), ys[xs >= xs.max() - 1].min()], np.float64)
    return left, right


def do_mouth_from(name, other):
    info = L.load(name)
    if "mouth" not in info["order"]:
        sys.exit(f"{name} has no mouth layer to replace")
    keep = os.path.join(L.folder(other), DRAWN)
    if not os.path.exists(keep):
        sys.exit(f"{keep}: missing; run parts.py grin {other} first")
    src = np.asarray(Image.open(keep).convert("RGBA"), np.float32) / 255
    own = L.read_part(name, "mouth")
    Image.fromarray(np.clip(own * 255, 0, 255).round().astype(np.uint8), "RGBA").save(
        os.path.join(L.folder(name), "mouth-own.png"), optimize=True)
    # The other drawing's mouth turned, scaled and moved so its top corners land on this one's.
    (a0, a1), (b0, b1) = mouth_corners(src[..., 3]), mouth_corners(own[..., 3])
    k = complex(*(b1 - b0)) / complex(*(a1 - a0))
    t = complex(*b0) - k * complex(*a0)
    ik, it = 1 / k, -t / k
    data = (ik.real, -ik.imag, it.real, ik.imag, ik.real, it.imag)
    pre = src.copy()
    pre[..., :3] *= pre[..., 3:4]
    W, H = info["frame"]
    planes = [Image.fromarray(np.ascontiguousarray(pre[..., c])).transform((W, H), Image.AFFINE, data, Image.BICUBIC)
              for c in range(4)]
    out = np.clip(np.dstack([np.asarray(p) for p in planes]), 0, 1)
    out[..., :3] = np.where(out[..., 3:4] > 1e-4, out[..., :3] / np.maximum(out[..., 3:4], 1e-4), 0)
    L.write_part(name, "mouth", out.astype(np.float32))
    L.note(info, f"mouth: her drawn mouth from {other} ({DRAWN}), fitted to this drawing's mouth corners "
                 f"(scale {abs(k):.2f}); this drawing's own kept as mouth-own.png")
    L.save(name, info)
    print(f"{name}: mouth from {other}, scale {abs(k):.2f}, turned {np.degrees(np.angle(k)):.1f} degrees")


def options(rest, words, flags=()):
    """<name> and what follows it: --word value pairs and --flags."""
    given, i = {}, 0
    while i < len(rest):
        key = rest[i].lstrip("-")
        if rest[i].startswith("--") and key in flags:
            given[key] = True
            i += 1
        elif rest[i].startswith("--") and key in words and i + 1 < len(rest):
            given[key] = rest[i + 1]
            i += 2
        else:
            sys.exit(f"{rest[i]}?\n\n{__doc__}")
    return given


def main(args):
    if not args:
        sys.exit(__doc__)
    cmd, rest = args[0], args[1:]
    if cmd == "mouth-from" and len(rest) == 2:
        do_mouth_from(rest[0], rest[1])
    elif cmd == "grin" and len(rest) == 1:
        do_grin(rest[0])
    elif cmd == "grin" and len(rest) == 2 and rest[1] == "--no-tongue":
        do_grin(rest[0], tongue=False)
    elif cmd == "w-mouth" and len(rest) == 1:
        do_w_mouth(rest[0])
    elif cmd == "eyewhite" and len(rest) == 1:
        do_eyewhite(rest[0])
    elif cmd == "closed-eyes" and len(rest) == 1:
        do_closed_eyes(rest[0])
    elif cmd == "mouth" and rest:
        o = options(rest[1:], ("style", "file", "width"), ("flip",))
        if "style" in o and "file" in o:
            sys.exit("give --style or --file, not both")
        do_mouth(rest[0], int(o["style"]) if "style" in o else None, o.get("file"),
                 float(o["width"]) if "width" in o else None, o.get("flip", False))
    elif cmd == "mouth-sheet" and len(rest) <= 1:
        do_mouth_sheet(*rest)
    elif cmd == "blush" and rest:
        o = options(rest[1:], ("style", "file", "size", "in", "down"), ("mirror",))
        if "style" in o and "file" in o:
            sys.exit("give --style or --file, not both")
        do_blush(rest[0], int(o["style"]) if "style" in o else None, o.get("file"), float(o.get("size", 1.0)),
                 float(o.get("in", 0.0)), float(o.get("down", 0.0)), o.get("mirror", False))
    elif cmd == "blush-sheet" and len(rest) <= 1:
        do_blush_sheet(*rest)
    elif cmd == "mouth-masters" and not rest:
        do_mouth_masters()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
