"""Her eyes drawn again, sharper, to choose from: `parts eyes`, run by parts.py. See its usage.

An upscaled drawing keeps an iris's shape but loses its depth (the gradient, the pupil, the rim,
the glow under it, the shine). Two ways back to it, each a candidate on one sheet beside her eyes
as they are:

- redrawn: her eyes as the model shows them, cut out together (so the two stay alike) and made
  several times bigger, are drawn over by Qwen Image at a strength from 0 (as they are) to 1 (a new
  drawing), on ComfyUI, with a seed (her drawing's own unless another is given);
- drawn: her iris drawn by code in her own iris colours, with a gradient, pupil, rim, glow and
  shine. No graphics card.

Either way her layers keep their shapes: each eye layer (eyewhite, irides, eyelash) takes the new
picture's colour where it shows, and her lashes their new line, from how dark the new picture is
over what is under them. The result is a sharp copy of each (parts/<layer>@head.png, as the head
pass makes) at KEEP of the redraw's size, and her frame's layer shrunk from it, so the build puts
it in her texture sharp. Her eyes as they were are kept (layers/<pose>/eyes-drawn/) the first time.
"""
import base64, io, json, os, re, shutil, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
import layers as L  # noqa: E402

EYES = ("eyewhite", "irides", "eyelash")  # the layers a candidate changes, bottom to top as they usually are
WIDE = 1344        # the redraw is about this wide: what Qwen Image draws well, and several times her eyes
ROOM = (0.12, 0.6, 0.25)  # the cut round her eyes: this share of their width each side, of their height above and below
KEEP = 2           # her texture keeps the redraw shrunk this many times: still about 3 times the head pass's sharpness
STRENGTHS = (0.35, 0.5, 0.65)  # --try's redraws when none are given: from a light touch to a new drawing of her eyes
FRESH = (0.6, 0.75, 0.9)  # ...and with --iris-only, where her iris is cut out of the redraw and fitted to hers
# Colour names Pillow doesn't know, that eyes are often given (Pillow knows the CSS ones: gold, teal, violet...).
GEMS = {"gold": "#e0a020", "amber": "#ffb000", "emerald": "#2fbf71", "sapphire": "#1f5fd0", "ruby": "#d0104c", "amethyst": "#9a5cd0",
        "golden": "#f2b632", "hazel": "#9a7b3c", "scarlet": "#ff2a10", "jade": "#30a878", "rose": "#f06c9b"}
FALLBACK_SEED = 1  # a drawing with no record of its seed (base.json) is redrawn with this one
KEPT = "eyes-drawn"  # her eyes as they were, kept beside her layers.json
PROMPT = ("Extreme close-up of the eyes of an anime girl, clean cel-shaded anime illustration, crisp fine line art. "
          "{eyes}Beautiful detailed glossy anime eyes: irises with depth, darker under the upper lid and lighter "
          "toward the bottom, a dark pupil, a thin dark rim, a soft glow in the lower iris and bright white "
          "highlights. The same eyes, the same shape, lashes and skin as the picture.")


# ---- Her eyes in a cut of their own --------------------------------------------------------------

def own(name, layer):
    """Where her own layer is, for a redraw to start from: her eyes as she was drawn (kept the first
    time a redraw was taken) rather than one taken since. (frame layer, sharp copy or None, its
    {"at", "per"} or None)."""
    keep = os.path.join(L.folder(name), KEPT)
    if layer in EYES and os.path.exists(os.path.join(keep, layer + ".png")):
        with open(os.path.join(keep, "sharp.json"), encoding="utf-8") as f:
            where = json.load(f).get(layer)
        return os.path.join(keep, layer + ".png"), os.path.join(keep, layer + "@head.png") if where else None, where
    where = L.load_sharp(name).get(layer)
    copy = L.sharp_path(name, layer) if where and os.path.exists(L.sharp_path(name, layer)) else None
    return L.part_path(name, layer), copy, where if copy else None


