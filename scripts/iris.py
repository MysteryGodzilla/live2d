"""An iris from the kit's library (or a picture of your own) in each of her eyes: `parts iris` and
`parts iris-sheet`, run by parts.py. See its usage.

An upscaled drawing's iris is soft and flat, and the split cuts it with a ragged outline (lash
shading joined on below, a notch where a lock of hair crossed it). Here each of her irises becomes a
clean oval: an upright ellipse fitted to her own iris's outline, the bumps left out, with a round
iris picture stretched into it. The rig still clips it by her eye white, so her lids cover the top
as they did.

The library is irises/<number>-<name>.png beside this script: a round iris filling its picture,
clear outside it. A clear patch inside one (a lash rubbed out by hand) is painted in from the iris
next to it. A new number is a new iris.

Her own irises are kept the first time (layers/<pose>/eyes-drawn/, with `parts eyes`'s), and every
fit starts from their outline, so a second iris is fitted as the first was.
"""
import json, os, re, shutil, sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eyes as E  # noqa: E402
import layers as L  # noqa: E402

IRISES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "irises")
FILE = re.compile(r"([0-9]{1,2})-([a-z0-9-]+)\.png")
KEY = "iris"       # layers.json: the iris she was given, {"style" and "names", or "file", "colour", "mirror", and PLAIN's}
PLAIN = {"size": 1.0, "tall": 1.0, "down": 0.0, "right": 0.0}
SOFT = 1.5         # the oval's edge is this many of the cut's pixels soft (a third of one of her frame's)
GREY = 0.10        # an iris or a colour less colourful than this (saturation, 0 to 1) is a grey
HERS = "hers"      # --colour hers: each eye's own colour, from her drawing
OWN = "own"        # --colour own: the iris's own colours, as it was drawn


# ---- The library ---------------------------------------------------------------------------------

def styles():
    """The kit's irises: {number: (name, path)}."""
    found = {}
    if os.path.isdir(IRISES):
        for f in os.listdir(IRISES):
            m = FILE.fullmatch(f)
            if m:
                found[int(m.group(1))] = (m.group(2), os.path.join(IRISES, f))
    return dict(sorted(found.items()))


def whole(rgba):
    """A round iris picture cropped to what it shows, as RGB with nothing clear in it: each clear or
    half-clear pixel takes the colour of the nearest solid one (a patch rubbed out by hand is painted
    in from the iris beside it, and the corners outside the round are never looked at)."""
    solid = rgba[..., 3] > 0.5
    if not solid.any():
        sys.exit("an iris picture with nothing in it")
    ys, xs = np.nonzero(solid)
    rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    sure = rgba[..., 3] > 0.98
    if not sure.any():
        sure = rgba[..., 3] > 0.5
    near = ndimage.distance_transform_edt(~sure, return_indices=True)[1]
    return rgba[near[0], near[1], :3]


def from_kit(style):
    have = styles()
    if style not in have:
        sys.exit(f"iris {style}: the kit has {', '.join(f'{n} ({v[0]})' for n, v in have.items()) or 'none'}")
    return whole(np.asarray(Image.open(have[style][1]).convert("RGBA"), np.float32) / 255)


def from_file(picture):
    import parts as P
    if not os.path.isfile(picture):
        sys.exit(f"{picture}: no such picture")
    return whole(P.cut_out(picture))


# ---- Another colour -------------------------------------------------------------------------------

