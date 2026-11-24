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
  seams <name>
      after the head pass: put right what `scale` coloured into her other layers from the drawing
      where it shows something else, which shows as a second jaw line or a seam across her neck
      once her head moves. Each layer's own colour is See-through's, from the PSD kept in her
      layers folder. Round her face, a layer holding the drawing's colour of something else (her
      jaw line or neck on her back hair, bits of her chin on her clothes) is cleared where a layer
      below it is what the drawing shows, and under her face it gets its own colour back, shaded
      like what shows of it nearby. Hair kept from the whole-body pass that lies above her neck in
      the order is cleared where her face hides it over her neck, so it can't swing out over it.
      And a layer's soft edge across her neck where the drawing shows no edge (a shirt's top edge)
      takes the drawing's colour, so no faint line runs there. A bit of a layer lying apart from the
      rest of it, mostly under her face (a scrap of collar), is cleared. Her neck itself, her hair
      below her face and the layers the head pass gave are left as they are. `head` runs this
      itself; run it for a character whose head layers were taken before it did, then `build`.
      Running it again changes nothing
  redraw <name> <layer> --under <layer>[,<layer>...] [--prompt "<what to change>"] [--seed <n>]
      what the layers named hide of <layer>, drawn again with Qwen Image 2.1's edit. See-through
      makes that part up, and scale colours the drawing's line along their edge into it: a
      cardigan under long hair shows the strands' outlines once the hair swings, thighs under a
      skirt its hem line and another shade of skin. Her layer is shown to the model alone on grey;
      only that part, a thin band round it and the slits See-through cut along the line are drawn
      again, and only they are kept. Her layer's own alpha stays, so what is clear round her stays
      clear, and the outer half of the line along the edge of the layer over it moves onto that
      layer's soft edge, so she is as drawn at rest and the line swings with the hair or skirt it
      belongs to. The prompt says what to change, in plain colour words for this layer ("Remove
      the thin dark lines that run down the cream cardigan on both sides, and fill them with the
      same cream colour and soft shading around them."; "knitted" drew a knit texture); without
      one it asks for stray lines, seams and gaps to go. A before-and-after picture and the layers
      as they were go to <out>/redraw/. It needs ComfyUI running (`live2d.py comfy start`) and the
      GPU to itself; then `build`
  redraw <name> <layer> --behind <layer> [--prompt "<what to change>"] [--seed <n>]
      the gaps in <layer> where the layer named, below it, shows through as she stands: her sleeves
      lie over her top's sides in the drawing, so repair cut her top away there, and the holes show
      her back hair once her arms swing out. Drawn with Qwen Image 2.1's edit, the gaps and a ring
      of her layer round them together (so they blend), on a flat key colour, starting from
      See-through's own colour in the gaps, with her layer's edge there drawn clean. Kept as a layer
      of its own, "<layer> behind <layer>", just under the layer named, and evened out to meet her
      layer's colour all round each hole: hidden as she stands, there once that layer moves away.
      Her layer's ragged edge over that layer goes to it (where it is her in the drawing), so she is
      as drawn at rest. layers.json's "moves_with" says which layer it patches, and `build` moves it
      exactly as that one (no swing of its own). To draw it again, put back the layers kept in
      <out>/redraw/ and `remove` it first
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
import datetime, io, json, os, shutil, sys

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
SEAM_SAME = 0.02   # seams: a layer's pixel this close to the drawing still holds the colour scale gave it
SEAM_NEAR = 0.02   # seams: what round her face is looked at, as a share of the frame
SEAM_EDGE = 0.006  # seams: as a share of the frame, how far a soft edge looks for its own layer's solid colour,
                   # and how far out her face's soft edge reaches
SEAM_FAINT = 0.02  # seams: alpha under this is no part of a layer
REDRAW_BAND = 0.004  # redraw: as a share of the frame, how far out from the edge of what lies over her layer it
                     # redraws too: scale coloured the drawing's line along that edge into her layer just there
REDRAW_PAD = 0.03    # redraw: how much of her layer round that part the model sees, as a share of the frame
REDRAW_SIZE = 1024   # redraw: the picture sent is about this many pixels square, at multiples of 32: the size
                     # Qwen Image 2.1 edits at (it brings a picture to about this size anyway)
REDRAW_GREY = 0.5    # redraw: the flat background her layer is shown on; none of it is kept
BEHIND_CLOSE = 0.006  # redraw --behind: a gap narrower than about twice this share of the frame is a bit
                      # cut out of her layer's edge, not its own shape (15 px at a 2560 frame)
BEHIND_RING = 0.008   # ...how far round each gap her layer is drawn again with it, so the patch blends in
BEHIND_RIM = 0.0012   # ...her layer's pixels this near a gap that hold the line of the layer below (scale
                      # coloured it in) go to that layer, so the line moves with it
BEHIND_EVEN = 400     # ...rounds of evening out the patch's colour into the holes in her layer (see meet)
REDRAW_SAY = "{change} Keep everything else exactly the same, including the plain {background} background."
# redraw --behind: the flat colour her layer is shown on, the one of these furthest from all of its own
# colours. The model draws her layer's edge against it, and how far a pixel it gives back is from it is
# how solid it is there (grey is too near a dark outline to tell them apart).
KEYS = {"magenta": (1.0, 0.0, 1.0), "green": (0.0, 1.0, 0.0), "blue": (0.0, 0.0, 1.0)}
REDRAW_CHANGE = ("Remove the stray dark lines, seams and narrow gaps across it, and fill them in with the same "
                 "colour and soft shading as round them.")

# Layers the rig shows only with her eyes shut, her mouth open or her cheeks flushed (parts.py
# makes them): the drawing has her eyes open, mouth shut and no blush, so check and repair leave
# these out.
SHUT = {"eye_close", "eye_close2", "mouth_open", "mouth_oh", "mouth_pout", "blush",
        "fx_sweat", "fx_anger", "fx_tears", "fx_sparkle_l", "fx_sparkle_r", "fx_gloom"}  # fx.py's marks, if she has her own


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


def psd_layers(name, info, wanted):
    """These whole-body layers as See-through painted them, from the PSD kept in her layers folder,
    at her frame's size: {layer: rgba}. A layer it hasn't is left out."""
    from psd_tools import PSDImage
    psd = PSDImage.open(os.path.join(folder(name), info["from"]))
    own = {}
    for layer in psd:
        if layer.name in wanted and layer.topil() is not None:
            full = Image.new("RGBA", (psd.width, psd.height))
            full.paste(layer.topil().convert("RGBA"), (layer.left, layer.top))
            own[layer.name] = resize_rgba(np.asarray(full, np.float32) / 255, tuple(info["frame"]))
    return own


def qwen_box(region):
    """The box of her frame qwen_fill sends for this region: ((x0, y0, x1, y1), (y0, x0, y1, x1))."""
    H, W = region.shape
    ys, xs = np.nonzero(region)
    pad = round(REDRAW_PAD * H)
    x0, x1, y0, y1 = max(xs.min() - pad, 0), min(xs.max() + pad + 1, W), max(ys.min() - pad, 0), min(ys.max() + pad + 1, H)
    return (x0, y0, x1, y1), (y0, x0, y1, x1)


def qwen_fill(picture, region, keep, change, seed, background="grey"):
    """Qwen Image 2.1's edit on a picture of her layer (her frame's size, on a flat colour), drawing
    again only the region given. Returns the picture with that part drawn, and the box it was
    cut from (x0, y0, x1, y1); what it sent and got is saved in keep."""
    import draw
    (x0, y0, x1, y1), _ = qwen_box(region)
    cw, ch = x1 - x0, y1 - y0
    k = REDRAW_SIZE / (cw * ch) ** 0.5
    size = (max(32, round(cw * k / 32) * 32), max(32, round(ch * k / 32) * 32))
    # Its alpha marks what may change (ComfyUI's LoadImage gives 1 - alpha as the mask), a few
    # pixels wider than what is kept, so what is kept meets what the model drew round it. Colour
    # and mask are resized apart: PIL resizes RGBA premultiplied, which blacks out the colour under
    # a clear pixel, and the model then draws black there (2026-11-25).
    may = ~ndimage.binary_dilation(region, iterations=3)[y0:y1, x0:x1]
    src = Image.fromarray((np.clip(picture[y0:y1, x0:x1], 0, 1) * 255).round().astype(np.uint8), "RGB").resize(size, Image.LANCZOS)
    src.putalpha(Image.fromarray(may.astype(np.uint8) * 255, "L").resize(size, Image.LANCZOS))
    src.save(os.path.join(keep, "sent.png"))
    # The edit starts from the picture itself under a noise mask: only the masked part is drawn
    # again, the rest is held as it is. (The latent the edit node gives is an empty one of the
    # picture's size: masked, that drew black.)
    prompt = REDRAW_SAY.format(change=change or REDRAW_CHANGE, background=background)
    wf, extra = draw.workflow(prompt, seed, size, source=os.path.join(keep, "sent.png"))
    wf["13"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["11", 0], "vae": ["3", 0]}}
    wf["12"] = {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["13", 0], "mask": ["11", 1]}}
    wf["6"]["inputs"]["latent_image"] = ["12", 0]
    print(f"  sent as {size[0]}x{size[1]}; prompt: {prompt}", flush=True)
    png = draw.Local().picture(wf, extra, "redraw")
    open(os.path.join(keep, "got.png"), "wb").write(png)
    out = picture.copy()
    out[y0:y1, x0:x1] = np.asarray(Image.open(io.BytesIO(png)).convert("RGB").resize((cw, ch), Image.LANCZOS), np.float32) / 255
    return out, (x0, y0, x1, y1)