def cut_box(name, info):
    """The cut round both her eyes, in her frame's pixels, and how many times bigger the redraw is.
    Its sides are whole multiples of 16, so the redraw (k times as big) is too."""
    found = []
    for layer in EYES:
        if layer in info["order"]:
            a = np.asarray(Image.open(own(name, layer)[0]).convert("RGBA"))[..., 3] / 255
            ys, xs = np.nonzero(a > 0.05)
            if len(xs):
                found.append((xs.min(), ys.min(), xs.max(), ys.max()))
    if not found:
        sys.exit(f"{name}: no eye layers ({', '.join(EYES)})")
    x0, y0 = min(b[0] for b in found), min(b[1] for b in found)
    x1, y1 = max(b[2] for b in found), max(b[3] for b in found)
    w, h = x1 - x0, y1 - y0
    x0, x1 = x0 - ROOM[0] * w, x1 + ROOM[0] * w
    y0, y1 = y0 - ROOM[1] * h, y1 + ROOM[2] * h
    W, H = info["frame"]
    w, h = int(np.ceil((x1 - x0) / 16)) * 16, int(np.ceil((y1 - y0) / 16)) * 16
    x0, y0 = int(max(0, min(W - w, round((x0 + x1 - w) / 2)))), int(max(0, min(H - h, round(y0))))
    k = max(2, round(WIDE / w))
    return (x0, y0, w, h), k


def pre(im):
    return im.convert("RGBa")


def straight(im):
    return np.asarray(im.convert("RGBA"), np.float32) / 255


def from_source(source, at, per, box, k):
    """A picture whose corner is `at` in her frame and whose pixel is `per` of hers, resampled into
    the cut (box, k times her frame's pixels): RGBA from 0 to 1."""
    x0, y0, w, h = box
    p = 1 / k
    src = pre(source)
    data = (p / per[0], 0, (x0 - at[0]) / per[0], 0, p / per[1], (y0 - at[1]) / per[1])
    return straight(src.transform((w * k, h * k), Image.AFFINE, data, resample=Image.BICUBIC))


def layer_in_cut(name, layer, box, k):
    """Her own layer in the cut, from its sharp copy where it has one (the head pass's size), else
    from her frame's layer."""
    frame, copy, where = own(name, layer)
    if copy:
        return from_source(Image.open(copy), where["at"], where["per"], box, k)
    return from_source(Image.open(frame), (0, 0), (1, 1), box, k)


def stack_in_cut(name, info, box, k):
    """Her layers as they show at rest, in the cut: [(layer, RGBA)], her iris clipped by her eye
    white as the rig clips it."""
    stack = [(layer, layer_in_cut(name, layer, box, k)) for layer in info["order"] if layer not in L.SHUT]
    return clipped(stack)


def clipped(stack):
    white = dict(stack).get("eyewhite")
    if white is None:
        return stack
    return [(n, np.dstack([im[..., :3], im[..., 3] * white[..., 3]]) if n == "irides" else im) for n, im in stack]


def flat(stack, upto=None):
    """The layers over white (below `upto`, if given): RGB."""
    rgb = None
    for n, im in stack:
        if n == upto:
            break
        if rgb is None:
            rgb = np.ones(im.shape[:2] + (3,), np.float32)
        a = im[..., 3:4]
        rgb = im[..., :3] * a + rgb * (1 - a)
    return rgb


def covered(stack, layer):
    """How much of each pixel the layers above `layer` cover, 0 to 1."""
    names = [n for n, _ in stack]
    clear = np.ones(stack[0][1].shape[:2], np.float32)
    for n, im in stack[names.index(layer) + 1:]:
        clear *= 1 - im[..., 3]
    return 1 - clear


def light(rgb):
    return rgb @ np.array([0.3, 0.59, 0.11], np.float32)


# ---- From a new picture of her eyes to her layers ------------------------------------------------

def take_colour(stack, layer, picture, alpha=None):
    """Her layer's colours (and, given, its alpha) where it shows, from a new picture of the cut: what
    the layer must be for it, over what is under it, to look like the picture."""
    im = dict(stack)[layer]
    a = im[..., 3] if alpha is None else alpha  # an iris's is clipped by her eye white already, in the stack
    under = flat(stack, layer)
    cover = covered(stack, layer)
    new = np.clip((picture - (1 - a[..., None]) * under) / np.maximum(a[..., None], 1e-3), 0, 1)
    w = (np.clip((a - 0.3) / 0.3, 0, 1) * np.clip((0.2 - cover) / 0.15, 0, 1))[..., None]
    rgb = im[..., :3] * (1 - w) + new * w
    return rgb