def hsv(rgb):
    """RGB from 0 to 1 -> hue, saturation, value, each from 0 to 1."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    v = rgb.max(axis=-1)
    c = v - rgb.min(axis=-1)
    safe = np.where(c > 0, c, 1)
    h = np.where(v == r, ((g - b) / safe) % 6, np.where(v == g, (b - r) / safe + 2, (r - g) / safe + 4)) / 6
    return np.where(c > 0, h, 0.0), np.where(v > 0, c / np.where(v > 0, v, 1), 0.0), v


def rgb_of(h, s, v):
    h, s, v = np.broadcast_arrays(np.asarray(h, np.float32), np.asarray(s, np.float32), np.asarray(v, np.float32))
    i = np.floor(h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return np.stack([np.choose(i, [v, q, p, p, t, v]), np.choose(i, [t, v, v, q, p, p]), np.choose(i, [p, p, t, v, v, q])], axis=-1)


def main_colour(rgb):
    """What colour a picture mostly is, its colourful pixels counting most: (hue, saturation, value)
    of its commonest hue, or None for a grey one."""
    h, s, v = hsv(rgb.reshape(-1, 3))
    w = s * v
    if w.mean() < GREY * 0.5:
        return None
    # Its commonest hue, not the average of them: an iris of pink and cyan is mostly pink, not the
    # violet between the two. The peak of the hues counted in 36 steps, then the mean of those near it.
    counts = np.bincount((h * 36).astype(int) % 36, weights=w, minlength=36)
    counts = counts + np.roll(counts, 1) + np.roll(counts, -1)
    peak = (np.argmax(counts) + 0.5) / 36
    w = w * (np.abs((h - peak + 0.5) % 1 - 0.5) < 0.09)
    turn = np.arctan2((w * np.sin(2 * np.pi * h)).sum(), (w * np.cos(2 * np.pi * h)).sum()) / (2 * np.pi) % 1
    return float(turn), float((w * s).sum() / w.sum()), float((w * v).sum() / w.sum())


def tinted(rgb, colour):
    """An iris in another colour. Its hues are turned round so its main one is the colour's (a
    second colour in it turns with it and stays a second colour), and it's made as strong and about
    as light as the colour; its white highlights and dark pupil stay white and dark. A grey iris
    takes the colour by how light each pixel is; a grey colour takes the iris's colour out."""
    colour = np.asarray(colour, np.float32)
    th, ts, tv = (float(x) for x in hsv(colour))
    main = main_colour(rgb)
    if main is None:  # a grey iris: the colour darkened where it's dark, toward white where it's light
        lt = max(float(E.light(colour)), 0.05)
        lv = E.light(rgb)[..., None]
        return np.where(lv <= lt, colour * lv / lt, colour + (1 - colour) * (lv - lt) / max(1 - lt, 0.05)).astype(np.float32)
    mh, ms, mv = main
    h, s, v = hsv(rgb)
    if ts < GREY:
        return rgb_of(h, s * ts / ms, v).astype(np.float32)
    part = np.clip(s / ms, 0, 1)  # how much of the iris's colour a pixel has: none in a highlight
    lighter = np.clip(tv / mv, 0.6, 1.6)
    v2 = np.clip(v * (1 + (lighter - 1) * part), 0, 1)
    s2 = np.clip(s * np.clip(ts / ms, 0.4, 1.8), 0, 1)
    return rgb_of((h + th - mh) % 1, s2, v2).astype(np.float32)


def chosen_colours(given, hers):
    """--colour's words as a colour for each eye, None where the iris keeps its own: one word or
    two (the eye on the picture's left first), each a name, #rrggbb, `hers` or `own`."""
    if not given or given.strip().lower() == OWN:
        return [None, None]
    out = []
    for word in [w.strip() for w in given.split(",") if w.strip()][:2]:
        if word.lower() == OWN:
            out.append(None)
        elif word.lower() == HERS:
            out.append(list(hers) if hers else None)
        else:
            out.append(E.colours(word)[0][1])
    if not out:
        sys.exit("--colour: a colour, or two with a comma between (the eye on the picture's left first)")
    out = [out[0], out[-1]]
    # `hers` is each eye's own colour: the first eye's for the first, the second's for the second.
    return [c[min(i, len(c) - 1)] if isinstance(c, list) else c for i, c in enumerate(out)]


# ---- Her eyes, and an iris in each ---------------------------------------------------------------

