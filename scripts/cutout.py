"""Transparent backgrounds for drawings: BiRefNet (ComfyUI's built-in background removal) on the
kit's ComfyUI makes the mask, then the edges are unmixed from the background colour so no fringe
shows on a dark or light room.

The background is whatever flat colour the picture has, measured from its border. White works, but
light hair fades into white in the drawing and leaves a white rim; a copy redrawn on flat grey
(an edit: "the background is a flat, solid, even medium grey") cuts out cleanly.

usage (`live2d.py cutout <name>` runs it on a character's drawing; by hand, with ComfyUI's own
Python, which has numpy, scipy and Pillow, and ComfyUI started):
  <comfyui python> -I cutout.py <in.png> <out.png> ...
Takes pairs of paths. An input written <grey.png>+<original.png> takes its shape and edges from the
redraw on grey (colours matched back, as it comes out a little darker) and keeps the original's own
pixels inside her, so a grainy redraw of an edit doesn't show. The model is birefnet.safetensors
(Hugging Face Comfy-Org/BiRefNet, MIT) in the models folder's background_removal/.
  ... cutout.py --tidy <in.png> <out.png> ...
tidies a picture drawn with its own transparency (no ComfyUI needed). Also writes <out>.mask.png into <out>/cutout/ for checking.
  cutout.py --own <in.png> <cutout.png> <drawing.png>
a character's drawing that came with its own transparency (`live2d.py pick` runs it): the tidied
picture is her cut-out, and the same on light grey is her drawing, as See-through and the layer
check see it (on white, See-through's layers came out a little less exact in a test, 2026-11-13). No ComfyUI needed. It stops with a message if the picture has no real transparency."""
import base64, io, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from scipy import ndimage
import comfy, kit

LOW, HIGH = 0.03, 0.97  # mask values below LOW are background, above HIGH solid
NEAR = 10               # a pixel within this of the background colour in every channel counts as background
GAP = 4000              # the largest background-coloured patch (in pixels) that can be a gap between strands
EDGE = 3                # pixels next to a cleared gap that get their alpha from their colour
RIM = 20                # with an original: near-white pixels this close to her edge come from the redraw
HAZE = 0.13             # --tidy: alpha below this is the haze a picture drawn with its own alpha leaves
SPECK = 0.02          # bits smaller than this share of her biggest piece are dropped


def mask(backend, path):
    wf = {
        "11": {"class_type": "LoadImage", "inputs": {"image": "src.png"}},
        "1": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}},
        "2": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["1", 0], "image": ["11", 0]}},
        "3": {"class_type": "MaskToImage", "inputs": {"mask": ["2", 0]}},
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "live2d-kit-mask", "images": ["3", 0]}},
    }
    extra = {"images": [{"name": "src.png", "image": base64.b64encode(open(path, "rb").read()).decode()}]}
    return Image.open(io.BytesIO(backend.picture(wf, extra, path, wait=300))).convert("L")


def background(rgb):
    """The flat background colour: the median of the picture's border."""
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    return np.median(border, axis=0)


def gaps(rgb, a, bg):
    """BiRefNet keeps the background between hair strands. Clear small enclosed background-coloured
    patches that it partly marked as background (white clothing on white joins the outer background
    or is bigger, so it stays), then give the edges next to them alpha from their colour: an edge
    pixel is its nearest solid colour F mixed with the background."""
    near = np.abs(rgb - bg).max(axis=2) <= NEAR
    labels, n = ndimage.label(near)
    outer = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    touching = np.unique(labels[ndimage.binary_dilation(a < 0.5) & near])
    sizes = ndimage.sum(np.ones(a.shape), labels, range(n + 1))
    ids = [t for t in touching if t > 0 and t not in outer and sizes[t] <= GAP]
    gap = np.isin(labels, ids) & (a > 0)
    if not gap.any():
        return a, gap
    a = np.where(gap, 0, a)
    dist = ndimage.distance_transform_edt(~gap)
    band = (dist > 0) & (dist <= EDGE) & (a > 0)
    solid = (dist > EDGE) & (a >= 1)
    _, (sy, sx) = ndimage.distance_transform_edt(~solid, return_indices=True)
    f = rgb[sy, sx] - bg
    c = rgb - bg
    norm = (f * f).sum(axis=2)
    est = np.clip((c * f).sum(axis=2) / np.maximum(norm, 1), 0, 1)
    a = np.where(band & (norm > 900), np.minimum(a, est), a)
    return a, gap


def specks(a):
    """Drop small bits apart from her: the drawn "z z z" (the house draws its own), stray marks."""
    labels, n = ndimage.label(a > 0.05, structure=np.ones((3, 3)))
    if n < 2:
        return a, np.zeros(a.shape, bool)
    sizes = ndimage.sum(np.ones(a.shape), labels, range(1, n + 1))
    small = np.isin(labels, 1 + np.flatnonzero(sizes < SPECK * sizes.max()))
    return np.where(small, 0, a), small