def lash_alpha(stack, picture, k):
    """Her lashes' line from the new picture: how much darker it is than what is under her lashes,
    near where her lashes were, and only where nothing covers them. Light parts of her own lashes
    (a coloured lower lash, a shine) keep their own."""
    lash = dict(stack)["eyelash"]
    under = light(flat(stack, "eyelash"))
    now = light(picture)
    old_a = lash[..., 3]
    near = ndimage.binary_dilation(old_a > 0.1, iterations=max(2, round(1.5 * k)))
    ink = np.quantile(now[old_a > 0.6], 0.05) if (old_a > 0.6).any() else 0.15
    new_a = np.clip((under - now) / np.maximum(under - ink, 0.1), 0, 1) * near
    new_a[new_a < 0.08] = 0
    # Only strokes that join her lash line: a crease or a loose stroke the redraw put above it
    # would stay behind as a floating line when her lid comes down.
    pieces, n = ndimage.label(new_a > 0.08, structure=np.ones((3, 3)))
    if n:
        joined = np.unique(pieces[(old_a > 0.5) & (pieces > 0)])
        new_a[~np.isin(pieces, joined)] = 0
    own_light = (old_a > 0.5) & (light(lash[..., :3]) > under - 0.25)
    a = np.where(own_light, old_a, new_a)
    cover = covered(stack, "eyelash")
    return np.where(cover < 0.15, a, old_a)


def new_layers(stack, picture, k, iris_only=False):
    """Her eye layers for a new picture of the cut: {layer: RGBA in the cut}. iris_only: her iris
    alone, her lashes and eye whites as they are."""
    names = dict(stack)
    out = {}
    if iris_only:
        return {"irides": np.dstack([fitted_iris(stack, picture), UNCLIPPED["irides"]])} if "irides" in names else {}
    if "eyelash" in names:
        a = lash_alpha(stack, picture, k)
        out["eyelash"] = np.dstack([take_colour(stack, "eyelash", picture, a), a])
    for layer in ("eyewhite", "irides"):
        if layer in names:
            own = layer_alpha(stack, layer)
            out[layer] = np.dstack([take_colour(stack, layer, picture), own])
    return out


def chroma(rgb):
    """Colour without lightness: red against green, and yellow against blue."""
    return np.stack([rgb[..., 0] - rgb[..., 1], (rgb[..., 0] + rgb[..., 1]) / 2 - rgb[..., 2]], -1)


def widest_row(mask):
    """An iris's middle: the rows where it is widest (the lids cut its top and bottom, not its middle)."""
    widths = mask.sum(axis=1).astype(np.float32)
    rows = np.nonzero(widths >= 0.95 * widths.max())[0]
    return float(rows.mean())


def iris_in(picture, near, ref, skin_light):
    """The iris the redraw drew near one of her eyes, as a mask: what has her iris's colour (and is
    darker than skin), closed up, with its pupil, highlights and dark rim filled in."""
    c = chroma(picture)
    lit = light(picture)
    like = (np.linalg.norm(c - ref, axis=-1) < 0.5 * np.linalg.norm(ref) + 0.06) & (lit < skin_light - 0.05) & near
    like = ndimage.binary_closing(like, np.ones((3, 3)), iterations=2)
    pieces, n = ndimage.label(like)
    if not n:
        return None
    big = pieces == 1 + int(np.argmax(ndimage.sum(np.ones(like.shape), pieces, range(1, n + 1))))
    ys, xs = np.nonzero(big)
    reach = max(2, round(0.08 * (xs.max() - xs.min())))
    big |= (lit < 0.3) & ndimage.binary_dilation(big, iterations=reach) & near  # its dark rim and top
    return ndimage.binary_fill_holes(big)


