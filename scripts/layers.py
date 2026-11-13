"""Layered characters: each character's See-through layers kept as PNGs we can edit (redraw a part,
recolour a skirt, share a mouth), and the PSD the animated avatar loads, built from them.

`live2d.py layers <command> <name> ...` runs it. By hand, with See-through's Python, which has
psd-tools (MIT), numpy and scipy:
  <see-through python> -I layers.py <command> <name> ...

  import <name> <file.psd>
      her layers from a See-through PSD into <characters>/<name>/layers/parts/, one PNG per
      layer as big as the frame, and their order (bottom first) into layers/layers.json
  add <name> <layer> <file.png> --above <layer>
      a layer from a PNG as big as the frame, such as one See-through made but left out of its PSD;
      faint stray pixels and specks away from the part are dropped
  remove <name> <layer> "<why>"
      drop a layer (its PNG goes; git keeps it), with the reason in layers.json
  move <name> <layer> --above <layer>
      put a layer somewhere else in the order (a skirt above the shirt, so the shirt's tucked
      in), saying how many pixels of her, as she stands, it changes
  repair <name> <layer>...
      make these layers agree with the original drawing wherever each is the one you see: erased
      where a layer below it, or the background, is what the drawing shows; the drawing's own
      colour painted in where nothing below matches. See-through paints in the hidden parts of a
      layer, and sometimes paints them where they aren't hidden (a skirt running on over the thighs)
  lining <name> <layer> <new layer> --above <layer> --light <low> <high>
      the inside of an open coat as a layer of its own, behind her: See-through paints a coat's
      front and the inside of its back as one layer, which then lies over her skirt and legs. The
      biggest patch of <layer> whose lightness (0 to 1) is between <low> and <high> moves to
      <new layer>, placed above the layer named (thin lines of that lightness, a fold or an
      outline, stay where they are)
  under <name> <layer> <over>
      what <over> hides of <layer> along <over>'s lower edge (a band 2% of the frame high),
      painted in <layer>'s own colour from just below it: her neck, and her back hair, under her
      chin. The drawing's jaw line gets coloured into them there, and shows as a second jaw line
      when her head lifts, tilts or turns off it
  strays <name> <layer>
      cut a layer below anything the drawing shows of it (faded out a little below that): See-through
      hangs strands of back hair down a character's back that her drawing never has, and they
      swing out from behind her as she moves
  check <name>
      where the layers, stacked, differ from the drawing: a count per layer, and a picture in
      <out>/layers/<name>-check.png (differences in red)
  build <name>
      layers/model.psd from the parts: the PSD the avatar test page (tools/avatar-test) loads
  pull <name>
      the other way: after model.psd has been touched up in a paint program, each layer that
      changed there back into its PNG, new layers added and the order taken from the PSD, with
      what changed noted in layers.json. Layers have to stay plain: no groups, vector masks,
      effects or blend modes. A layer's opacity is folded into its pixels, and so is a mask,
      where it hides more than the layer's own transparency
  scale <name> <factor>
      every layer and the frame made bigger (2 for twice), then each layer's colour taken from the
      drawing wherever it's the one you see, so what shows is as sharp as the drawing (use an
      upscaled one: full/base-2x.png, from upscale.py); only hidden parts stay soft
  cubism <name>
      layers/cubism.psd: her layers laid out for Cubism Editor, one folder (a Cubism part) per thing
      it rigs, pairs cut into screen-left and screen-right at her face's or body's middle, the eye
      parts in the usual order (white, iris, lashes, closed lid), cropped to her with a margin.
      Cubism's Auto generation of facial motion wants exactly these folders: face, each eye and
      eyeball, each eyebrow, each ear, mouth and nose
  head <name> <head.psd> <crop.json>
      her head's layers (hair, face, eyes, ears, nose, mouth, glasses) taken from a second
      See-through pass on her head alone, cut from the drawing upscaled four times, so they have
      several times the pixels a whole-body pass gives them. crop.json says where the cut was:
      {"box_in_base": [x0, y0, x1, y1] in base.png's pixels, "scale_of_crop": 4, "base": path}.
      Her neck and clothes stay from the whole-body pass, and so does any layer that reaches out
      of the cut (long hair, when the cut is close round her face). The head pass's mouth replaces
      her mouth_close; eye_close and mouth_open go, as they were made from the old eyes and mouth:
      run parts.py closed-eyes and mouth again. Each layer taken is also kept at the head pass's
      own size (parts/<layer>@head.png, and sharp.json beside layers.json), about two and a half
      times her frame's: the build puts those in her model's texture, so her face stays sharp
      when an app shows her close up
  sharp <name>
      the same full-size copies for a character whose head layers were taken before the kit kept
      them: made again from the head PSD kept in her layers folder, for every head layer that is
      still as it was taken. Her layers themselves aren't changed

The drawing is her base.png, placed in the frame as See-through placed it (scaled to the frame's
height, centred), with the background where her idle sprite's cut-out is clear.

<name> can also be a character's other drawing with layers of its own, akane/working: its layers
in <characters>/akane/layers/working/, its drawing sprites/white/working.png and its cut-out
sprites/working.png. For her full-size drawing, akane/full, the drawing is full/base-2x.png if
there is one (upscale.py), else full/base.png, and the cut-out full/cutout.png."""
import datetime, json, os, sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402

ROOT = kit.project()
CHARS = kit.characters()
OUT = kit.out("layers")