def oval(mask):
    """An upright ellipse fitted to a shape's outline, its worst points left out five times over (a
    bump of lash shading the split left on an iris doesn't pull it): cx, cy, rx, ry."""
    ys, xs = np.nonzero(mask)
    edge = mask & ~ndimage.binary_erosion(mask)
    ey, ex = np.nonzero(edge)
    start = np.array([xs.mean(), ys.mean(), (xs.max() - xs.min()) / 2 + 0.5, (ys.max() - ys.min()) / 2 + 0.5], float)
    p, pts = start.copy(), np.stack([ex, ey], 1).astype(float)
    for _ in range(5):
        x, y = pts[:, 0], pts[:, 1]
        for _ in range(10):
            u, w = (x - p[0]) / p[2], (y - p[1]) / p[3]
            J = np.stack([-2 * u / p[2], -2 * w / p[3], -2 * u * u / p[2], -2 * w * w / p[3]], 1)
            p -= np.linalg.lstsq(J, u * u + w * w - 1, rcond=None)[0]
            if not (np.isfinite(p).all() and 0.5 < p[2] / start[2] < 1.5 and 0.5 < p[3] / start[3] < 1.5):
                return start  # an outline no ellipse fits (half an iris): its box
        res = np.abs(np.hypot((x - p[0]) / p[2], (y - p[1]) / p[3]) - 1)
        pts = pts[res <= np.quantile(res, 0.85)]
    return p


def her_eyes(name, info):
    """Her eyes in a cut of their own, as `parts eyes` cuts them: the cut's box in her frame and how
    many times bigger it is, her layers there as they show now, and each eye's (mask, oval, main
    colour) from her own iris as she was drawn, the one on the picture's left first."""
    if "irides" not in info["order"]:
        sys.exit(f"{name}: she has no irides layer")
    box, k = E.cut_box(name, info)
    drawn = E.layer_in_cut(name, "irides", box, k)
    sharp = L.load_sharp(name)
    stack = []
    for layer in info["order"]:
        if layer in L.SHUT:
            continue
        where = sharp.get(layer)
        if where and os.path.exists(L.sharp_path(name, layer)):
            stack.append((layer, E.from_source(Image.open(L.sharp_path(name, layer)), where["at"], where["per"], box, k)))
        else:
            stack.append((layer, E.from_source(Image.open(L.part_path(name, layer)), (0, 0), (1, 1), box, k)))
    found = []
    for eye in E.eye_pieces(drawn[..., 3]):
        solid = eye & (drawn[..., 3] > 0.5)
        if solid.sum() < 30:
            continue
        main = main_colour(drawn[..., :3][solid])
        found.append((eye, oval(solid), None if main is None else rgb_of(*main)))
    if not found:
        sys.exit(f"{name}: no iris found in her irides layer")
    return box, k, stack, found


def adjusted(info, given):
    """Her iris's size and place: what is given, else what she has (layers.json), else plain."""
    kept = dict(PLAIN, **{k: v for k, v in info.get(KEY, {}).items() if k in PLAIN})
    out = {k: float(given[k] if given.get(k) is not None else kept[k]) for k in PLAIN}
    if not 0.5 <= out["size"] <= 2:
        sys.exit("--size: from 0.5 to 2 (1 is her own iris's size)")
    if not 0.8 <= out["tall"] <= 1.6:
        sys.exit("--tall: from 0.8 to 1.6 (1 is her own iris's height; 1.12 is a little taller)")
    if abs(out["down"]) > 0.5 or abs(out["right"]) > 0.5:
        sys.exit("--down and --right: shares of her iris's width, from -0.5 to 0.5 (0.05 is a small step)")
    return out


def words(adjust):
    return "".join(f", {k} {adjust[k]:g}" for k in PLAIN if adjust[k] != PLAIN[k])


def placed(ell, adjust):
    """Her iris's oval with the size and place asked for. Taller grows upward, under her lid: its
    lower edge stays where her drawing has it."""
    cx, cy, rx, ry = ell
    return (cx + adjust["right"] * 2 * rx, cy + adjust["down"] * 2 * rx - ry * adjust["size"] * (adjust["tall"] - 1),
            rx * adjust["size"], ry * adjust["size"] * adjust["tall"])