def fitted_iris(stack, picture):
    """Her iris from a redraw that drew her eyes anew (a high strength), cut out as the split cuts a
    layer: each eye's iris found in the redraw by its colour, then warped onto her own iris, row by
    row (middle on middle, bottom on bottom, each row's edges on hers), and painted into her iris
    layer. Nothing of her old iris is left inside it."""
    iris = dict(stack)["irides"]
    rgb = iris[..., :3].copy()
    full = UNCLIPPED["irides"]
    shown = iris[..., 3] > 0.5
    face = flat(stack, "eyewhite") if "eyewhite" in dict(stack) else flat(stack, "irides")
    for eye in eye_pieces(full):
        ys, xs = np.nonzero(eye & (full > 0.5))
        if len(xs) < 20:
            continue
        ox0, ox1, oy0, oy1 = xs.min(), xs.max(), ys.min(), ys.max()
        w, h = ox1 - ox0, oy1 - oy0
        near = np.zeros(full.shape, bool)
        near[max(0, int(oy0 - 0.5 * h)):int(oy1 + 0.5 * h), max(0, int(ox0 - 0.4 * w)):int(ox1 + 0.4 * w)] = True
        own = rgb[eye & shown] if (eye & shown).sum() > 20 else rgb[eye]
        ref = np.median(chroma(own), axis=0)
        ring = ndimage.binary_dilation(near, iterations=4) & ~near
        skin_light = float(np.median(light(face[ring]))) if ring.any() else 0.85
        found = iris_in(picture, near, ref, skin_light)
        if found is None or found.sum() < 0.2 * eye.sum():
            print("   an eye's iris wasn't found in the redraw: hers is kept")
            continue
        mine = eye & (full > 0.5)
        fys, fxs = np.nonzero(found)
        fy0, fy1 = fys.min(), fys.max()
        ocy, fcy = widest_row(mine), widest_row(found)
        # Rows: her middle on its middle, her bottom on its bottom, so its lower half is stretched
        # to hers; above its lid, her rows take its top row (the shadow under a lid).
        step = (fy1 - fcy) / (oy1 - ocy) if oy1 - ocy > 2 and fy1 - fcy > 2 else (fxs.max() - fxs.min()) / max(w, 1)
        ys2, xs2 = np.nonzero(mine)
        ty = np.clip(fcy + (ys2 - ocy) * step, fy0, fy1)
        has = found.any(axis=1)
        nearest = ndimage.distance_transform_edt(~has, return_indices=True)[1][0]  # each row's nearest row with iris
        row = nearest[np.round(ty).astype(int)]
        ty = np.where(has[np.round(ty).astype(int)], ty, row)
        # Across: each of her rows from its left edge to its right takes that row of the redraw's
        # iris from its left edge to its right, so the iris is stretched and skewed to her shape.
        left = lambda m: m.argmax(axis=1)  # noqa: E731
        right = lambda m: m.shape[1] - 1 - m[:, ::-1].argmax(axis=1)  # noqa: E731
        ml, mr, fl, fr = left(mine), right(mine), left(found), right(found)
        t = (xs2 - ml[ys2] + 0.5) / (mr[ys2] - ml[ys2] + 1)
        tx = fl[row] - 0.5 + t * (fr[row] - fl[row] + 1)
        for i in range(3):
            rgb[ys2, xs2, i] = ndimage.map_coordinates(picture[..., i], [ty, tx], order=1)
        # Her iris's soft edge takes its nearest new pixel.
        edge = eye & ~mine
        if edge.any():
            iy, ix = ndimage.distance_transform_edt(~mine, return_indices=True)[1]
            rgb[edge] = rgb[iy[edge], ix[edge]]
    return rgb


def layer_alpha(stack, layer):
    return dict(stack)[layer][..., 3] if layer != "irides" else UNCLIPPED["irides"]


UNCLIPPED = {}  # the iris's own alpha in the cut, before the clip by her eye white


# ---- An iris drawn by code -----------------------------------------------------------------------