DIFF = 0.2    # a stacked pixel this far from the drawing (0 to 1, in any channel) is wrong
MATCH = 0.12  # a layer's pixel this close to the drawing is the one the drawing shows
MARGIN = 0.02 # repair: a layer below shows instead when it's this much closer to the drawing
SOLID = 0.5   # alpha above this hides what's below
SPOT = 40     # a fix smaller than this many pixels is left alone: it's edge noise
FAINT = 16    # added layers: alpha below this (of 255) is stray noise
SPECK = 0.02  # added layers: bits smaller than this share of the biggest piece are dropped
STRAY_KEEP = 16  # strays: a layer is kept this many rows below where the drawing shows it...
STRAY_FADE = 12  # ...and faded out over this many more
UNDER_NEAR = 0.03  # under: a column is compared with the columns this near it, as a share of the frame
UNDER_ODD = 0.18   # ...and is odd when its own colour is this far from their middle one (0 to 1)
UNDER_EVEN = 0.012 # under: colours are evened out over this many columns each side, as a share of the frame

# Layers the rig shows only with her eyes shut, her mouth open or her cheeks flushed (parts.py
# makes them): the drawing has her eyes open, mouth shut and no blush, so check and repair leave
# these out.
SHUT = {"eye_close", "eye_close2", "mouth_open", "mouth_oh", "mouth_pout", "blush"}


POSES = {"working", "full"}  # drawings with layers of their own, besides her base (idle)


def split(name):
    """akane → (akane, None); akane/working → (akane, working), the layers of her working drawing."""
    char, _, pose = name.partition("/")
    if not char or "\\" in name or ".." in name or (pose and pose not in POSES):
        sys.exit(f"{name}: a character, or a character/pose ({', '.join(sorted(POSES))})")
    return char, pose or None


def folder(name):
    char, pose = split(name)
    return os.path.join(CHARS, char, "layers", *([pose] if pose else []))


def slug(name):
    """For file names: akane, akane-working."""
    return name.replace("/", "-")


def load(name):
    with open(os.path.join(folder(name), "layers.json"), encoding="utf-8") as f:
        return json.load(f)