def painted(shape, eyes, sources, colours, adjust, mirror=False):
    """Her irides layer in the cut: each eye's oval with its iris picture stretched into it. RGBA."""
    out = np.zeros(tuple(shape) + (4,), np.float32)
    H, W = shape
    for i, (_, ell, _) in enumerate(eyes):
        src = sources[min(i, len(sources) - 1)]
        if colours[min(i, 1)] is not None:
            src = tinted(src, colours[min(i, 1)])
        if mirror and i == 1:
            src = src[:, ::-1]
        cx, cy, rx, ry = placed(ell, adjust)
        x0, x1 = max(0, int(cx - rx - 3)), min(W, int(cx + rx + 4))
        y0, y1 = max(0, int(cy - ry - 3)), min(H, int(cy + ry + 4))
        if x1 <= x0 or y1 <= y0:
            continue
        # The picture brought to the oval's own size first (a big one shrunk well), then laid in.
        w, h = max(2, round(2 * rx)), max(2, round(2 * ry))
        small = Image.fromarray((np.clip(src, 0, 1) * 255).round().astype(np.uint8), "RGB").resize((w, h), Image.LANCZOS)
        small = np.asarray(small, np.float32) / 255
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        sx, sy = (xx - cx) * (w / 2) / rx + (w - 1) / 2, (yy - cy) * (h / 2) / ry + (h - 1) / 2
        rgb = np.dstack([ndimage.map_coordinates(small[..., c], [sy, sx], order=1, mode="nearest") for c in range(3)])
        alpha = np.clip((1 - np.hypot((xx - cx) / rx, (yy - cy) / ry)) * min(rx, ry) / SOFT + 0.5, 0, 1)
        over = alpha > out[y0:y1, x0:x1, 3]
        out[y0:y1, x0:x1][over] = np.dstack([rgb, alpha])[over]
    return out


def shown(stack, irides):
    """The cut as it shows with this irides layer: RGB."""
    return E.flat(E.clipped([(n, irides if n == "irides" else im) for n, im in stack]))


def sources_for(info, style, file):
    """The iris picture for each eye, and how to keep and say it: a number or two from the kit, or
    a picture or two of your own; with neither, the one she has, or the kit's first."""
    if style and file:
        sys.exit("give --style or --file, not both")
    had = info.get(KEY, {})
    if not style and not file:
        style, file = had.get("style"), had.get("file")
        if style and had.get("names"):  # by name: the kit's irises may have been numbered again since
            numbers = {said: n for n, (said, _) in styles().items()}
            gone = [said for said in had["names"] if said not in numbers]
            if gone:
                sys.exit(f"her iris ({', '.join(gone)}) is not in the kit any more: give --style (iris-sheet shows them)")
            style = [numbers[said] for said in had["names"]]
        if not style and not file:
            style = [min(styles(), default=1)]
    if file:
        files = file if isinstance(file, list) else [f.strip() for f in file.split(",") if f.strip()][:2]
        return [from_file(f) for f in files], {"file": files}, "from " + " and ".join(os.path.basename(f) for f in files)
    try:
        numbers = list(style) if isinstance(style, list) else [int(s) for s in str(style).split(",")][:2]
    except ValueError:
        sys.exit("--style: an iris's number, or two with a comma between (the eye on the picture's left first)")
    sources, names = [from_kit(n) for n in numbers], styles()
    return sources, {"style": numbers, "names": [names[n][0] for n in numbers]}, "the kit's iris " + " and ".join(f"{n} ({names[n][0]})" for n in numbers)


# ---- The commands --------------------------------------------------------------------------------

def do_sheet(name=None, colour=None, given=None):
    import parts as P
    if name is None:  # each iris by itself, for the GUI and the README
        cells = []
        for n, (said, _) in styles().items():
            pad = np.full((240, 240, 3), (0.93, 0.93, 0.95), np.float32)
            part = painted((240, 240), [(None, (120, 120, 104, 104), None)], [from_kit(n)], [None, None], PLAIN)
            cells.append((f"{n}  {said}", part[..., :3] * part[..., 3:4] + pad * (1 - part[..., 3:4])))
        if not cells:
            sys.exit(f"no irises in {IRISES}")
        return P.sheet(cells, os.path.join(IRISES, "sheet.png"), wide=200, cols=6)
    info = L.load(name)
    box, k, stack, eyes = her_eyes(name, info)
    adjust = adjusted(info, given or {})
    had = info.get(KEY, {})
    colour = colour if colour is not None else had.get("colour")
    colours = chosen_colours(colour, [e[2] for e in eyes])
    shape = stack[0][1].shape[:2]
    cells = [("hers now", E.flat(E.clipped(stack)))]
    for n, (said, _) in styles().items():
        cells.append((f"{n}  {said}", shown(stack, painted(shape, eyes, [from_kit(n)], colours, adjust))))
    P.sheet(cells, P.out_path(name, "irises"), wide=460, cols=3)
    said = (f", in {colour}" if colour and colour.lower() != OWN else "") + words(adjust)
    if said:
        print("drawn" + said[1:])