def drawn_iris(stack, k):
    """Her iris drawn again in its own colours, each eye: a gradient from dark under the lid to light
    below, a dark rim, a pupil, a glow in the lower half and two highlights. RGB in the cut."""
    iris = UNCLIPPED["irides"]
    rgb = dict(stack)["irides"][..., :3].copy()
    shown = dict(stack)["irides"][..., 3] > 0.5
    labels, n = ndimage.label(iris > 0.5, structure=np.ones((3, 3)))
    if n < 1:
        return rgb
    sizes = ndimage.sum(np.ones(iris.shape), labels, range(1, n + 1))
    H, W = iris.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    for lab in 1 + np.argsort(sizes)[-2:]:
        eye = labels == lab
        ys, xs = np.nonzero(eye)
        cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
        rx, ry = (xs.max() - xs.min()) / 2 + 0.5, (ys.max() - ys.min()) / 2 + 0.5
        own = rgb[eye & shown] if (eye & shown).sum() > 20 else rgb[eye]
        lit = light(own)
        q = np.quantile(lit, [0.12, 0.4, 0.6, 0.85])
        dark, bright = own[lit <= q[0]].mean(axis=0), own[lit >= q[3]].mean(axis=0)
        middle = (lit >= q[1]) & (lit <= q[2])
        mid = own[middle].mean(axis=0) if middle.any() else own.mean(axis=0)
        u, v = (xx - cx) / rx, (yy - cy) / ry
        r = np.sqrt(u * u + v * v)
        t = np.clip((v + 1) / 2, 0, 1)[..., None]  # 0 at the top, 1 at the bottom
        col = np.where(t < 0.5, dark + (mid - dark) * (t / 0.5), mid + (bright - mid) * ((t - 0.5) / 0.5))
        deep = dark * 0.45
        soft = lambda m, s: ndimage.gaussian_filter(m.astype(np.float32), s * k)  # noqa: E731
        lid = soft(v < -0.35, 0.6)[..., None] * 0.55          # under the upper lid, darker
        col = col * (1 - lid) + deep * lid
        glow = soft(((u / 0.62) ** 2 + ((v - 0.5) / 0.32) ** 2) < 1, 0.8)[..., None] * 0.55
        col = col * (1 - glow) + np.clip(bright * 1.25 + 0.08, 0, 1) * glow
        pupil = soft(((u / 0.36) ** 2 + ((v + 0.05) / 0.46) ** 2) < 1, 0.35)[..., None] * 0.9
        col = col * (1 - pupil) + deep * pupil
        rim = soft(r > 0.86, 0.3)[..., None] * 0.75
        col = col * (1 - rim) + deep * rim
        for hx, hy, hrx, hry, s in ((-0.34, -0.38, 0.24, 0.2, 1.0), (0.36, 0.34, 0.11, 0.09, 0.85)):
            spot = soft(((u - hx) / hrx) ** 2 + ((v - hy) / hry) ** 2 < 1, 0.15)[..., None] * s
            col = col * (1 - spot) + spot
        rgb[eye] = col[eye]
    return rgb


# ---- Another eye colour ---------------------------------------------------------------------------

def colours(given):
    """--colour's words: one colour, or two (the eye on the picture's left first), each a name
    (Pillow's CSS names, or GEMS) or #rrggbb. -> [(words, RGB from 0 to 1)]."""
    from PIL import ImageColor
    out = []
    for word in [w.strip() for w in given.split(",") if w.strip()][:2]:
        try:
            rgb = ImageColor.getrgb(GEMS.get(word.lower(), word))
        except ValueError:
            sys.exit(f"{word}: not a colour I know: a name (gold, teal, violet, crimson, {', '.join(sorted(GEMS))}...) or #rrggbb")
        out.append(("" if word.startswith("#") else word, np.array(rgb[:3], np.float32) / 255))
    if not out:
        sys.exit("--colour: give a colour, or two with a comma between (the eye on the picture's left first)")
    return out


def colour_words(chosen):
    """The prompt's sentence for the chosen colour(s), or nothing when only #rrggbb was given."""
    words = [w for w, _ in chosen]
    if not all(words):
        return ""
    if len(words) == 1 or words[0].lower() == words[1].lower():
        return f"Her eyes: {words[0]} eyes. "
    return f"Her eyes: heterochromia: one {words[0]} eye and one {words[1]} eye. "