def save(name, info):
    with open(os.path.join(folder(name), "layers.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
        f.write("\n")


def note(info, text):
    info.setdefault("changes", []).append(f"{datetime.date.today()}: {text}")


def part_path(name, layer):
    return os.path.join(folder(name), "parts", layer + ".png")


def read_part(name, layer):
    return np.asarray(Image.open(part_path(name, layer)).convert("RGBA"), np.float32) / 255


def write_part(name, layer, rgba):
    os.makedirs(os.path.join(folder(name), "parts"), exist_ok=True)
    im = np.clip(rgba * 255, 0, 255).round().astype(np.uint8)
    Image.fromarray(im, "RGBA").save(part_path(name, layer), optimize=True)


def drawing_files(name):
    """Her drawing on white and its cut-out: base.png and sprites/idle.png, or for a pose its
    sprites/white/<pose>.png and sprites/<pose>.png, or for her full-size drawing (the Live2D one)
    full/base.png and full/cutout.png."""
    char, pose = split(name)
    sprites = os.path.join(CHARS, char, "sprites")
    if pose == "full":
        full = os.path.join(CHARS, char, "full")
        sharp = os.path.join(full, "base-2x.png")
        return (sharp if os.path.exists(sharp) else os.path.join(full, "base.png"),
                os.path.join(full, "cutout.png"))
    if pose:
        return os.path.join(sprites, "white", pose + ".png"), os.path.join(sprites, pose + ".png")
    return os.path.join(CHARS, char, "base.png"), os.path.join(sprites, "idle.png")


def drawing(name, frame):
    """Her drawing in the frame as See-through placed it, and where she is (not background)."""
    W, H = frame
    on_white, cut_out = drawing_files(name)
    base = Image.open(on_white).convert("RGB")
    cut = Image.open(cut_out).convert("RGBA")
    w = round(base.width * H / base.height)
    x = (W - w) // 2
    rgb = np.ones((H, W, 3), np.float32)
    rgb[:, x:x + w] = np.asarray(base.resize((w, H), Image.LANCZOS), np.float32) / 255
    her = np.zeros((H, W), bool)
    her[:, x:x + w] = np.asarray(cut.resize((w, H), Image.LANCZOS))[..., 3] > 127
    return rgb, her


def composite(stack):
    """The layers stacked on white, as the drawing is, and which layer is on top at each pixel."""
    H, W = stack[0][1].shape[:2]
    rgb = np.ones((H, W, 3), np.float32)
    top = np.full((H, W), -1, np.int16)
    for i, (_, im) in enumerate(stack):
        a = im[..., 3:4]
        rgb = im[..., :3] * a + rgb * (1 - a)
        top[im[..., 3] > SOLID] = i
    return rgb, top


def big(mask, least=SPOT):
    labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if not n:
        return mask
    sizes = ndimage.sum(mask, labels, range(1, n + 1))
    return np.isin(labels, 1 + np.flatnonzero(sizes >= least))


def do_import(name, psd_path):
    from psd_tools import PSDImage
    psd = PSDImage.open(psd_path)
    order = []
    for layer in psd:
        if layer.name in order or "/" in layer.name or "\\" in layer.name:
            sys.exit(f"{layer.name}: a layer name used twice or with a slash")
        full = Image.new("RGBA", (psd.width, psd.height))
        full.paste(layer.topil().convert("RGBA"), (layer.left, layer.top))
        write_part(name, layer.name, np.asarray(full, np.float32) / 255)
        order.append(layer.name)
    info = {"frame": [psd.width, psd.height], "order": order, "from": os.path.basename(psd_path)}
    note(info, f"imported {len(order)} layers from {os.path.basename(psd_path)}")
    save(name, info)
    print(f"{name}: {len(order)} layers, bottom first: {', '.join(order)}")


def clean_alpha(im):
    """Faint stray pixels (alpha under FAINT) and specks away from the part dropped."""
    im = im.copy()
    a = np.where(im[..., 3] < FAINT / 255, 0, im[..., 3])
    labels, n = ndimage.label(a > 0.05, structure=np.ones((3, 3)))
    if n > 1:
        sizes = ndimage.sum(np.ones(a.shape), labels, range(1, n + 1))
        a = np.where(np.isin(labels, 1 + np.flatnonzero(sizes < SPECK * sizes.max())), 0, a)
    im[..., 3] = a
    return im


def do_add(name, layer, png, above):
    info = load(name)
    if above not in info["order"]:
        sys.exit(f"{above}: no such layer; there are {', '.join(info['order'])}")
    im = np.asarray(Image.open(png).convert("RGBA"), np.float32) / 255
    if list(im.shape[1::-1]) != info["frame"]:
        sys.exit(f"{png}: {im.shape[1]}x{im.shape[0]}, the frame is {info['frame'][0]}x{info['frame'][1]}")
    write_part(name, layer, clean_alpha(im))
    if layer in info["order"]:
        info["order"].remove(layer)
    info["order"].insert(info["order"].index(above) + 1, layer)
    note(info, f"added {layer} above {above}, from {os.path.basename(png)}")
    save(name, info)
    print(f"{name}: {layer} added above {above}")


def do_remove(name, layer, why):
    info = load(name)
    if layer not in info["order"]:
        sys.exit(f"{layer}: no such layer; there are {', '.join(info['order'])}")
    info["order"].remove(layer)
    os.remove(part_path(name, layer))
    note(info, f"removed {layer}: {why}")
    save(name, info)
    print(f"{name}: {layer} removed")


def shown_stack(name, order):
    return [(layer, read_part(name, layer)) for layer in order if layer not in SHUT]


def do_move(name, layer, above):
    info = load(name)
    for x in (layer, above):
        if x not in info["order"]:
            sys.exit(f"{x}: no such layer; there are {', '.join(info['order'])}")
    before, _ = composite(shown_stack(name, info["order"]))
    order = [x for x in info["order"] if x != layer]
    order.insert(order.index(above) + 1, layer)
    after, _ = composite(shown_stack(name, order))
    n = int((np.abs(after - before).max(axis=2) > DIFF).sum())
    info["order"] = order
    note(info, f"moved {layer} above {above} ({n} px of her look different)")
    save(name, info)
    print(f"{name}: {layer} now above {above}; {n} px of her look different")


def do_repair(name, targets):
    info = load(name)
    order = info["order"]
    shown = [layer for layer in order if layer not in SHUT]
    for t in targets:
        if t not in shown:
            sys.exit(f"{t}: no such layer, or one the drawing doesn't show; there are {', '.join(shown)}")
    stack = [[layer, read_part(name, layer)] for layer in shown]
    orig, her = drawing(name, info["frame"])
    done = []
    # From the top down: once a layer stops covering the one below, that one may show where
    # it shouldn't too.
    for t in sorted(targets, key=shown.index, reverse=True):
        ti = shown.index(t)
        rgb, top = composite(stack)
        im = stack[ti][1].copy()
        on_top = top == ti
        wrong = (np.abs(rgb - orig).max(axis=2) > DIFF) & on_top
        own = np.abs(im[..., :3] - orig).max(axis=2)
        # How close the best layer below comes to the drawing.
        below = np.full(own.shape, np.inf, np.float32)
        for k in range(ti):
            lower = stack[k][1]
            d = np.abs(lower[..., :3] - orig).max(axis=2)
            below = np.where(lower[..., 3] > SOLID, np.minimum(below, d), below)
        matches_below = below < MATCH
        # The drawing shows the layer below wherever that comes closer to it than this one, even
        # by a little (a lavender panel over a lavender skirt); gaps in such a patch close up.
        erase = on_top & matches_below & (below + MARGIN < own)
        erase = ndimage.binary_closing(erase, structure=np.ones((3, 3)), iterations=2) & on_top & matches_below
        erase = big(erase | (wrong & ~her))
        paint = big(wrong & her & ~matches_below & ~erase)
        # The soft edge round what's erased goes with it, or a faint outline would stay.
        rim = ndimage.binary_dilation(erase, iterations=2) & ~erase & ~paint & (im[..., 3] < 0.9)
        im[..., 3][erase | rim] = 0
        im[..., :3][paint] = orig[paint]
        im[..., 3][paint] = 1
        stack[ti][1] = im
        write_part(name, t, im)
        done.append(f"{t} ({int(erase.sum())} px erased, {int(paint.sum())} painted)")
        print(f"{name} {t}: {int(erase.sum())} px erased (a layer below or the background shows there), "
              f"{int(paint.sum())} px painted from the drawing")
    note(info, "repaired against the drawing: " + ", ".join(done))
    save(name, info)


def do_lining(name, layer, new, above, low, high):
    info = load(name)
    for x in (layer, above):
        if x not in info["order"]:
            sys.exit(f"{x}: no such layer; there are {', '.join(info['order'])}")
    if new in info["order"]:
        sys.exit(f"{new}: she has that layer already")
    im = read_part(name, layer)
    light = im[..., :3].mean(axis=2)
    wanted = (im[..., 3] > 0.5) & (light >= low) & (light <= high)
    patches, n = ndimage.label(ndimage.binary_opening(wanted, iterations=3))
    if not n:
        sys.exit(f"{layer}: nothing that light")
    sizes = ndimage.sum(np.ones_like(patches), patches, range(1, n + 1))
    patch = ndimage.binary_fill_holes(patches == 1 + int(np.argmax(sizes)))
    back = np.where(patch[..., None], im, 0).astype(np.float32)
    write_part(name, new, back)
    write_part(name, layer, np.where(patch[..., None], 0, im).astype(np.float32))
    info["order"].insert(info["order"].index(above) + 1, new)
    note(info, f"{new} taken out of {layer}: its biggest patch between {low} and {high} light, "
               f"{int(patch.sum())} px, placed above {above}")
    save(name, info)
    print(f"{name}: {new}, {int(patch.sum())} px out of {layer}, now above {above}")


def do_under(name, layer, over):
    info = load(name)
    for x in (layer, over):
        if x not in info["order"]:
            sys.exit(f"{x}: no such layer; there are {', '.join(info['order'])}")
    im, cover = read_part(name, layer), read_part(name, over)[..., 3] > 0.5
    hidden = cover & (im[..., 3] > 0.5)
    reach = max(4, round(0.004 * im.shape[0]))  # this far below the hidden part, clear of its outline
    band = round(0.02 * im.shape[0])
    found = []  # (column, where to paint from and to, the colour found below it)
    for x in np.where(hidden.any(axis=0))[0]:
        rows = np.where(hidden[:, x])[0]
        low = rows.max() + reach
        below = np.arange(low, min(low + 3 * reach, im.shape[0]))
        below = below[(im[below, x, 3] > 0.5) & ~cover[below, x]]
        if len(below):  # the middle colour of a short run, so one dark line there isn't what spreads
            found.append((x, max(rows.min(), rows.max() - band), low, np.median(im[below, x, :3], axis=0)))
    # A few columns can find something else just below: a choker close under her chin gave black
    # stripes up her neck. A column far from the middle colour of the columns round it is odd, and
    # takes its colour from the nearest columns that aren't, each side, by how near each is: the
    # colours run on across it, with no panel of another shade.
    cols = np.array([f[0] for f in found])
    colours = np.array([f[3] for f in found]).reshape(-1, 3)
    near = round(UNDER_NEAR * im.shape[0])
    odd = np.array([np.abs(c - np.median(colours[np.abs(cols - x) <= near], axis=0)).max() > UNDER_ODD
                    for x, c in zip(cols, colours)], bool)
    good = np.nonzero(~odd)[0]
    if len(good) and odd.any():
        for channel in range(3):
            colours[odd, channel] = np.interp(cols[odd], cols[good], colours[good, channel])
    # Then each column's colour is evened out with the columns beside it, so a column that found a
    # little shadow below doesn't stand as a stripe next to one that found none.
    if len(cols) > 2:
        even = round(UNDER_EVEN * im.shape[0])
        colours = np.array([colours[np.abs(cols - x) <= even].mean(axis=0) for x in cols])
    n = 0
    for (x, top, low, _), colour in zip(found, colours):
        im[top:low, x, :3] = colour
        n += low - top
    write_part(name, layer, im)
    note(info, f"{layer} under {over} painted in its own colour from just below ({n} px)")
    save(name, info)
    print(f"{name}: {layer} under {over}: {n} px painted" + (f"; {int(odd.sum())} columns found another colour just "
                                                            "below and took the columns' beside them" if odd.any() else ""))


def do_strays(name, layer):
    info = load(name)
    stack = shown_stack(name, info["order"])
    names = [n for n, _ in stack]
    if layer not in names:
        sys.exit(f"{layer}: no such layer, or one the drawing doesn't show; there are {', '.join(names)}")
    _, top = composite(stack)
    rows = np.nonzero((top == names.index(layer)).any(axis=1))[0]
    if not len(rows):
        sys.exit(f"{layer}: the drawing shows none of it")
    lowest = int(rows.max())
    im = read_part(name, layer)
    labels, n = ndimage.label(im[..., 3] > 0.02, structure=np.ones((3, 3)))
    gone = 0
    for k in range(1, n + 1):
        piece = labels == k
        if np.nonzero(piece.any(axis=1))[0].min() > lowest:
            gone += int(piece.sum())
            im[piece] = 0
    # And a strand that hangs on from the hair itself: faded out from a little below that row.
    fade = np.clip(1 - (np.arange(im.shape[0]) - (lowest + STRAY_KEEP)) / STRAY_FADE, 0, 1)[:, None]
    gone += int(((im[..., 3] > 0.02) & (fade < 1)).sum())
    im[..., 3] *= fade
    write_part(name, layer, im)
    note(info, f"{layer}: cut below where the drawing shows any of it (row {lowest}; faded out over "
               f"{STRAY_FADE} rows from {STRAY_KEEP} below it), {gone} px: strands See-through hung where "
               f"the drawing has none")
    save(name, info)
    print(f"{name} {layer}: {gone} px cut below row {lowest}")


def do_check(name):
    info = load(name)
    stack = [(layer, read_part(name, layer)) for layer in info["order"] if layer not in SHUT]
    orig, her = drawing(name, info["frame"])
    rgb, top = composite(stack)
    bad = np.abs(rgb - orig).max(axis=2) > DIFF
    print(f"{name}: {int(bad.sum())} px differ from the drawing")
    for i, (layer, _) in enumerate(stack):
        n = int((bad & (top == i)).sum())
        if n:
            print(f"  {layer} on top: {n}")
    n = int((bad & (top < 0) & her).sum())
    if n:
        print(f"  no layer, but she's there in the drawing: {n}")
    os.makedirs(OUT, exist_ok=True)
    pic = orig * 0.35 + bad[..., None] * np.array([0.65, 0, 0], np.float32)
    path = os.path.join(OUT, f"{slug(name)}-check.png")
    Image.fromarray((np.clip(pic, 0, 1) * 255).astype(np.uint8)).save(path)
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, f"{slug(name)}-stacked.png"))
    print(f"  {path}")