def match(f, a, ref):
    """A redraw on grey comes out a little darker: map each channel back to the original (the same
    picture on white, lined up to a few pixels) with a straight-line fit over her solid pixels."""
    ref = np.asarray(ref.convert("RGB").resize(f.shape[1::-1]), dtype=np.float32)
    solid = a >= 1
    out = f.copy()
    for ch in range(3):
        x = np.vstack([f[..., ch][solid], np.ones(solid.sum())]).T
        k, c = np.linalg.lstsq(x, ref[..., ch][solid], rcond=None)[0]
        out[..., ch] = f[..., ch] * k + c
    return out


def cutout(src, m, ref=None):
    """src on a flat background, m the mask: RGBA with the background unmixed from the soft edges,
    and the colours matched to ref when given."""
    rgb = np.asarray(src.convert("RGB"), dtype=np.float32)
    bg = background(rgb)
    a = np.asarray(m.resize(src.size, Image.LANCZOS), dtype=np.float32) / 255
    a = np.clip((a - LOW) / (HIGH - LOW), 0, 1)
    a, _ = gaps(rgb, a, bg)
    a, _ = specks(a)
    # A soft edge pixel is a*F + (1-a)*background; solve for F.
    soft = (a > 0) & (a < 1)
    f = rgb.copy()
    f[soft] = (rgb[soft] - (1 - a[soft, None]) * bg) / a[soft, None]
    if ref is not None:
        # The redraw gives the shape and the edges; inside, the original's own pixels are kept (a
        # redraw of an edit gets grainy), except near-white ones near the edge: the white rims.
        f = match(f, a, ref)
        orig = np.asarray(ref.convert("RGB").resize(src.size), dtype=np.float32)
        near_edge = ndimage.distance_transform_edt(a >= 1) <= RIM
        rim = (orig.min(axis=2) >= 235) & near_edge
        f = np.where(((a < 1) | rim)[..., None], f, orig)
    out = np.dstack([np.clip(f, 0, 255), a * 255]).round().astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def tidy(im):
    """A picture drawn with its own alpha (Qwen Image 2.1's VAE decodes RGBA when the prompt asks
    for a transparent background) has a faint haze over the background: clear it, drop specks."""
    rgba = np.asarray(im.convert("RGBA"), dtype=np.float32)
    a = np.clip((rgba[..., 3] / 255 - HAZE) / (1 - HAZE), 0, 1)
    a, _ = specks(a)
    return Image.fromarray(np.dstack([rgba[..., :3], a * 255]).round().astype(np.uint8), "RGBA")


GREY = (220, 220, 224)  # --own: her drawing goes on this, the light grey draw --background asks for
OWN = 0.6  # --own: the share of a picture's border that has to be clear for its transparency to be real


def own(src_path, cutout_path, drawing_path):
    im = Image.open(src_path)
    if im.mode != "RGBA":
        sys.exit(f"{src_path}: it has no alpha channel")
    a = np.asarray(im.getchannel("A"), dtype=np.float32) / 255
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    if (border < HAZE).mean() < OWN:
        sys.exit(f"{src_path}: its background isn't transparent ({(border < HAZE).mean():.0%} of its border is clear)")
    cut = tidy(im)
    cut.save(cutout_path, optimize=True)
    grey = Image.new("RGBA", cut.size, GREY + (255,))
    grey.alpha_composite(cut)
    grey.convert("RGB").save(drawing_path, optimize=True)
    solid = np.asarray(cut.getchannel("A")) > 127
    print(f"{cutout_path}: her cut-out, from the drawing's own transparency ({solid.mean():.0%} of the picture is her)")
    print(f"{drawing_path}: her drawing, on light grey")


def main(args):
    if args[:1] == ["--own"] and len(args) == 4:
        return own(*args[1:])
    if args[:1] == ["--tidy"]:
        for src_path, out_path in zip(args[1::2], args[2::2]):
            tidy(Image.open(src_path)).save(out_path, optimize=True)
            print(f"{out_path}: saved")
        return
    if not args or len(args) % 2:
        sys.exit(__doc__)
    backend = comfy.Local()
    check = kit.out("cutout")
    os.makedirs(check, exist_ok=True)
    for src_arg, out_path in zip(args[::2], args[1::2]):
        src_path, _, ref_path = src_arg.partition("+")
        m = mask(backend, src_path)
        m.save(os.path.join(check, os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(out_path)))) + "-" +
                            os.path.splitext(os.path.basename(out_path))[0] + ".mask.png"))
        cutout(Image.open(src_path), m, Image.open(ref_path) if ref_path else None).save(out_path, optimize=True)
        print(f"{out_path}: saved")


if __name__ == "__main__":
    main(sys.argv[1:])