def eye_pieces(alpha):
    """Her two eyes' masks in an alpha, the one on the picture's left first (one, if only one)."""
    labels, n = ndimage.label(alpha > 0.3, structure=np.ones((3, 3)))
    if not n:
        return []
    sizes = ndimage.sum(np.ones(alpha.shape), labels, range(1, n + 1))
    big = sorted(1 + np.argsort(sizes)[-2:], key=lambda k: ndimage.center_of_mass(labels == k)[1])
    near = ndimage.distance_transform_edt(labels == 0, return_indices=True)[1]
    nearest = labels[near[0], near[1]]  # each pixel to its nearest piece, so faint edges go with their eye
    return [(nearest == b) & (alpha > 0) for b in big]


def recoloured(stack, chosen):
    """Her iris in the chosen colour(s), each pixel as light or dark as it was: [(layer, RGBA)]."""
    names = dict(stack)
    if "irides" not in names:
        return stack
    iris = names["irides"].copy()
    for i, eye in enumerate(eye_pieces(UNCLIPPED["irides"])):
        t = chosen[min(i, len(chosen) - 1)][1]
        lt = max(float(light(t)), 0.05)
        lv = light(iris[..., :3])[eye][:, None]
        # A pixel darker than the colour is the colour darkened; lighter, the colour toward white.
        iris[eye, :3] = np.where(lv <= lt, t * lv / lt, t + (1 - t) * (lv - lt) / max(1 - lt, 0.05))
    return [(n, iris if n == "irides" else im) for n, im in stack]


# ---- ComfyUI ------------------------------------------------------------------------------------

def her_seed(name):
    """Her drawing's own seed (base.json, written by pick), or FALLBACK_SEED."""
    char, _ = L.split(name)
    record = os.path.join(L.CHARS, char, "full", "base.json")
    try:
        with open(record, encoding="utf-8") as f:
            return int(json.load(f)["seed"]), "her drawing's seed"
    except (OSError, ValueError, KeyError):
        return FALLBACK_SEED, f"her drawing has no record of its seed (base.json), so {FALLBACK_SEED}"


def her_eye_words(name):
    """What the looks file says of her eyes, as a sentence for the prompt ("Her eyes: large violet
    eyes. "), or nothing: each part of her look, between commas outside brackets, that names an eye."""
    char, _ = L.split(name)
    try:
        with open(kit.looks_file(), encoding="utf-8") as f:
            look = json.load(f)["characters"][char]["looks"]["default"]
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    parts, depth, word = [], 0, ""
    for ch in look:
        depth += (ch == "(") - (ch == ")")
        if ch in ",." and depth == 0:
            parts.append(word.strip())
            word = ""
        else:
            word += ch
    parts.append(word.strip())
    said = [w for w in parts if re.search(r"\beyes?\b", w, re.I) and not re.search(r"\b(glasses|eyewear|patch)\b", w, re.I)]
    return f"Her eyes: {', '.join(said)}. " if said else ""


def redraw_graph(picture, prompt, seed, strength):
    """draw.py's graph, starting from the picture instead of noise: img2img."""
    import draw
    wf, _ = draw.workflow(prompt, seed, (picture.width, picture.height))
    del wf["5"]
    wf["11"] = {"class_type": "LoadImage", "inputs": {"image": "eyes.png"}}
    wf["12"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["11", 0], "vae": ["3", 0]}}
    wf["6"]["inputs"].update({"latent_image": ["12", 0], "denoise": float(strength)})
    buf = io.BytesIO()
    picture.save(buf, "PNG")
    return wf, {"images": [{"name": "eyes.png", "image": base64.b64encode(buf.getvalue()).decode()}]}


def redraws(jobs):
    """Each (label, graph, extra) on this PC's ComfyUI: {label: RGB from 0 to 1}."""
    import comfy, draw, time
    if not comfy.answers():
        print(f"ComfyUI isn't answering on {comfy.url()}: no redraws, only the drawn iris (`live2d.py comfy start`)")
        return {}
    backend = draw.Local()
    pending = {backend.submit(wf, extra): label for label, wf, extra in jobs}
    got, t0 = {}, time.time()
    while pending and time.time() - t0 < 300 * len(jobs):
        time.sleep(2)
        for job, label in list(pending.items()):
            res = backend.result(job)
            if res is None:
                continue
            del pending[job]
            png, note = res
            if png is None:
                print(f"{label}: failed: {note}")
                continue
            got[label] = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), np.float32) / 255
            print(f"{label}: redrawn, {note}", flush=True)
    for label in pending.values():
        print(f"{label}: no answer, gave up")
    return got