def do_build(name):
    from psd_tools import PSDImage
    from psd_tools.constants import Compression
    info = load(name)
    W, H = info["frame"]
    psd = PSDImage.new("RGBA", (W, H), depth=8)
    whole = Image.new("RGBA", (W, H))
    for layer in info["order"]:
        im = Image.open(part_path(name, layer)).convert("RGBA")
        box = im.getbbox()
        if box:
            psd.create_pixel_layer(im.crop(box), name=layer, top=box[1], left=box[0])
        if layer not in SHUT:
            whole.alpha_composite(im)
    # The picture a viewer shows for the whole file (her as drawn, eyes open and mouth shut),
    # compressed as the layers are: stored raw it was two thirds of the file.
    psd._record.image_data.compression = Compression.RLE
    psd._record.image_data.set_data([band.tobytes() for band in whole.split()], psd._record.header)
    out = os.path.join(folder(name), "model.psd")
    psd.save(out)
    print(f"{out}: {len(info['order'])} layers, {os.path.getsize(out) // 1024} KB")


def do_pull(name):
    from psd_tools import PSDImage
    from psd_tools.constants import BlendMode
    info = load(name)
    W, H = info["frame"]
    psd = PSDImage.open(os.path.join(folder(name), "model.psd"))
    if [psd.width, psd.height] != [W, H]:
        sys.exit(f"model.psd is {psd.width}x{psd.height}, her frame is {W}x{H}")
    plain = []
    for layer in psd:
        why = ("a group" if layer.is_group() else
               f"a {layer.kind} layer" if layer.kind != "pixel" else
               "a vector mask" if layer.has_vector_mask() else
               "effects" if layer.has_effects() else
               "a blend mode" if layer.blend_mode != BlendMode.NORMAL else
               "a slash in its name" if "/" in layer.name or "\\" in layer.name else
               "a name used twice" if layer.name in [n for n, _ in plain] else None)
        if why:
            sys.exit(f"{layer.name}: {why}; merge or flatten it in the paint program first, nothing taken")
        full = Image.new("RGBA", (W, H))
        pic = layer.topil()
        if pic is not None:
            full.paste(pic.convert("RGBA"), (layer.left, layer.top))
        im = np.asarray(full, np.float32) / 255
        im[..., 3] *= layer.opacity / 255
        mask = layer.mask
        if layer.has_mask() and not mask.disabled and mask.topil() is not None:
            # Some paint programs save each layer's own transparency again as a mask; the rig
            # ignores masks. So a mask counts only where it hides more than the layer itself
            # does: multiplying would thin every soft edge (the hair's especially).
            m = np.full((H, W), mask.background_color / 255, np.float32)
            part = np.asarray(mask.topil().convert("L"), np.float32) / 255
            x0, y0 = max(mask.left, 0), max(mask.top, 0)
            x1, y1 = min(mask.left + part.shape[1], W), min(mask.top + part.shape[0], H)
            m[y0:y1, x0:x1] = part[y0 - mask.top:y1 - mask.top, x0 - mask.left:x1 - mask.left]
            im[..., 3] = np.minimum(im[..., 3], m)
        if not layer.visible:
            print(f"  {layer.name} is hidden in the PSD; taken all the same (hide layers in the rig)")
        plain.append((layer.name, im))
    changed, added = [], []
    for layer, im in plain:
        if layer in info["order"]:
            old = read_part(name, layer)
            # Compare what shows: colours under clear pixels don't count.
            diff = np.abs(im[..., :3] * im[..., 3:] - old[..., :3] * old[..., 3:]).max(axis=2)
            diff = np.maximum(diff, np.abs(im[..., 3] - old[..., 3]))
            n = int((diff > 2 / 255).sum())
            if not n:
                continue
            changed.append(f"{layer} ({n} px)")
        else:
            added.append(layer)
        write_part(name, layer, im)
    order = [layer for layer, _ in plain]
    gone = [layer for layer in info["order"] if layer not in order]
    for layer in gone:
        os.remove(part_path(name, layer))
    kept = [layer for layer in order if layer in info["order"]]
    moved = kept != [layer for layer in info["order"] if layer in order]
    info["order"] = order
    said = (["touched up in model.psd: " + ", ".join(changed)] if changed else []) + \
           (["added in model.psd: " + ", ".join(added)] if added else []) + \
           (["removed in model.psd: " + ", ".join(gone)] if gone else []) + \
           (["reordered in model.psd"] if moved else [])
    for text in said:
        note(info, text)
        print(f"{name}: {text}")
    if not said:
        print(f"{name}: model.psd has nothing new")
    save(name, info)