def do_iris(name, style=None, file=None, colour=None, given=None, mirror=False):
    import parts as P
    info = L.load(name)
    box, k, stack, eyes = her_eyes(name, info)
    adjust = adjusted(info, given or {})
    had = info.get(KEY, {})
    sources, kept, what = sources_for(info, style, file)
    colour = colour if colour is not None else had.get("colour")
    if colour and colour.strip().lower() == OWN:
        colour = None
    mirror = bool(mirror)
    colours = chosen_colours(colour, [e[2] for e in eyes])
    x0, y0, w, h = box
    big = painted((h * k, w * k), eyes, sources, colours, adjust, mirror)
    E.keep_hers(name, info)
    # Her frame's layer, and a sharp copy of just the irises at the cut's own size.
    frame_w, frame_h = info["frame"]
    part = np.zeros((frame_h, frame_w, 4), np.float32)
    part[y0:y0 + h, x0:x0 + w] = E.straight(E.pre(E.to_image(big)).resize((w, h), Image.LANCZOS))
    L.write_part(name, "irides", part)
    ys, xs = np.nonzero(big[..., 3] > 0)
    cx0, cy0 = max(0, int(xs.min()) - 4), max(0, int(ys.min()) - 4)
    E.to_image(big[cy0:ys.max() + 5, cx0:xs.max() + 5]).save(L.sharp_path(name, "irides"), optimize=True)
    sharp = L.load_sharp(name)
    sharp["irides"] = {"at": [x0 + cx0 / k, y0 + cy0 / k], "per": [1 / k, 1 / k]}
    L.save_sharp(name, sharp)
    info[KEY] = dict(kept, colour=colour, mirror=bool(mirror), **adjust)
    said = what + (f", in {colour}" if colour else "") + (", the second eye's mirrored" if mirror else "") + words(adjust)
    L.note(info, f"irides: {said}, each in a clean oval fitted to her own iris, with a sharp copy at {k:g} times "
                 f"her frame's size; hers kept in {E.KEPT}/")
    L.save(name, info)
    P.sheet([("before", E.flat(E.clipped(stack))), ("now", shown(stack, big))], P.out_path(name, "iris"), wide=640, cols=2)
    sizes = ", ".join(f"{2 * placed(e[1], adjust)[2] / k:.0f}x{2 * placed(e[1], adjust)[3] / k:.0f}" for e in eyes)
    print(f"{name}: irides: {said}; {len(eyes)} iris{'es' if len(eyes) != 1 else ''}, {sizes} in her frame. Run `build` again")


def do_back(name):
    """Her own irises back (her lashes and eye whites stay as they are)."""
    info = L.load(name)
    keep = os.path.join(L.folder(name), E.KEPT)
    if KEY not in info or not os.path.exists(os.path.join(keep, "irides.png")):
        sys.exit(f"{name}: her irises are her own already")
    shutil.copy(os.path.join(keep, "irides.png"), L.part_path(name, "irides"))
    with open(os.path.join(keep, "sharp.json"), encoding="utf-8") as f:
        record = json.load(f)
    sharp = L.load_sharp(name)
    if "irides" in record:
        shutil.copy(os.path.join(keep, "irides@head.png"), L.sharp_path(name, "irides"))
        sharp["irides"] = record["irides"]
    else:
        sharp.pop("irides", None)
        if os.path.exists(L.sharp_path(name, "irides")):
            os.remove(L.sharp_path(name, "irides"))
    L.save_sharp(name, sharp)
    del info[KEY]
    L.note(info, "irides: her own back")
    L.save(name, info)
    print(f"{name}: her own irises are back. Run `build` again")