# ---- Candidates, the sheet, and taking one -------------------------------------------------------

def tries_folder(name):
    return kit.out("parts", f"{L.slug(name)}-eyes-try")


def to_image(rgba):
    return Image.fromarray(np.clip(rgba * 255, 0, 255).round().astype(np.uint8), "RGBA")


def save_candidate(folder, layers, box, k):
    os.makedirs(folder, exist_ok=True)
    for layer, rgba in layers.items():
        to_image(rgba).save(os.path.join(folder, layer + ".png"), optimize=True)
    with open(os.path.join(folder, "cut.json"), "w", encoding="utf-8") as f:
        json.dump({"box": list(box), "k": k}, f)


def picture_of(stack, layers):
    """The cut as it shows, with these eye layers in it: RGB."""
    swapped = [(n, layers[n] if n in layers else im) for n, im in stack]
    return flat(clipped(swapped))


def do_try(name, seeds=None, strengths=None, colour=None, iris_only=False):
    import parts as P
    info = L.load(name)
    box, k = cut_box(name, info)
    stack = stack_in_cut(name, info, box, k)
    UNCLIPPED["irides"] = layer_in_cut(name, "irides", box, k)[..., 3] if "irides" in info["order"] else None
    hers = flat(stack)
    chosen = colours(colour) if colour else None
    if chosen:  # her iris tinted first: the redraws start from it, and her hidden iris keeps it
        stack = clipped([(n, np.dstack([im[..., :3], UNCLIPPED["irides"]]) if n == "irides" else im)
                         for n, im in recoloured(stack, chosen)])
    now = flat(stack)
    folder = tries_folder(name)
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    source = Image.fromarray((np.clip(now, 0, 1) * 255).round().astype(np.uint8), "RGB")
    source.save(os.path.join(folder, "source.png"))
    seed_note = None
    if not seeds:
        seed, seed_note = her_seed(name)
        seeds = [seed]
    prompt = PROMPT.format(eyes=colour_words(chosen) if chosen else her_eye_words(name))
    if iris_only:
        prompt = prompt.replace("The same eyes, the same shape, lashes and skin as the picture.",
                                "The same eye shape, lashes and skin as the picture, with new irises.")
    jobs, labels = [], []
    for seed in seeds:
        for s in strengths or (FRESH if iris_only else STRENGTHS):
            label = f"seed {seed} at {s:g}"
            wf, extra = redraw_graph(source, prompt, seed, s)
            jobs.append((label, wf, extra))
            labels.append(label)
    print(f"{name}: her eyes in a cut of {box[2]}x{box[3]} of her frame, redrawn at {box[2] * k}x{box[3] * k}"
          + (f"; seed: {seed_note}" if seed_note else ""))
    print("prompt:", prompt)
    got = redraws(jobs)
    cells, n = [("now", hers)], 0
    if chosen:
        n += 1
        layers = {"irides": np.dstack([dict(stack)["irides"][..., :3], UNCLIPPED["irides"]])}
        save_candidate(os.path.join(folder, str(n)), layers, box, k)
        cells.append((f"{n}  tinted {colour}", now))
    for label in labels:
        if label not in got:
            continue
        n += 1
        layers = new_layers(stack, got[label], k, iris_only)
        save_candidate(os.path.join(folder, str(n)), layers, box, k)
        Image.fromarray((got[label] * 255).round().astype(np.uint8), "RGB").save(os.path.join(folder, str(n), "redraw.png"))
        cells.append((f"{n}  {label}" + (f", {colour}" if chosen else "") + (", iris only" if iris_only else ""),
                       picture_of(stack, layers)))
    if "irides" in info["order"]:
        n += 1
        layers = {"irides": np.dstack([drawn_iris(stack, k), UNCLIPPED["irides"]])}
        save_candidate(os.path.join(folder, str(n)), layers, box, k)
        cells.append((f"{n}  drawn iris", picture_of(stack, layers)))
    with open(os.path.join(folder, "labels.json"), "w", encoding="utf-8") as f:
        json.dump({c[0].split()[0]: c[0] for c in cells[1:]}, f)
    P.sheet(cells, P.out_path(name, "eyes"), wide=640, cols=2)
    print(f"take one with `parts eyes {L.split(name)[0]} <number>`")