def resize_rgba(im, size):
    """A layer resized with its colours weighted by alpha, so clear pixels don't darken its edges."""
    a = im[..., 3]
    out = [np.asarray(Image.fromarray(ch, "F").resize(size, Image.LANCZOS))
           for ch in (im[..., 0] * a, im[..., 1] * a, im[..., 2] * a, a)]
    a = np.clip(out[3], 0, 1)
    rgb = np.stack(out[:3], axis=-1) / np.maximum(a, 1e-4)[..., None]
    return np.concatenate([np.clip(rgb, 0, 1), a[..., None]], axis=-1).astype(np.float32)


def do_scale(name, factor):
    info = load(name)
    W, H = info["frame"]
    size = (round(W * factor), round(H * factor))
    for layer in info["order"]:
        write_part(name, layer, resize_rgba(read_part(name, layer), size))
    info["frame"] = list(size)
    # What shows of each layer, from the drawing at the new size: as sharp as the drawing is.
    orig, _ = drawing(name, size)
    shown = [layer for layer in info["order"] if layer not in SHUT]
    _, top = composite([(layer, read_part(name, layer)) for layer in shown])
    for i, layer in enumerate(shown):
        im = read_part(name, layer)
        im[..., :3] = np.where((top == i)[..., None], orig, im[..., :3])
        write_part(name, layer, im)
    on_white, _ = drawing_files(name)
    note(info, f"scaled {factor:g} times to {size[0]}x{size[1]}; what shows coloured from "
               f"{os.path.basename(on_white)}")
    save(name, info)
    print(f"{name}: {len(info['order'])} layers at {size[0]}x{size[1]}")