def do_redraw(name, layer, overs, change, seed):
    info = load(name)
    for x in [layer] + overs:
        if x not in info["order"]:
            sys.exit(f"{x}: no such layer; there are {', '.join(info['order'])}")
        if x != layer and info["order"].index(x) < info["order"].index(layer):
            sys.exit(f"{x} is below {layer}: redraw is for what the layers over it hide")
    if layer in load_sharp(name):
        sys.exit(f"{layer} came from the head pass and has a sharp copy: redraw is for her whole-body layers")
    im = read_part(name, layer)
    H, W = im.shape[:2]
    a = im[..., 3]
    cover = np.zeros((H, W), bool)
    for x in overs:
        cover |= read_part(name, x)[..., 3] > SOLID
    solid = a > SOLID
    reach = max(2, round(REDRAW_BAND * H))
    # What to redraw: what the layers over it hide of it, and a band round that, where scale coloured
    # the drawing's line along their edge into it. See-through also cuts thin slits out of a layer
    # along such a line, which show the background through it: those are filled, and become part of it.
    near = ndimage.distance_transform_edt(~cover) <= reach
    shut = ndimage.binary_closing(np.pad(solid, 2 * reach), iterations=max(1, reach // 2))[2 * reach:-2 * reach, 2 * reach:-2 * reach]
    holes = (ndimage.binary_fill_holes(solid) | shut) & ~solid & ndimage.binary_dilation(cover, iterations=reach)
    mine = solid | holes
    region = ndimage.binary_opening(near & mine, iterations=1) | holes
    if region.sum() < SPOT:
        sys.exit(f"{', '.join(overs)} hide{'s' if len(overs) == 1 else ''} nothing of {layer}: nothing to redraw")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    keep = kit.out("redraw", f"{slug(name)}-{layer.replace(' ', '-')}-{stamp}")
    os.makedirs(keep, exist_ok=True)
    before = os.path.join(keep, "before.png")
    Image.fromarray(np.clip(im * 255, 0, 255).round().astype(np.uint8), "RGBA").save(before)
    for o in overs:  # their edges may change too (below)
        shutil.copyfile(part_path(name, o), os.path.join(keep, f"{o} before.png"))
    shown = np.where(mine, 1.0, a)[..., None]
    print(f"{name}: redrawing {layer} under {', '.join(overs)}: {int(region.sum())} px, seed {seed}", flush=True)
    got, (x0, y0, x1, y1) = qwen_fill(im[..., :3] * shown + REDRAW_GREY * (1 - shown), region, keep, change, seed)
    got = got[y0:y1, x0:x1]
    # Only the part found is kept, its edge feathered over a pixel. Its alpha is her layer's own
    # (so the background round her stays clear), solid inside it, where the gaps and their soft
    # rims were.
    soft = np.maximum(ndimage.gaussian_filter(region.astype(np.float32), 1.0), region)[y0:y1, x0:x1, None]
    new = im.copy()
    new[y0:y1, x0:x1, :3] = got * soft + im[y0:y1, x0:x1, :3] * (1 - soft)
    new[..., 3] = np.where(ndimage.binary_erosion(mine, iterations=1) & region, 1.0, a)
    write_part(name, layer, new)
    # As she stands she stays the drawing. The band held the outer half of the line along the edge of
    # what lies over her layer (scale coloured it in there, under that layer's soft edge); redrawn, the
    # line came out thinner at rest (924 px of one character's hair outline, 2026-11-25). That half now
    # goes with the layer it belongs to: its soft edge there is given its own colour (its nearest solid
    # pixel's) at the alpha that puts it over what is now below back to the drawing's colour. So the
    # line swings with the hair or the skirt, and nothing is left behind on her layer.
    orig, _ = drawing(name, info["frame"])
    shown = [x for x in info["order"] if x not in SHUT]
    stack = [[x, new if x == layer else read_part(name, x)] for x in shown]
    edged, sharp = [], load_sharp(name)
    for o in sorted(overs, key=shown.index):
        if o in sharp:  # editing a head-pass layer would switch off its sharp copy: its line stays where it is
            print(f"  {o} came from the head pass: the outer half of its line stays on {layer}")
            continue
        i = shown.index(o)
        ov = stack[i][1]
        solid_o = ov[..., 3] > SOLID
        dist, (iy, ix) = ndimage.distance_transform_edt(~solid_o, return_indices=True)
        band = region & ~cover & (dist > 0) & (dist <= 2 * reach)
        if not band.any():
            continue
        below, _ = composite(stack[:i])
        mine_c = ov[..., :3][iy, ix]
        step = mine_c - below
        alpha = np.clip(((orig - below) * step).sum(axis=2) / np.maximum((step ** 2).sum(axis=2), 1e-6), 0, 1)
        more = band & (alpha > ov[..., 3]) & (np.abs(step).max(axis=2) > MATCH)
        if more.any():
            ov[..., :3][more] = mine_c[more]
            ov[..., 3][more] = alpha[more]
            stack[i][1] = ov
            write_part(name, o, ov)
            edged.append(f"{o}'s edge ({int(more.sum())} px)")

    def on_grey(x):
        return x[..., :3] * x[..., 3:] + REDRAW_GREY * (1 - x[..., 3:])
    Image.fromarray((np.clip(np.concatenate([on_grey(im)[y0:y1, x0:x1], on_grey(new)[y0:y1, x0:x1]], axis=1), 0, 1) * 255)
                    .astype(np.uint8)).save(os.path.join(keep, "compare.png"))
    note(info, f"{layer} redrawn under {', '.join(overs)} with Qwen Image 2.1, seed {seed} ({int(region.sum())} px): "
               f"\"{change or REDRAW_CHANGE}\"" + (f"; the line along it moved onto {', '.join(edged)}" if edged else "")
               + f"; as it was: {os.path.relpath(before, ROOT)}")
    save(name, info)
    print(f"{name}: {layer} redrawn ({int(region.sum())} px)" + (f", the line along it moved onto {', '.join(edged)}" if edged else "")
          + f". Before and after: {os.path.join(keep, 'compare.png')}; "
          f"the layers as they were: {keep} (before.png is {layer}; copy them back into {os.path.dirname(part_path(name, layer))} "
          f"to undo). Then `build`")


def meet(colour, over, where):
    """The patch's colour where her layer (over) doesn't cover it, evened out so it meets her layer's
    colour all round each hole: the model's drawing kept, its difference from her layer at the hole's
    edge carried smoothly across the hole (a seamless clone). The model drew the shading round a gap
    lighter than the drawing has it, and the gap's shape showed in it (2026-11-25)."""
    hole = where & (over[..., 3] < 0.98)
    rim = ndimage.binary_dilation(hole) & ~hole & (over[..., 3] >= 0.98)
    if not hole.any() or not rim.any():
        return colour
    ys, xs = np.nonzero(ndimage.binary_dilation(hole, iterations=2))
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    h, r = hole[y0:y1, x0:x1], rim[y0:y1, x0:x1]
    diff = np.zeros((y1 - y0, x1 - x0, 3), np.float32)
    diff[r] = (over[y0:y1, x0:x1, :3] - colour[y0:y1, x0:x1])[r]
    known = (h | r).astype(np.float32)
    for _ in range(BEHIND_EVEN):  # each hole pixel the mean of its neighbours that are in a hole or on its rim
        total = np.zeros_like(diff)
        count = np.zeros(h.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            total += np.roll(diff * known[..., None], (dy, dx), axis=(0, 1))
            count += np.roll(known, (dy, dx), axis=(0, 1))
        diff[h] = (total / np.maximum(count, 1)[..., None])[h]
    out = colour.copy()
    out[y0:y1, x0:x1][h] = np.clip(colour[y0:y1, x0:x1] + diff, 0, 1)[h]
    return out


def do_behind(name, layer, below, change, seed):
    info = load(name)
    order = info["order"]
    for x in (layer, below):
        if x not in order:
            sys.exit(f"{x}: no such layer; there are {', '.join(order)}")
    if order.index(below) > order.index(layer):
        sys.exit(f"{below} is over {layer}: --behind is for a layer under it that shows through it")
    sharp = load_sharp(name)
    for x in (layer, below):
        if x in sharp:
            sys.exit(f"{x} came from the head pass and has a sharp copy: --behind is for her whole-body layers")
    patch_name = f"{layer} behind {below}"
    if patch_name in order:
        sys.exit(f"she already has {patch_name}: put back the layers kept in <out>/redraw/ and remove it "
                 f"(`layers remove {name} \"{patch_name}\" \"...\"`) before drawing it again")
    im, un = read_part(name, layer), read_part(name, below)
    H, W = im.shape[:2]
    a = im[..., 3]
    solid = a > SOLID
    # The gaps: where the layer below shows through hers as she stands, cut into her layer's edge
    # (her sleeve lies over her top there, so repair cut her top away). Narrow cuts only: a gap
    # wider than the closing is her layer's own shape (a cardigan's open front).
    r = max(2, round(BEHIND_CLOSE * H))
    closed = ndimage.binary_fill_holes(ndimage.binary_closing(np.pad(solid, 3 * r), iterations=r)[3 * r:-3 * r, 3 * r:-3 * r])
    gaps = big(closed & ~solid & (un[..., 3] > SOLID))
    if not gaps.any():
        sys.exit(f"nothing of {below} shows through {layer} as she stands: no gaps to fill")
    own = psd_layers(name, info, [layer]).get(layer)
    if own is None:
        sys.exit(f"{info['from']} has no {layer} layer to start the gaps from")
    # Drawn: the gaps and a ring of her layer round them, together, so the patch blends with it, and
    # out over the layer below there: See-through never drew her layer's edge where that one lay over
    # it, and left it ragged. The model draws that edge against a flat key colour, starting from
    # See-through's own colour in the gaps (what repair cut away).
    under = un[..., 3] > SOLID
    ring = max(1, round(BEHIND_RING * H))
    region = ndimage.binary_dilation(gaps, iterations=ring) & (closed | under)
    start = im.copy()
    start[gaps] = own[gaps]
    colours = im[..., :3][solid][::max(1, int(solid.sum()) // 20000)]
    key_name = max(KEYS, key=lambda k: np.percentile(np.abs(colours - KEYS[k]).max(axis=1), 2))
    key = np.array(KEYS[key_name], np.float32)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    keep = kit.out("redraw", f"{slug(name)}-{layer.replace(' ', '-')}-behind-{stamp}")
    os.makedirs(keep, exist_ok=True)
    for x in (layer, below):
        shutil.copyfile(part_path(name, x), os.path.join(keep, f"{x} before.png"))
    print(f"{name}: drawing {layer} behind {below}: {int(gaps.sum())} px of gaps, {int(region.sum())} px drawn on "
          f"{key_name}, seed {seed}", flush=True)
    sa = start[..., 3:]
    got, _ = qwen_fill(start[..., :3] * sa + key * (1 - sa), region, keep, change, seed, key_name)
    # How solid each pixel the model drew is: how far it is from the key, between how far the key it
    # kept round her strays (its noise) and how far her layer's own colours are (all but the nearest
    # few). A pixel that isn't solid takes the colour of the nearest one that is: its own colour, with
    # the key mixed in, left a coloured fringe along her edge.
    d = np.abs(got - key).max(axis=2)
    bare = ~ndimage.binary_dilation(region, iterations=4) & (start[..., 3] < SEAM_FAINT)
    _, (cy0, cx0, cy1, cx1) = qwen_box(region)
    bare[:cy0], bare[cy1:], bare[:, :cx0], bare[:, cx1:] = False, False, False, False
    floor = np.percentile(d[bare], 99) if bare.any() else 0.0
    far = np.percentile(np.abs(colours - key).max(axis=1), 2)
    drawn_a = np.clip((d - floor) / max(far - floor, 1e-3), 0, 1)
    # Along her edge the key shows through what the model drew: there, no channel the key has more
    # of than the others is let stand above the others (a green key: green no higher than red or blue).
    edge = ndimage.binary_dilation(drawn_a < 0.98, iterations=2) & (drawn_a > 0)
    hot, cold = [c for c in range(3) if key[c] > 0.5], [c for c in range(3) if key[c] <= 0.5]
    if cold:
        top_cold = got[..., cold].max(axis=2)
        for c in hot:
            got[..., c] = np.where(edge, np.minimum(got[..., c], top_cold), got[..., c])
    # The patch: that part as a layer of its own, just under the layer below. It is hidden at rest
    # (under her layer, and in the gaps under the layer below), and there when that one moves away.
    patch = np.zeros_like(im)
    patch[..., :3] = got
    patch[..., 3] = np.where(region, np.maximum(drawn_a, ndimage.binary_erosion(solid).astype(np.float32)), 0)
    # Her layer's pixels outside the edge the model drew, over the layer below (her ragged edge
    # there), and her rim along each gap (scale coloured the line of the layer below into it), are
    # that layer's in the drawing: they would stay on her when it moved. They go, and it takes them.
    rim = (solid & under & ndimage.binary_dilation(gaps, iterations=max(1, round(BEHIND_RIM * H)))
           & (np.abs(im[..., :3] - got).max(axis=2) > MATCH))
    rim |= (a > 0) & ((region & under & (drawn_a < SOLID)) | gaps)  # and what little of her the gaps held
    new = im.copy()
    new[..., 3][rim] = 0
    patch[..., :3] = meet(patch[..., :3], new, region & (patch[..., 3] > 0))
    # As she stands she stays as she was: where what is under the layer below now differs (the
    # patch under a soft edge of it, her rim gone), the layer below takes the colour, and if needed
    # the alpha, that puts it back.
    shown = [x for x in order if x not in SHUT]
    old = {x: read_part(name, x) for x in shown}
    old_stack = [[x, old[x]] for x in shown]
    j, li = shown.index(below), shown.index(layer)
    target = np.where(rim[..., None], composite(old_stack[:li + 1])[0], composite(old_stack[:j + 1])[0])
    parts = {**old, layer: new, patch_name: patch}
    new_shown = shown[:j] + [patch_name] + shown[j:]
    under_c, _ = composite([[x, parts[x]] for x in new_shown[:j + 1]])
    now, _ = composite([[x, parts[x]] for x in new_shown[:j + 2]])
    fix = (ndimage.binary_dilation(region, iterations=2) & (np.abs(now - target).max(axis=2) > 0.01)) | rim
    # Only where she is in the drawing: See-through's ragged edge also reached into the background
    # between her arm and her side, coloured like it, and the layer below took that as grey scraps that
    # hung under her arms once they moved (2026-11-25). There it is cleared, and given to nothing.
    _, her = drawing(name, info["frame"])
    fix &= her
    # ...and only where the layer below is what shows: under her layer, or anything else over it, the
    # patch changes nothing as she stands, and a colour put there would show once the layer below moved.
    above = np.zeros((H, W), np.float32)
    for x in new_shown[j + 2:]:
        above = np.maximum(above, parts[x][..., 3])
    fix &= above < SEAM_FAINT
    ua = un[..., 3]
    firm = fix & (ua > SOLID)
    un[..., :3][firm] = np.clip((target - (1 - ua[..., None]) * under_c) / np.maximum(ua[..., None], 1e-3), 0, 1)[firm]
    dist, (iy, ix) = ndimage.distance_transform_edt(~(ua > SOLID), return_indices=True)
    its = un[..., :3][iy, ix]
    step = its - under_c
    alpha = np.clip(((target - under_c) * step).sum(axis=2) / np.maximum((step ** 2).sum(axis=2), 1e-6), 0, 1)
    soft = fix & ~firm & (alpha > ua)
    # ...only where its own colour can make the drawing's there: elsewhere it would add a scrap of
    # another colour (a sleeve's lavender in place of a jacket's olive, 2026-11-25).
    soft &= np.abs(alpha[..., None] * its + (1 - alpha[..., None]) * under_c - target).max(axis=2) <= MATCH
    un[..., :3][soft] = its[soft]
    un[..., 3][soft] = alpha[soft]
    parts[below] = un
    after, _ = composite([[x, parts[x]] for x in new_shown])
    moved = int((np.abs(after - composite(old_stack)[0]).max(axis=2) > 0.02).sum())
    write_part(name, layer, new)
    write_part(name, below, un)
    write_part(name, patch_name, patch)
    order.insert(order.index(below), patch_name)
    info.setdefault("moves_with", {})[patch_name] = layer

    def on_grey(x):
        return x[..., :3] * x[..., 3:] + REDRAW_GREY * (1 - x[..., 3:])
    shows, _ = composite([[patch_name, patch], [layer, new]])  # what shows once the layer below moves away
    ys, xs = np.nonzero(region)
    pad = round(REDRAW_PAD * H)
    y0, y1, x0, x1 = max(ys.min() - pad, 0), ys.max() + pad, max(xs.min() - pad, 0), xs.max() + pad
    both = np.dstack([shows, np.maximum(new[..., 3], patch[..., 3])])
    two = np.concatenate([on_grey(im)[y0:y1, x0:x1], on_grey(both)[y0:y1, x0:x1]], axis=1)
    Image.fromarray((np.clip(two, 0, 1) * 255).astype(np.uint8)).save(os.path.join(keep, "compare.png"))
    note(info, f"{patch_name}: the gaps in {layer} where {below} shows through ({int(gaps.sum())} px), drawn with "
               f"Qwen Image 2.1, seed {seed}, \"{change or REDRAW_CHANGE}\"; it moves with {layer}. {int(rim.sum())} px of "
               f"{layer}'s rim went to {below}; as they were: {os.path.relpath(keep, ROOT)}")
    save(name, info)
    print(f"{name}: {patch_name} added under {below} ({int((patch[..., 3] > 0).sum())} px); {int(rim.sum())} px of {layer}'s "
          f"rim went to {below}; as she stands, {moved} px changed. Before and after (with {below} moved away): "
          f"{os.path.join(keep, 'compare.png')}; the layers as they were: {keep}. Then `build`: it moves {patch_name} "
          f"with {layer}")


def alien(mask, orig, mine, reach):
    """The pixels of mask whose drawn colour See-through painted nowhere on this layer (mine) within
    reach: another part's colour, not a shade of its own it put a little to one side."""
    from scipy.spatial import cKDTree
    out = np.zeros_like(mask)
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return out
    y0, x0 = max(ys.min() - reach, 0), max(xs.min() - reach, 0)
    box = mine[y0:ys.max() + reach + 1, x0:xs.max() + reach + 1]
    oy, ox = np.nonzero(box[..., 3] > SOLID)
    if not len(oy):
        out[ys, xs] = True
        return out
    # One distance for both: a step of reach in place counts as much as DIFF in colour.
    s = DIFF / reach
    tree = cKDTree(np.column_stack([(oy + y0) * s, (ox + x0) * s, box[oy, ox, :3]]))
    d, _ = tree.query(np.column_stack([ys * s, xs * s, orig[ys, xs]]), p=np.inf, distance_upper_bound=DIFF)
    far = np.isinf(d)
    out[ys[far], xs[far]] = True
    return out


def do_seams(name):
    info = load(name)
    W, H = info["frame"]
    shown = [layer for layer in info["order"] if layer not in SHUT]
    if "face" not in shown:
        sys.exit("she has no face layer: seams is for after the head pass")
    stack = [[layer, read_part(name, layer)] for layer in shown]
    orig, _ = drawing(name, info["frame"])
    # Layers the head pass gave weren't coloured by scale; editing one would also switch off its sharp copy.
    taken = set(load_sharp(name))
    if not taken:  # head layers taken before the kit kept sharp copies: the head step's note names them
        for text in info.get("changes", []):
            if "head layers from" in text:
                taken = {t.strip() for t in text.split("): ", 1)[-1].split(";")[0].split(",")}
    own = psd_layers(name, info, [x for x in shown if x not in taken])  # as See-through painted them
    face = shown.index("face")
    neck = shown.index("neck") if "neck" in shown else -1
    done = []

    # 0. A bit of a whole-body layer lying apart from the rest of it, mostly under her face: See-through's
    # collar or shirt painted under her chin, coloured by scale. Her face hides most of it at rest, and
    # it floats there when her head lifts or turns. It is cleared (2026-11-25, on two characters; the
    # few pixels of it that showed below her chin were a darker edge than the drawing's line).
    under_face = stack[face][1][..., 3] > SOLID
    for i in range(face):
        layer, im = stack[i]
        if layer not in own or layer == "neck":
            continue
        pieces, n = ndimage.label(im[..., 3] > SEAM_FAINT, structure=np.ones((3, 3)))
        if n < 2:
            continue
        sizes = ndimage.sum(np.ones((H, W)), pieces, range(1, n + 1))
        under = ndimage.mean(under_face, pieces, range(1, n + 1))
        loose = np.isin(pieces, 1 + np.flatnonzero((under > 0.5) & (sizes < sizes.max())))
        if loose.any():
            im[..., 3][loose] = 0
            write_part(name, layer, im)
            done.append(f"{layer}: a loose bit under her face cleared ({int(loose.sum())} px)")

    # 1. Round her face. scale coloured each layer from the drawing wherever it was on top, and the
    # whole-body face was a little smaller than the drawing's: her jaw line and a sliver of neck went
    # onto her back hair (and bits of chin onto her clothes). The head pass's face hides most of it
    # at rest; it shows when her head lifts or her hair sways. Only her face counts here: counting
    # every head layer reached her front hair where it hangs over her shirt, and painted the line
    # along a strand there in her shirt's colour (2026-11-24). Her neck itself is left as it is: the
    # drawing's colours on it looked better than any touching up of them did.
    fa = stack[face][1][..., 3]
    near = ndimage.distance_transform_edt(fa <= SEAM_FAINT) <= round(SEAM_NEAR * H)
    hidden, soft_face = fa > SOLID, fa > SEAM_FAINT
    # Her face's soft edge, and how far the drawing is from the colour of her face just inside it (its line).
    dist, (iy, ix) = ndimage.distance_transform_edt(fa <= SOLID, return_indices=True)
    face_soft = soft_face & (dist > 0) & (dist <= round(SEAM_EDGE * H))
    face_line = np.abs(stack[face][1][..., :3][iy, ix] - orig).max(axis=2)
    for i in range(face):  # bottom up: a layer cleared first shows what is below the next
        layer, im = stack[i]
        if layer not in own or layer == "neck":
            continue
        mine = own[layer]
        a = im[..., 3]
        # What scale coloured: solid pixels it found on top, still the drawing's colour.
        painted = (a > SOLID) & (np.abs(im[..., :3] - orig).max(axis=2) < SEAM_SAME)
        # The drawing's colour of something else, round her face: far from what See-through painted this layer.
        foreign = (painted & near & (mine[..., 3] > SEAM_FAINT)
                   & (np.abs(mine[..., :3] - orig).max(axis=2) > DIFF))
        # Hair kept from the whole-body pass that lies above her neck in the order (her braid in
        # front of her coat took her back hair up with it): under her face it would cover her neck
        # as soon as her hair swings, where the drawing never shows it. Cleared over her neck.
        over_neck = np.zeros((H, W), bool)
        if layer in HEAD and 0 <= neck < i:
            over_neck = (stack[neck][1][..., 3] > SOLID) & hidden & (a > SEAM_FAINT)
        face_edge = painted & face_soft
        if not foreign.any() and not over_neck.any() and not face_edge.any():
            continue
        below, under_top = composite(stack[:i]) if i else (np.ones_like(orig), np.full((H, W), -1, np.int16))
        lower = under_top >= 0
        lower_shows = lower & (np.abs(below - orig).max(axis=2) < MATCH)
        # Cleared under her face's soft edge (the jaw line there is the head pass's own now).
        erase = foreign & ~hidden & lower & soft_face
        # And where the layer below is what the drawing shows, if it is another part's colour: one
        # See-through painted nowhere on this layer close by (skin on her hair). Skin over skin
        # stays: clearing it gained nothing, and cut a shirt that runs up under her chin into
        # ragged bits the build then dyed with her collar's colour (2026-11-24).
        loose = foreign & ~hidden & lower_shows & ~erase
        erase |= loose & alien(loose, orig, mine, round(SEAM_NEAR * H))
        # Her face's own edge coloured onto a layer under it, whatever See-through put there: under
        # her face's soft edge, where the drawing is nearer her face's line just inside it than what
        # is below this layer. The head pass's face draws that line. The tip of her chin line, on a
        # shirt whose own collar edge See-through drew dark at that very spot, stayed as a dark
        # speck just under her chin (2026-11-24).
        erase |= face_edge & ~hidden & lower & (face_line < np.abs(below - orig).max(axis=2))
        erase |= over_neck
        # Its own colour back under her face where it isn't cleared: hidden at rest, it shows as
        # her head moves.
        repaint = foreign & ~erase & soft_face
        if repaint.any():
            # See-through's colours are a little off the drawing's: shaded by how far they are
            # where this layer shows, close by, so the repainted part runs on from it.
            _, top = composite(stack)
            ring = (top == i) & painted & ~foreign & ndimage.binary_dilation(repaint, iterations=round(SEAM_NEAR * H))
            shift = np.median((orig - mine[..., :3])[ring], axis=0) if ring.sum() > SPOT else np.zeros(3)
            im[..., :3][repaint] = np.clip(mine[..., :3] + shift, 0, 1)[repaint]
        # The soft rim round what's cleared goes with it, as in repair, or a faint line would stay.
        erase |= ndimage.binary_dilation(erase, iterations=2) & (a <= SOLID) & lower
        im[..., 3][erase] = 0
        stack[i][1] = im
        if erase.any() or repaint.any():
            write_part(name, layer, im)
            done.append(f"{layer} round her face ({int(erase.sum())} px cleared, {int(repaint.sum())} given its own colour)")

    # 2. The seam over her neck. scale gave the drawing's colour only where a layer is solid; its
    # soft edge kept See-through's, often darker. Where a layer's edge crosses her neck and the
    # drawing runs on through it (skin into skin: her shirt's top edge) that left a faint line the
    # drawing doesn't have. Only over her neck: elsewhere the edges were never seen to need it.
    reach = round(SEAM_EDGE * H)
    _, top = composite(stack)
    below, under_top = np.ones_like(orig), np.full((H, W), -1, np.int16)
    for i, (layer, im) in enumerate(stack):
        if layer in own and 0 <= neck < i:
            a = im[..., 3]
            soft = (a > SEAM_FAINT) & (a <= SOLID) & (under_top == neck) & (top == neck)
            solid = top == i
            if soft.any() and solid.any():
                dist, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
                inner = im[..., :3][iy, ix]  # the layer's own colour just inside its edge
                fix = (soft & (dist <= reach) & (np.abs(inner - orig).max(axis=2) < MATCH)
                       & (np.abs(below - orig).max(axis=2) < MATCH) & (np.abs(im[..., :3] - orig).max(axis=2) >= SEAM_SAME))
                if fix.any():
                    im[..., :3][fix] = orig[fix]
                    write_part(name, layer, im)
                    done.append(f"{layer} edge over her neck ({int(fix.sum())} px)")
        # What's below the next layer up.
        al = im[..., 3:4]
        below = im[..., :3] * al + below * (1 - al)
        under_top = np.where(im[..., 3] > SOLID, i, under_top).astype(np.int16)

    if done:
        note(info, "seams: " + ", ".join(done))
        save(name, info)
    print(f"{name}: " + ("; ".join(done) if done else "no seams to put right"))


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
SHARP_SAME = kit.SHARP_SAME  # sharp: a head layer this close to the head pass's (0 to 1, on average) is as it was taken


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
    seen = set()
    for layer in psd:
        if layer.name not in HEAD:
            continue
        seen.add(layer.name)
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
    # A head name the PSD simply lacks used to pass in silence, leaving her face at the whole-body
    # pass's size while the step said nothing (a run of this kit, 2026-11-19). Name it.
    absent = sorted({("mouth" if t == "mouth_close" else t) for t in order
                     if ("mouth" if t == "mouth_close" else t) in HEAD} - seen)
    if absent:
        print(f"  the head PSD has no {', '.join(absent)}: kept from the whole-body pass, so close up "
              f"{'it stays' if len(absent) == 1 else 'they stay'} at that pass's softness")
    if gone:
        print(f"  removed {', '.join(gone)}: run parts.py closed-eyes {name}, then parts.py mouth {name}")
    # Her face is the head pass's now, so what scale coloured round the old one can be put right:
    # her old jaw line on her hair, a seam across her neck (2026-11-24: on three characters, found
    # only once their heads moved).
    do_seams(name)


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
    elif cmd == "seams" and not rest:
        do_seams(name)
    elif cmd == "redraw" and len(rest) >= 3 and rest[1] == "--under":
        given = dict(zip(rest[3::2], rest[4::2]))
        if len(rest[3:]) % 2 or set(given) - {"--prompt", "--seed"}:
            sys.exit(__doc__)
        do_redraw(name, rest[0], [x.strip() for x in rest[2].split(",")], given.get("--prompt", ""), int(given.get("--seed", 1)))
    elif cmd == "redraw" and len(rest) >= 3 and rest[1] == "--behind":
        given = dict(zip(rest[3::2], rest[4::2]))
        if len(rest[3:]) % 2 or set(given) - {"--prompt", "--seed"}:
            sys.exit(__doc__)
        do_behind(name, rest[0], rest[2], given.get("--prompt", ""), int(given.get("--seed", 1)))
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