def keep_hers(name, info):
    """Her eye layers and their sharp copies as they are, kept the first time (layers/<pose>/eyes-drawn/)."""
    keep = os.path.join(L.folder(name), KEPT)
    if os.path.exists(keep):
        return keep
    os.makedirs(keep)
    sharp = L.load_sharp(name)
    record = {}
    for layer in EYES:
        if layer in info["order"]:
            shutil.copy(L.part_path(name, layer), os.path.join(keep, layer + ".png"))
            if layer in sharp and os.path.exists(L.sharp_path(name, layer)):
                shutil.copy(L.sharp_path(name, layer), os.path.join(keep, layer + "@head.png"))
                record[layer] = sharp[layer]
    with open(os.path.join(keep, "sharp.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, indent=2)
        f.write("\n")
    return keep


def do_take(name, number):
    info = L.load(name)
    folder = os.path.join(tries_folder(name), str(number))
    if not os.path.isdir(folder):
        sys.exit(f"{name}: no eyes numbered {number}: make them with `parts eyes {L.split(name)[0]} --try`")
    with open(os.path.join(tries_folder(name), "labels.json"), encoding="utf-8") as f:
        label = json.load(f).get(str(number), str(number))
    with open(os.path.join(folder, "cut.json"), encoding="utf-8") as f:
        cut = json.load(f)
    (x0, y0, w, h), k = cut["box"], cut["k"]
    keep_hers(name, info)
    sharp = L.load_sharp(name)
    took = []
    for layer in EYES:
        path = os.path.join(folder, layer + ".png")
        if not os.path.exists(path) or layer not in info["order"]:
            continue
        big = Image.open(path).convert("RGBA")
        copy = pre(big).resize((w * k // KEEP, h * k // KEEP), Image.LANCZOS)
        copy.convert("RGBA").save(L.sharp_path(name, layer), optimize=True)
        sharp[layer] = {"at": [float(x0), float(y0)], "per": [KEEP / k, KEEP / k]}
        small = straight(pre(big).resize((w, h), Image.LANCZOS))
        part = straight(Image.open(own(name, layer)[0]))  # her own, outside the cut
        part[y0:y0 + h, x0:x0 + w] = small
        L.write_part(name, layer, part)
        took.append(layer)
    L.save_sharp(name, sharp)
    L.note(info, f"eyes: {label} taken ({', '.join(took)}), sharp copies at {k / KEEP:g} times her frame's size; "
                 f"hers kept in {KEPT}/")
    L.save(name, info)
    print(f"{name}: eyes {label}: {', '.join(took)}, with sharp copies. Run `build` again")


def do_back(name):
    info = L.load(name)
    keep = os.path.join(L.folder(name), KEPT)
    if not os.path.isdir(keep):
        sys.exit(f"{name}: her eyes are her own already")
    sharp = L.load_sharp(name)
    with open(os.path.join(keep, "sharp.json"), encoding="utf-8") as f:
        record = json.load(f)
    for layer in EYES:
        path = os.path.join(keep, layer + ".png")
        if not os.path.exists(path):
            continue
        shutil.copy(path, L.part_path(name, layer))
        if layer in record:
            shutil.copy(os.path.join(keep, layer + "@head.png"), L.sharp_path(name, layer))
            sharp[layer] = record[layer]
        else:
            sharp.pop(layer, None)
            if os.path.exists(L.sharp_path(name, layer)):
                os.remove(L.sharp_path(name, layer))
    L.save_sharp(name, sharp)
    shutil.rmtree(keep)
    L.note(info, "eyes: her own back")
    L.save(name, info)
    print(f"{name}: her own eyes are back. Run `build` again")