HEAD = {"back hair", "front hair", "face", "ears", "eyebrow", "eyelash", "eyewhite", "irides",
        "nose", "mouth", "eyewear", "headwear", "earwear"}


# A head layer at the head pass's own size: parts/<layer>@head.png, with where it lies in her frame
# in sharp.json ({layer: {"at": [x, y] of its corner in her frame's pixels, "per": [x, y] how many
# of her frame's pixels one of its pixels is}}). Her layers stay the truth: the build uses a sharp
# copy only while it still matches its layer, so an edit to a layer simply switches its copy off.
SHARP = "sharp.json"
SHARP_SAME = 0.03  # sharp: a head layer this close to the head pass's (0 to 1, on average) is as it was taken


def sharp_path(name, layer):
    return os.path.join(folder(name), "parts", layer + "@head.png")


def load_sharp(name):
    path = os.path.join(folder(name), SHARP)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_sharp(name, sharp):
    with open(os.path.join(folder(name), SHARP), "w", encoding="utf-8", newline="\n") as f:
        json.dump(sharp, f, indent=2, ensure_ascii=False)
        f.write("\n")


def rename_sharp(name, old, new):
    """A layer's sharp copy goes with it when the layer is renamed (mouth to mouth_close)."""
    sharp = load_sharp(name)
    if old in sharp and os.path.exists(sharp_path(name, old)):
        os.replace(sharp_path(name, old), sharp_path(name, new))
        sharp[new] = sharp.pop(old)
        save_sharp(name, sharp)


def head_placing(name, info, psd, crop):
    """Where a head pass's frame lies in hers: its size there, its corner, the cut's own box in her
    frame, and how many of her pixels one of its pixels is."""
    W, H = info["frame"]
    x0, y0, x1, y1 = crop["box_in_base"]
    c = crop["scale_of_crop"]
    base = os.path.join(ROOT, crop["base"])
    if not os.path.exists(base):  # the project was moved since the cut: her drawing, where it is now
        char, pose = split(name)
        base = os.path.join(CHARS, char, *([pose] if pose else []), "base.png")
    bw, bh = Image.open(base).size
    # Her drawing in her frame, as drawing() places it.
    s = H / bh
    X = (W - round(bw * s)) // 2
    # The head cut in the head pass's frame: See-through fits its longer side to the frame and
    # centres it. (This took the height to be the longer side, right for one character's tall cut; another's
    # was wider than tall, so her face went in 7% small and her drawn jaw line showed under it.)
    k = min(psd.width / ((x1 - x0) * c), psd.height / ((y1 - y0) * c))
    xo = (psd.width - (x1 - x0) * c * k) / 2
    yo = (psd.height - (y1 - y0) * c * k) / 2
    m = s / (c * k)  # head-pass pixels to hers
    size = (round(psd.width * m), round(psd.height * m))
    at = (round(X + x0 * s - xo * m), round(y0 * s - yo * m))
    cut = (round(X + x0 * s), round(y0 * s), round(X + x1 * s), round(y1 * s))
    return size, at, cut, m


def head_layer(psd, layer, size, at, frame):
    """One layer of the head pass as a layer of hers: shrunk to her frame's size and put in place."""
    W, H = frame
    part = Image.new("RGBA", (psd.width, psd.height))
    pic = layer.topil()
    if pic is not None:
        part.paste(pic.convert("RGBA"), (layer.left, layer.top))
    small = resize_rgba(np.asarray(part, np.float32) / 255, size)
    full = np.zeros((H, W, 4), np.float32)
    fx0, fy0 = max(at[0], 0), max(at[1], 0)
    fx1, fy1 = min(at[0] + size[0], W), min(at[1] + size[1], H)
    full[fy0:fy1, fx0:fx1] = small[fy0 - at[1]:fy1 - at[1], fx0 - at[0]:fx1 - at[0]]
    return full


def best_fit(taken, hers):
    """How far a head-pass layer, put in her frame, is from her own layer, at the whole-pixel shift
    of up to 2 that fits best: (how far apart on average from 0 to 1, the shift across, the shift
    down). An older kit rounded a head layer's place a pixel differently."""
    where = (taken[..., 3] > 0.05) | (hers[..., 3] > 0.05)
    if not where.any():
        return 1.0, 0, 0
    ys, xs = np.nonzero(where)
    y0, y1, x0, x1 = max(ys.min() - 3, 0), ys.max() + 4, max(xs.min() - 3, 0), xs.max() + 4
    a, b = taken[y0:y1, x0:x1], hers[y0:y1, x0:x1]
    a, b = a[..., :3] * a[..., 3:4], b[..., :3] * b[..., 3:4]
    seen = where[y0:y1, x0:x1]
    best = (9.0, 0, 0)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            moved = np.roll(a, (dy, dx), axis=(0, 1))
            both = seen | np.roll(seen, (dy, dx), axis=(0, 1))
            best = min(best, (float(np.abs(moved - b)[both].mean()), dx, dy))
    return best


def keep_sharp(name, sharp, target, psd, layer, size, at):
    """Keep a head-pass layer at its own size beside her layer."""
    pic = layer.topil()
    if pic is None:
        return False
    pic.convert("RGBA").save(sharp_path(name, target), optimize=True)
    per = (size[0] / psd.width, size[1] / psd.height)
    sharp[target] = {"at": [at[0] + layer.left * per[0], at[1] + layer.top * per[1]], "per": list(per)}
    return True


def do_sharp(name):
    from psd_tools import PSDImage
    info = load(name)
    psds = sorted(f for f in os.listdir(folder(name)) if f.endswith("-head.psd"))
    crop_path = os.path.join(folder(name), "head-crop.json")
    if not psds or not os.path.exists(crop_path):
        sys.exit(f"{name}: no head PSD and head-crop.json in {folder(name)}: the head pass (`split <name> head`) makes them")
    psd = PSDImage.open(os.path.join(folder(name), psds[-1]))
    size, at, _, m = head_placing(name, info, psd, json.load(open(crop_path, encoding="utf-8")))
    order, sharp, made, changed = info["order"], load_sharp(name), [], []
    for layer in psd:
        if layer.name not in HEAD:
            continue
        target = "mouth_close" if layer.name == "mouth" and "mouth_close" in order else layer.name
        if target not in order:
            continue
        apart, dx, dy = best_fit(head_layer(psd, layer, size, at, info["frame"]), read_part(name, target))
        if apart <= SHARP_SAME and keep_sharp(name, sharp, target, psd, layer, size, (at[0] + dx, at[1] + dy)):
            made.append(target + (f" (moved {dx:+d},{dy:+d})" if dx or dy else ""))
        else:
            changed.append(f"{target} ({apart:.2f} apart)")
            sharp.pop(target, None)
            if os.path.exists(sharp_path(name, target)):
                os.remove(sharp_path(name, target))
    save_sharp(name, sharp)
    print(f"{name}: kept at the head pass's own size ({1 / m:.2f} times her frame's): {', '.join(made) or 'none'}")
    if changed:
        print(f"  not as the head pass made them (from the whole-body pass, or changed since), left at her frame's size: {', '.join(changed)}")
    print(f"next: `live2d.py build {name.removesuffix('/full')}`")


def do_head(name, psd_path, crop_path):
    from psd_tools import PSDImage
    info = load(name)
    W, H = info["frame"]
    crop = json.load(open(crop_path, encoding="utf-8"))
    psd = PSDImage.open(psd_path)
    size, at, (cx0, cy0, cx1, cy1), m = head_placing(name, info, psd, crop)
    order, taken, left, kept, sharp = info["order"], [], [], [], load_sharp(name)
    for layer in psd:
        if layer.name not in HEAD:
            continue
        target = "mouth_close" if layer.name == "mouth" and "mouth_close" in order else layer.name
        if target not in order:
            left.append(layer.name)
            continue
        # The cut in her frame, a little inside its edge: a layer of hers with anything out of it
        # was cut short by the head pass (long hair), so hers stays.
        inside = np.zeros((H, W), bool)
        edge = round(0.02 * (cy1 - cy0))
        inside[max(cy0 + edge, 0):cy1 - edge, max(cx0 + edge, 0):cx1 - edge] = True
        if cy0 <= 0:  # a cut that starts at the top of her drawing has no edge there
            inside[:edge, max(cx0 + edge, 0):cx1 - edge] = True
        if ((read_part(name, target)[..., 3] > 0.5) & ~inside).sum() > SPOT:
            kept.append(target)
            continue
        write_part(name, target, head_layer(psd, layer, size, at, info["frame"]))
        keep_sharp(name, sharp, target, psd, layer, size, at)
        taken.append(target)
    save_sharp(name, sharp)
    gone = [layer for layer in ("eye_close", "mouth_open", "blush") if layer in order]
    for layer in gone:
        os.remove(part_path(name, layer))
        order.remove(layer)
    note(info, f"head layers from {os.path.basename(psd_path)} (a head pass, {m:.2f} of its pixels to "
               f"one of hers): {', '.join(taken)}" + (f"; {', '.join(kept)} reach out of the cut and stay"
               if kept else "") + (f"; {', '.join(gone)} removed, to be made again "
               "from the new eyes and mouth" if gone else ""))
    save(name, info)
    print(f"{name}: head layers taken: {', '.join(taken)}")
    if kept:
        print(f"  reach out of the cut, kept from the whole-body pass: {', '.join(kept)}")
    if left:
        print(f"  not in her layers, left out: {', '.join(left)}")
    if gone:
        print(f"  removed {', '.join(gone)}: run parts.py closed-eyes {name}, then parts.py mouth {name}")


# Cubism's layout, bottom first: (folder, [(art mesh name, her layer, side)]), side "" for whole,
# "left" or "right" for the half of a pair on that side of the screen. A folder inside a folder is
# ("Folder", [...]) in place of an art mesh. Layers she doesn't have are skipped.
CUBISM = [
    ("Back hair", [("Back hair", "back hair", "")]),
    ("Arm (screen left)", [("Arm (screen left)", "handwear", "left")]),
    ("Arm (screen right)", [("Arm (screen right)", "handwear", "right")]),
    ("Legs", [("Leg (screen left)", "legwear", "left"), ("Leg (screen right)", "legwear", "right"),
              ("Shoe (screen left)", "footwear", "left"), ("Shoe (screen right)", "footwear", "right")]),
    ("Neck", [("Neck", "neck", "")]),
    ("Body", [("Skirt", "bottomwear", ""), ("Top", "topwear", "")]),
    ("Ear (screen left)", [("Ear (screen left)", "ears", "left")]),
    ("Ear (screen right)", [("Ear (screen right)", "ears", "right")]),
    ("Face", [("Face", "face", "")]),
    ("Nose", [("Nose", "nose", "")]),
    ("Mouth", [("Mouth closed", "mouth_close", ""), ("Mouth open (hide at rest)", "mouth_open", "")]),
    ("Eye (screen left)", [("Eye white (screen left)", "eyewhite", "left"),
                           ("Eyeball (screen left)", [("Iris (screen left)", "irides", "left")]),
                           ("Lashes (screen left)", "eyelash", "left"),
                           ("Lid closed (screen left, hide at rest)", "eye_close", "left")]),
    ("Eye (screen right)", [("Eye white (screen right)", "eyewhite", "right"),
                            ("Eyeball (screen right)", [("Iris (screen right)", "irides", "right")]),
                            ("Lashes (screen right)", "eyelash", "right"),
                            ("Lid closed (screen right, hide at rest)", "eye_close", "right")]),
    ("Eyebrow (screen left)", [("Eyebrow (screen left)", "eyebrow", "left")]),
    ("Eyebrow (screen right)", [("Eyebrow (screen right)", "eyebrow", "right")]),
    ("Glasses", [("Glasses", "eyewear", "")]),
    ("Headwear", [("Headwear", "headwear", "")]),
    ("Front hair", [("Front hair", "front hair", "")]),
]
FACE_PARTS = {"ears", "eyewhite", "irides", "eyelash", "eye_close", "eyebrow"}
MARGIN_PX = 0.04  # cubism: margin round her, as a share of the frame


def do_cubism(name):
    from psd_tools import PSDImage
    from psd_tools.api.layers import Group, PixelLayer
    info = load(name)
    have = set(info["order"])
    W, H = info["frame"]
    parts = {layer: clean_alpha(read_part(name, layer)) for layer in info["order"]}

    def middle(layer):
        xs = np.nonzero((parts[layer][..., 3] > 0.5).any(axis=0))[0]
        return (xs.min() + xs.max()) / 2 if len(xs) else W / 2
    # Pairs are cut at her face's middle (face parts) or her neck's (the rest).
    face_x = middle("face") if "face" in have else W / 2
    body_x = middle("neck") if "neck" in have else face_x
    whole = np.zeros((H, W), bool)
    for im in parts.values():
        whole |= im[..., 3] > 0
    ys, xs = np.nonzero(whole)
    m = round(MARGIN_PX * max(W, H))
    box = (max(xs.min() - m, 0), max(ys.min() - m, 0), min(xs.max() + m + 1, W), min(ys.max() + m + 1, H))

    psd = PSDImage.new("RGBA", (box[2] - box[0], box[3] - box[1]), depth=8)
    made, empty = [], []

    def add(parent, label, items):
        group = Group.new(parent, name=label)
        for item in items:
            if isinstance(item[1], list):
                add(group, *item)
                continue
            mesh, layer, side = item
            if layer not in have:
                continue
            im = parts[layer].copy()
            if side:
                cut = round(face_x if layer in FACE_PARTS else body_x)
                if side == "left":
                    im[:, cut:, 3] = 0
                else:
                    im[:, :cut, 3] = 0
            im = clean_alpha(im)
            pic = Image.fromarray((np.clip(im, 0, 1) * 255).round().astype(np.uint8), "RGBA").crop(box)
            bb = pic.getbbox()
            if not bb:
                empty.append(mesh)
                continue
            art = PixelLayer.frompil(pic.crop(bb), group, name=mesh, top=bb[1], left=bb[0])
            if layer in SHUT:
                art.visible = False  # shown only with her eyes shut or mouth open
            made.append(mesh)
        if not len(group):
            parent.remove(group)

    for label, items in CUBISM:
        add(psd, label, items)
    out = os.path.join(folder(name), "cubism.psd")
    psd.save(out)
    print(f"{out}: {len(made)} art meshes in {len(psd)} parts, {psd.width}x{psd.height}, "
          f"{os.path.getsize(out) // 1024} KB")
    if empty:
        print(f"  empty after the cut, left out: {', '.join(empty)}")


def main(args):
    if len(args) < 2:
        sys.exit(__doc__)
    cmd, name, rest = args[0], args[1], args[2:]
    if cmd == "import" and len(rest) == 1:
        do_import(name, rest[0])
    elif cmd == "add" and len(rest) == 4 and rest[2] == "--above":
        do_add(name, rest[0], rest[1], rest[3])
    elif cmd == "remove" and len(rest) == 2:
        do_remove(name, rest[0], rest[1])
    elif cmd == "move" and len(rest) == 3 and rest[1] == "--above":
        do_move(name, rest[0], rest[2])
    elif cmd == "repair" and rest:
        do_repair(name, rest)
    elif cmd == "lining" and len(rest) == 7 and rest[2] == "--above" and rest[4] == "--light":
        do_lining(name, rest[0], rest[1], rest[3], float(rest[5]), float(rest[6]))
    elif cmd == "under" and len(rest) == 2:
        do_under(name, rest[0], rest[1])
    elif cmd == "strays" and len(rest) == 1:
        do_strays(name, rest[0])
    elif cmd == "check" and not rest:
        do_check(name)
    elif cmd == "build" and not rest:
        do_build(name)
    elif cmd == "pull" and not rest:
        do_pull(name)
    elif cmd == "scale" and len(rest) == 1:
        do_scale(name, float(rest[0]))
    elif cmd == "cubism" and not rest:
        do_cubism(name)
    elif cmd == "head" and len(rest) == 2:
        do_head(name, rest[0], rest[1])
    elif cmd == "sharp" and not rest:
        do_sharp(name)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
