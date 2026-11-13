"""A character's layers as a Live2D model: her edited layers (<characters>/<name>/layers/, see
layers.py) rigged into a Cubism bundle that AIRI, Open-LLM-VTuber and other Cubism players load.

The first rig, its parts, meshes, physics and most motions come from image2live2d (Apache-2.0,
github.com/Wzhang3912/image2live2d), whose code this kit carries in vendor/image2live2d/: the files
its build path uses, as they were at commit 714e7cc (vendor/README.md). Nothing else of it has to
be installed. This script then rewrites how she moves and writes the .moc3 itself.

`live2d.py build <name>` runs it. By hand, with the Python the layer steps use (it needs numpy,
Pillow and pydantic):
  <python> -I rig.py build <name>

  build <name>
      her layers, named the way image2live2d reads them, into <out>/live2d/<name>/layers/; the
      bundle (model.moc3, model.model3.json, physics, motions, textures/atlas.png) into
      <out>/live2d/<name>/model/; an editable Cubism Editor project, <out>/live2d/<name>/<name>.cmo3
      (image2live2d's own rig, without what this script changes); and the bundle zipped for an
      app's model import, <out>/live2d/<name>.zip. Her expressions, emotion motions and taps are
      added, the same names for every character (see "Acting")

To look at her, use the kit's viewer (`live2d.py view`), which draws with the Cubism Core.

It is made for full-size, standing drawings: a whole figure seen from the front.

Our layers go in as they are, with three of them told apart from See-through's names:
- eye_close, the closed eyes drawn by parts.py, is image2live2d's closed eye (split into left and
  right), so it doesn't paint its own lash line;
- ears, both ears in one layer, is split into left and right;
- mouth_close is her mouth, and mouth_open, the open mouth parts.py draws, goes in as the mouth's
  inside (image2live2d's mouth_cavity), so it paints none of its own. Opening her mouth fades her
  closed line out and the drawn open mouth in, early, then grows it down to all of its height
  (see mouth_swap): image2live2d's own open pulls the lips apart in proportion to their height, and
  a drawn closed mouth is a line a few pixels high, so it hardly opened (2026-11-10).

Her stockinged legs (legwear) go in as two legs, so each knee can bend, and her lashes and closed
eyes go over her irises (see drawing_order).

Her blush is the kit's own (blush.py): her `blush` layer if parts.py made one, else style 1 drawn
here from her eyes, so image2live2d paints none. Its mesh covers all of it (see soft_mesh).

Her head's layers go into the model's texture at the head pass's own size where layers.py kept
them (see sharp_atlas): her frame holds them at about two fifths of it.

How she moves is ours, and so is the .moc3's writing (see "The rig" below): her head's turn and nod
(each part of her face sliding a little, her irises doing most of the looking), her irises cut off
at the edge of her eyes, her body's sway, bob, lean and breath with her feet on the floor, arms
that lift and bend at the elbow, and knees that bend.

<name> can be a character's other drawing, akane/working, as in layers.py."""
import importlib.util, json, math, os, shutil, sys, zipfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acting  # noqa: E402
import blush as blush_marks  # noqa: E402
import kit  # noqa: E402

VENDOR = os.path.join(kit.KIT, "vendor")
sys.path.insert(0, VENDOR)  # the kit's own copy of image2live2d, before any other that is installed
CHARS = kit.characters()
OUT = kit.out("live2d")

from image2live2d.backends.live2d import moc3_emit
from image2live2d.backends.nijilive.puppet import head_group_ids
from image2live2d.core import decompose
from image2live2d.core.decompose import sources
from image2live2d.core.mesh import build as mesh_build
from image2live2d.core.rig import author
from image2live2d.core.structure import strands
from image2live2d.irr.schema import Keyform, Parameter, SemanticRole
from image2live2d import pipeline
from image2live2d.pipeline import rig_from_stack

LEFT_OUT = set()
ROLES = {
    "eye_close": SemanticRole.eye_closed_l,
    "ears": SemanticRole.ear_l,
    "mouth_close": SemanticRole.mouth,
    "mouth_open": SemanticRole.mouth_cavity,
    "mouth_oh": SemanticRole.mouth_cavity,  # her "O" mouth (see mouth_shapes)
}
# Opening her mouth, as her eyes shut (see SQUINT): her closed line stays solid while her drawn open
# mouth starts as a slit hanging from its top edge, and the two swap over the first tenth of the
# way; from there the open mouth is solid and grows down to its full height, its top edge (her upper
# lip) still and the rest dropping, as a jaw does. The two used to crossfade over the whole way, so
# a mouth half open, as it mostly is in talk, was both half see-through, one over the other (first
# user, 2026-11-13).
MOUTH_SWAP = 0.1   # ParamMouthOpenY by which her open mouth has taken over from her closed line
SLIT = 0.12        # the open mouth's height then, as a share of its own (from 0.06 at 0)
_mouth_open = author._mouth_open


def mouth_swap(param_id, lips, cavity, open_fn):
    """ParamMouthOpenY as a swap (see MOUTH_SWAP)."""
    CAVITY[:] = cavity  # for mouth_form, which image2live2d calls next and gives the lips alone
    if not cavity:
        return _mouth_open(param_id, lips, cavity, open_fn)
    # Each open mouth (her "O" mouth too) hangs from its own top edge: the rig's y is up.
    hang = lambda m, share: author._collapse_to(m, 1 - share, max(y for _, y in m.vertices))
    keys = []
    for value, shut, share in ((0.0, 1.0, SLIT / 2), (MOUTH_SWAP, 0.0, SLIT), (1.0, 0.0, 1.0)):
        keys.append(Keyform(value=value,
                            mesh_offsets={**{pid: author._zeros(m) for pid, m in lips},
                                          **{pid: hang(m, share) if share < 1 else author._zeros(m) for pid, m in cavity}},
                            opacity_overrides={**{pid: shut for pid, _ in lips}, **{pid: 1 - shut for pid, _ in cavity}}))
    return author._set_keyforms(param_id, keys)


author._mouth_open = mouth_swap

# A smile or frown (ParamMouthForm) raises or lowers her open mouth's corners as much as her closed
# line's. image2live2d moved her closed line's alone, so a smile went flat as her mouth opened.
CAVITY = []
_mouth_form = author._mouth_form


def mouth_form(param_id, group, *, mouth_lm=None):
    param = _mouth_form(param_id, group, mouth_lm=mouth_lm)
    if not CAVITY or not group:
        return param
    if mouth_lm is not None:  # the same measures image2live2d took for her closed line
        cx, half, height = mouth_lm.center[0], max(mouth_lm.width / 2, 1e-6), max(mouth_lm.height, 1e-6)
    else:
        x0, y0, x1, y1 = author._bbox([v for _, m in group for v in m.vertices])
        cx, half, height = (x0 + x1) / 2, max((x1 - x0) / 2, 1e-6), y1 - y0
    for key in param.keyforms:
        sign = 0.0 if key.value == 0 else math.copysign(1.0, key.value)
        for pid, m in CAVITY:
            key.mesh_offsets[pid] = [(0.0, sign * min(author._MOUTH_FORM * height * min(abs(x - cx) / half, 1.2),
                                                       author._MOUTH_CAP)) for x, _ in m.vertices]
    return param


author._mouth_form = mouth_form

# Her hair in sections. image2live2d can swing a sheet of hair as several sections side by side,
# each on a pendulum of its own, blended across the sheet so it ripples and nothing tears. It
# sizes a section for a head that fills the picture (0.13 of the picture's width) and leaves the
# front hair out, so on a whole figure, whose head is a tenth of the picture, every sheet came out
# as one section: her bangs, the locks beside her face and both her tails swung as one board.
# Here a section is sized from her own face, and her front hair is sectioned too: the locks beside
# her face swing apart from her bangs, and one tail apart from the other.
HAIR_SECTION = 0.6   # a section's width, in face widths: a sheet narrower than two of them stays one
HAIR_SECTIONS = 4    # the most sections one sheet gets (each is one more parameter on its mesh)
FACE_WIDE = [None]   # her face's width as a share of the picture's, set when her layers are written
_column_count = strands._column_count


def hair_sections(width):
    """How many sections a sheet of hair this wide gets (the width as a share of the picture's)."""
    if not FACE_WIDE[0]:
        return _column_count(width)
    section = HAIR_SECTION * FACE_WIDE[0]
    return 1 if width < 2.0 * section else min(HAIR_SECTIONS, max(2, round(width / section)))


strands._column_count = hair_sections
strands._COLUMN_ROLES = (SemanticRole.hair_back, SemanticRole.hair_side, SemanticRole.hair_front)

_build_mesh = mesh_build.build_mesh


def whole_mesh(layer, *, grid=mesh_build.DEFAULT_GRID, alpha_threshold=mesh_build.DEFAULT_ALPHA_THRESHOLD, tighten=True):
    """A part's mesh with every cell that holds any of it. image2live2d's build_mesh (which this
    follows) keeps a cell of its lattice when one of nine points probed in it is on the part. A thin
    line passes between the points: a glasses rim came out with gaps in it, and thin strands of
    hair lost their tips. Here a cell is kept when any pixel in it is on the part."""
    import numpy as np
    with Image.open(layer.texture_path) as img:
        alpha = img.convert("RGBA").getchannel("A")
    width, height = alpha.size
    px = alpha.load()
    x0, y0, x1, y1 = layer.bbox  # in the picture, y down
    rect, uv = (x0, 1.0 - y1, x1, 1.0 - y0), mesh_build.FULL_UV  # in the model, y up
    if tighten:
        box = mesh_build.alpha_bbox(lambda x, y: px[x, y], width, height, alpha_threshold)
        if box is not None:
            uv = (box[0] / width, box[1] / height, (box[2] + 1) / width, (box[3] + 1) / height)
            rect = mesh_build._subrect(rect, uv)
    u0, v0, u1, v1 = uv
    solid = np.asarray(alpha)
    most = np.zeros((grid, grid), np.uint8)  # each cell's most solid pixel: [row from the top][column]
    for j in range(grid):
        ya, yb = int(np.floor((v0 + (v1 - v0) * j / grid) * height)), int(np.ceil((v0 + (v1 - v0) * (j + 1) / grid) * height))
        for i in range(grid):
            xa, xb = int(np.floor((u0 + (u1 - u0) * i / grid) * width)), int(np.ceil((u0 + (u1 - u0) * (i + 1) / grid) * width))
            cell = solid[max(ya, 0):yb, max(xa, 0):xb]
            most[j, i] = cell.max() if cell.size else 0

    def in_cell(u, v):
        i = min(grid - 1, max(0, int((u - u0) / max(u1 - u0, 1e-9) * grid)))
        j = min(grid - 1, max(0, int((v - v0) / max(v1 - v0, 1e-9) * grid)))
        return int(most[j, i])

    return mesh_build.grid_mesh(layer.id, rect, in_cell, grid=grid, uv_rect=uv, alpha_threshold=alpha_threshold)


def soft_mesh(layer, **how):
    """A blush's mesh over all of it. image2live2d lays a part's mesh over the box of its solid
    pixels (alpha 64 and up), which keeps a decomposer's stray specks out of it; a blush is soft all
    the way to nothing, so that box cut it off in a rectangle with hard edges (its first user, 2026-11-12:
    "cheeks have hard cut offs"). Its mesh here is a whole lattice over the box of everything the
    texture atlas keeps of it (alpha above 8), the same box the atlas cuts."""
    if layer.semantic_role is not SemanticRole.blush:
        return whole_mesh(layer, **how)
    with Image.open(layer.texture_path) as img:
        alpha = img.convert("RGBA").getchannel("A")
    box = alpha.point(lambda a: 255 if a > 8 else 0).getbbox()
    if not box:
        return _build_mesh(layer, **how)
    w, h = alpha.size
    uv = (box[0] / w, box[1] / h, box[2] / w, box[3] / h)
    x0, y0, x1, y1 = layer.bbox
    rect = mesh_build._subrect((x0, 1.0 - y1, x1, 1.0 - y0), uv)
    return mesh_build.grid_mesh(layer.id, rect, lambda u, v: 255, grid=how.get("grid", mesh_build.DEFAULT_GRID),
                                uv_rect=uv, alpha_threshold=1)


mesh_build.build_mesh = soft_mesh

# ---- The rig ---------------------------------------------------------------------------------
# image2live2d makes the rig (its parts, meshes, parameters, physics and motions) from the layers.
# Before the .moc3 is written we rewrite how she moves in it, and we write the .moc3 ourselves
# (rig_to_moc3 below, in place of image2live2d's own): its writer bakes every move into every part
# as straight-line moves of its points, which can't carry what follows. Ours puts her whole figure
# in one warp deformer for her body's moves, her head in a second one inside it for the tilt, cuts
# her irises off at the edge of her eyes' whites, and can change which part is in front as she moves.

# Head turn and nod: each part of her face slides by its own amount over a face and hair that
# hardly move. The idea, and the first amounts, are from a test of the first character
# in Cubism Editor (2026-11-10), measured there as shares of her face's width and
# height. At Cubism's own amounts (nose 0.195, mouth 0.124, eyes 0.114) a look down and to the left
# read as her face melting (the kit's first user, the same day): "These head movements are for looking at different
# things so the mouth and nose only need to give an illusion of a slight head turn, not a full
# turn. Its 2d not 3d". So the features now move about half as far, close to each other, and her
# irises do more of the looking (TURN_LOOK).
#   slide         how far the part moves at a full turn, in face widths
#   less          how much less it moves when it is on the side she turns to (and more on the other)
#   toward, away  its width when she turns to its side, and when she turns away from it
#   up, down      how far it moves at a full nod up and down, in face heights
TURNS = {
    #            slide  less   toward away  up     down
    "eye":     (0.055, 0.005, 0.95, 1.03, 0.034, 0.038),
    "brow":    (0.055, 0.004, 0.95, 1.03, 0.034, 0.040),
    "nose":    (0.060, 0.0, 1.0, 1.0, 0.036, 0.036),
    "mouth":   (0.045, 0.0, 1.0, 1.0, 0.028, 0.028),
    "ear":     (0.010, 0.005, 0.94, 1.04, 0.006, 0.006),
    "face":    (0.012, 0.0, 1.0, 1.0, 0.004, 0.006),
    # Glasses go with her eyes, narrowing as the gap between them does; blush sits on her cheek,
    # between face and eyes; bangs and things in her hair stay with the face under them. Her back
    # hair doesn't move.
    "glasses": (0.055, 0.0, 0.98, 0.98, 0.034, 0.038),
    "blush":   (0.040, 0.005, 0.95, 1.04, 0.024, 0.026),
    "hair":    (0.012, 0.0, 1.0, 1.0, 0.004, 0.006),
}
KINDS = {"eye_l": "eye", "eye_r": "eye", "eye_white_l": "eye", "eye_white_r": "eye", "pupil_l": "eye",
         "pupil_r": "eye", "eye_closed_l": "eye", "eye_closed_r": "eye", "eyebrow_l": "brow",
         "eyebrow_r": "brow", "mouth": "mouth", "mouth_cavity": "mouth", "nose": "nose", "ear_l": "ear",
         "ear_r": "ear", "face_base": "face", "blush": "blush", "hair_front": "hair", "hair_side": "hair",
         "accessory": "hair"}
# Her irises: a look (ParamEyeBallX/Y) slides them over her eyes' whites, both by the same amount so
# her eyes stay together. An iris drawn at the edge of its white has no room to go that way, so it
# may go part of the way out of the white, where it is cut off (the white is its clipping mask), the
# way an iris goes under the corner of an eye. image2live2d slid them with no cut-off: one character's left
# iris went onto her skin by her nose as she looked right, and the white it left "sat funny".
LOOK, LOOK_UP = 0.40, 0.22  # how far an iris goes at a full look, in iris widths, and in heights
HIDE, HIDE_UP = 0.20, 0.12  # how much of an iris may go out of its white
TURN_LOOK = 0.30  # how much of a full look her irises add by themselves at a full turn or nod
SMALL_IRIS = 0.62  # an iris's size at ParamEyeBallForm -1: the small irises of a fright
# Her lids: an eye shuts by its lashes and its white coming down onto the line of her closed eye,
# the white taking the iris with it (it is the iris's mask), all of it solid until the eye is
# nearly shut; only then does her drawn closed eye fade in over it. image2live2d fades the open eye
# out and the closed one in over the whole blink, so a half-shut eye was two see-through drawings
# over each other: fine in a blink, wrong for the heavy lids of "tired".
SQUINT = 0.2  # ParamEye?Open where her open eye is as shut as it gets before her closed eye shows
# Her smiling eyes (ParamEyeLSmile, ParamEyeRSmile), as Cubism's own models do them: with her eyes
# shut, the smile bends her drawn closed eye from its sag into an anime "^", its middle rising above
# its corners. With her eyes open it only narrows them a little, from below, as a cheek pushes up.
# image2live2d squashed the open eye (lashes, white and iris) onto an arch, so a smile showed the
# squashed iris colours under the lash line (first user, 2026-11-13: "the squeeze looks a bit weird
# and shows the squished eyes underneath"). The expressions that smile shut her eyes for it.
SMILE_BEND = 0.55  # how far the middle of her closed eye rises at a full smile, in eye heights
SMILE_OPEN = 0.5   # how far an open eye narrows at a full smile, from below, in eye heights
# The tilt: 12 degrees at the most, about a point just under her jaw. image2live2d tilts her 20
# degrees about the base of her neck, which swung her head half a head sideways, off her neck.
TILT = 0.21  # radians at a full ParamAngleZ
TILT_UNDER_JAW = 0.15  # how far under her jaw the point is, in face heights
# A nod moves her whole head too, hair and all, not only the features on it: with her face's outline
# still, a look down read as her features sliding down a mask (first user, 2026-11-12: "up/down look
# should move the entire head/hair up or down slightly too, like on a real person looking down moves
# the chin line down"). Her head's deformer carries it, so every part of her head goes together and
# her features' own slide (TURNS) comes on top. Hair that hangs below her chin goes less the lower
# it hangs, as with a straightened head (HANGS): hair on her shoulders stays on her shoulders.
NOD_UP, NOD_DOWN = 0.022, 0.032  # how far her head goes at a full ParamAngleY, in face heights

# Her body, standing: sway (ParamBodyAngleX), bob (ParamBodyAngleY), lean (ParamBodyAngleZ) and
# breath as one move of every point of her, by how high it is between her feet (0) and the base of
# her neck (1). Her feet stay on the floor, and no part can come away from the one next to it,
# because they all take the same move. image2live2d's own body moves are for a bust: the sway and
# bob slid all of her over the floor, the lean left her head behind, it swung her stockings and
# shoes as loose cloth (each on its own, so her legs left her feet), and a lifted arm dragged her
# skirt along (first user, 2026-11-10: "distortions and clipping. the feet also separate from the legs").
SWAY = 0.025  # how far her shoulders and head go sideways at a full sway, in picture heights
RISE, DIP = 0.006, 0.012  # how far everything from her hips up goes at a full bob up, and down
LEAN = 5.0  # degrees, from her hips up, at a full lean
BREATH = 0.004  # how far her shoulders and head rise at a full breath, from her waist up
HIPS, KNEE, ANKLE = 0.62, 0.365, 0.11  # how high these are on her
WAIST, CHEST = 0.80, 0.91
# Her chest's bounce (ParamBustY, which physics drives from her body's moves): a small round patch
# at her chest, on everything she wears over it. image2live2d's patch is as tall as her whole top,
# so the bounce pulled her shirt's hem off her skirt and a gap opened at her waist; with a breath
# that started at her thighs it looked like a stretch "between her belly and boots" (first user,
# 2026-11-10: "having it higher and making it more subtle would give a more natrual bounce").
BUST = 0.004  # how far the middle of the patch goes at a full ParamBustY, in picture heights
BUST_WIDE, BUST_HIGH = 0.065, 0.045  # the patch's half width and half height, in her own heights
BODY = ("ParamBodyAngleX", "ParamBodyAngleY", "ParamBodyAngleZ", "ParamBreath")
STILL = {"legwear", "footwear"}  # layers that are part of her, not cloth that swings
LAYER_OF = {}  # each part image write_layers made -> the layer it came from
DRAWN = {}  # ... -> the box of what is drawn in it, in the rig's units (a mesh's own box is wider)
MIDDLE = {}  # ... -> the middle of what is drawn in it (its pixels' own), and of its lowest rows
SHARP = {}  # ... -> its picture at the head pass's own size, and the box of her frame it covers (0 to 1)

# Her face, sharp close up. Her frame holds each head layer at about 0.41 of the size the head pass
# made it, and image2live2d's texture atlas packs every part at her frame's size, which leaves nine
# tenths of the atlas empty. layers.py keeps each head layer at the head pass's own size beside her
# layer (parts/<layer>@head.png, sharp.json); here a part whose layer has such a copy goes into the
# atlas at that size, about six times the pixels. Her layer stays the truth: its own alpha says
# which of the copy's pixels are this part's (a left eye, not the right; nothing the cleaning took
# out), and a copy that no longer matches its layer, shrunk, isn't used (the layer was edited
# since).
SHARP_SAME = 0.08  # a sharp copy this close to its part (0 to 1, on average, over the part) still matches it:
                   # a mouth or nose of a few dozen pixels measures 0.06 as taken, a layer from another pass far more

# Her head, straight: a drawing often has her head a little to one side (9.6 degrees on one
# character, 2.3 on another), and everything after this takes it to be upright: her features slide level, her
# lids come straight down, a tilt leans as far one way as the other. So first her head is turned
# about her chin until her eyes are level (the middle of what her eye whites, irises, lashes and
# brows each say), and moved sideways until the middle of her face is over the middle of her neck
# (first user, 2026-11-11: "we need to make sure we center and straighten the head before rigging").
# It is her meshes that turn, not her drawing, so nothing is redrawn or blurred. Hair that hangs
# below her chin turns less the lower it hangs, and not at all from HANGS face heights down.
LEVEL = ("eye_white", "pupil", "eye", "eyebrow")  # the pairs her tilt is read from
HANGS = 1.2
STRAIGHT = 0.5  # degrees: a head this near upright is left as drawn

# Her arms: ParamArm?A turns the whole arm at the shoulder, ParamArm?B bends it at the elbow, and
# the elbow goes where the shoulder has taken it. image2live2d added the two as straight-line moves
# of the arm at rest, so a bent arm on a lifted shoulder came apart ("stumpy"), and it bent
# a stiff forearm piece, whose top end stuck out past the elbow. Here the arm bends over a short
# band at the elbow, every point about the elbow by its own share of the angle, and there is a key
# every few degrees so the arm keeps its length on the way. Her arms are drawn behind her clothes:
# a forearm bent in toward her comes in front of them, or her hand would go behind her skirt. For
# that the .moc3 gets each arm as two drawables, cut along the mesh's own triangles at the elbow, so
# they meet edge to edge. (image2live2d's own cut makes two pieces that lie over each other for
# two fifths of the limb, where the outline is drawn twice and shows as a step; we switch it off.)
ARM_OUT, ARM_IN = 35.0, 10.0  # degrees at the shoulder at a full ParamArm?A, away from her and in
ELBOW_OUT, ELBOW_IN = 70.0, 80.0  # degrees at the elbow at a full ParamArm?B, away from her and in
ELBOW_BAND = 0.07  # the bend spreads this far each side of the elbow, in arm lengths
SWING_KEYS = (-10, -5, 0, 2.5, 5, 7.5, 10)
BEND_KEYS = (-10, -8, -6, -4, -2, -0.5, 0, 2, 4, 6, 8, 10)
ARM_ROLES = {"L": (SemanticRole.arm_l, SemanticRole.hand_l), "R": (SemanticRole.arm_r, SemanticRole.hand_r)}
pipeline.split_limb_segments = lambda stack, meshes: []

# Her knees: ParamLeg?B moves a knee toward her other leg (above 0) or away from it, her hip and her
# foot staying where they are, so the leg bends at the knee and her shoe stays on the floor. The
# leg she bends comes in front of the other. A sway bends the knee of the leg she sways off, the
# way weight goes onto one leg. (image2live2d's own leg moves swing a leg from the hip and kick the
# shin out from the knee, shoe and all, which is for a figure that walks.)
KNEE_IN, KNEE_OUT = 0.030, 0.018  # how far a knee goes at a full ParamLeg?B, in picture heights
SWAY_KNEE = 0.5  # how much of a full bend in the knee she sways off gets at a full sway
LEG_ROLES = {"L": SemanticRole.leg_l, "R": SemanticRole.leg_r}

BODY_BOX = (-0.25, -0.25, 1.5, 1.5)  # the body's warp deformer lies over the picture and round it,
BODY_GRID = (60, 12)                 # so nothing she does leaves it; its rows and columns
HEAD_GRID = (16, 8)  # rows enough that her chin goes all the way while hair below it stays


def box(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def ease(low, high, t):
    u = min(1.0, max(0.0, (t - low) / (high - low)))
    return u * u * (3 - 2 * u)


def turned(point, about, angle):
    dx, dy = point[0] - about[0], point[1] - about[1]
    c, s = math.cos(angle), math.sin(angle)
    return about[0] + dx * c - dy * s, about[1] + dx * s + dy * c


def by_id(rig, param_id):
    return next((p for p in rig.parameters if p.id == param_id), None)


def share(param, value):
    """A key's value as a share of the parameter's full swing: -1 to 1."""
    return value / max(abs(param.min), abs(param.max), 1e-6)


def write_moves(rig, param_id, part, mesh, move):
    """One part's moves at each key of a parameter: move(a, x, y) -> (dx, dy) for its point (x, y),
    a being the key's share of the parameter's full swing."""
    param = by_id(rig, param_id)
    if param is None:
        return
    for key in param.keyforms:
        a = share(param, key.value)
        if a:
            key.mesh_offsets[part.id] = [move(a, x, y) for x, y in mesh.vertices]


def clear_moves(rig, wanted, parts):
    """Take these parts' moves out of every parameter wanted(its id) picks."""
    for param in rig.parameters:
        if wanted(param.id):
            for key in param.keyforms:
                for part, _ in parts:
                    key.mesh_offsets.pop(part.id, None)


def set_keys(rig, param_id, values):
    param = by_id(rig, param_id)
    param.keyforms = [Keyform(value=float(v)) for v in values if param.min <= v <= param.max]


class Figure:
    """Where things are on her, in the rig's own units: 0 to 1 across the picture, y up."""

    def __init__(self, rig):
        self.drawn = [(p, rig.mesh_for(p.id)) for p in rig.parts_in_draw_order()
                      if rig.mesh_for(p.id) is not None]
        ids = head_group_ids(self.drawn)
        # image2live2d puts her parts in an order of its own. On her head that is wanted (her brows
        # come over her bangs). On her body it isn't: it took an open lab coat for a skirt and put
        # her legs behind the coat's inside. Her body's parts go back in our layers' order (the
        # number each part's name starts with), in the places image2live2d gave her body.
        places = [i for i, (p, _) in enumerate(self.drawn) if p.id not in ids]
        ours = sorted((self.drawn[i] for i in places),
                      key=lambda pm: int(pm[0].id[:2]) if pm[0].id[:2].isdigit() else 99)
        for i, part in zip(places, ours):
            self.drawn[i] = part
        self.head = [(p, m) for p, m in self.drawn if p.id in ids]
        self.body = [(p, m) for p, m in self.drawn if p.id not in ids]
        self.face = next((box(m.vertices) for p, m in self.head
                          if p.semantic_role is SemanticRole.face_base), None)
        neck = next((box(m.vertices) for p, m in self.drawn if p.semantic_role is SemanticRole.neck), None)
        # Where her drawing ends, not her meshes: a mesh can reach past what is drawn in it.
        self.feet = (min(b[1] for b in DRAWN.values()) if DRAWN
                     else min(y for _, m in self.drawn for _, y in m.vertices))
        if neck:
            self.middle, top = (neck[0] + neck[2]) / 2, neck[1]
        elif self.face:  # no neck layer: its base is a third of a face under her jaw
            self.middle, top = (self.face[0] + self.face[2]) / 2, self.face[1] - (self.face[3] - self.face[1]) / 3
        else:
            sys.exit("no face and no neck layer: can't tell where her head and body are")
        self.tall = max(top - self.feet, 1e-6)
        self.hips, self.knee, self.ankle = (self.feet + h * self.tall for h in (HIPS, KNEE, ANKLE))

    def height(self, y):
        return (y - self.feet) / self.tall

    def of(self, roles):
        return [(p, m) for p, m in self.drawn if p.semantic_role in roles]


def straighten(rig, fig):
    """Turn her head upright and centre it, in the rig's meshes. Returns what it did, for the log."""
    head = {p.id for p, _ in fig.head}
    role = {p.semantic_role.value: p.id for p, _ in fig.head}
    tilts, eyes = [], []
    for pair in LEVEL:
        left, right = (MIDDLE.get(role.get(f"{pair}_{side}")) for side in "lr")
        if left and right:
            (lx, ly), (rx, ry) = sorted((left[0], right[0]))
            tilts.append(math.atan2(ry - ly, rx - lx))
            if pair in ("eye_white", "pupil"):
                eyes.append(((lx + rx) / 2, (ly + ry) / 2))
    face = MIDDLE.get(role.get("face_base"))
    if not tilts or not face or fig.face is None:
        return "her head is as drawn (no pair of eyes or brows to read its tilt from)"
    tilt = sorted(tilts)[len(tilts) // 2]
    chin, high = face[1], fig.face[3] - fig.face[1]
    hold = lambda y: ease(chin[1] - HANGS * high, chin[1], y)  # 1 from her chin up, 0 where her hair hangs free

    def upright(point, share=1.0, across=0.0):
        x, y = turned(point, chin, -tilt * share)
        return x + across * share, y

    # The middle of her face, once upright: halfway between her chin and the point between her eyes.
    between = upright(eyes[0] if eyes else (fig.face[0] / 2 + fig.face[2] / 2, chin[1] + high / 2))
    across = fig.middle - (between[0] + chin[0]) / 2
    if abs(math.degrees(tilt)) < STRAIGHT and abs(across) < 0.001:
        return f"her head is upright as drawn ({math.degrees(tilt):+.1f} degrees)"
    for part, mesh in fig.head:
        mesh.vertices = [upright(v, hold(v[1]), across) for v in mesh.vertices]
        for boxes in (DRAWN, MIDDLE):
            if part.id not in boxes:
                continue
            if boxes is MIDDLE:
                boxes[part.id] = tuple(upright(p, hold(p[1]), across) for p in boxes[part.id])
            else:  # its box keeps its size and goes where its middle goes
                x0, y0, x1, y1 = boxes[part.id]
                mx, my = upright(((x0 + x1) / 2, (y0 + y1) / 2), hold((y0 + y1) / 2), across)
                boxes[part.id] = (mx - (x1 - x0) / 2, my - (y1 - y0) / 2, mx + (x1 - x0) / 2, my + (y1 - y0) / 2)
    return (f"her head turned {-math.degrees(tilt):+.1f} degrees about her chin and moved {across:+.4f} "
            f"(read from {len(tilts)} pairs: {', '.join(f'{math.degrees(t):+.1f}' for t in tilts)})")


def look(rig, fig):
    """Rewrite her irises' moves for a look. Returns how far they go each way, and each iris's white
    (its clipping mask)."""
    whites = {p.semantic_role.value[-1]: (p, m) for p, m in fig.head if p.semantic_role.value.startswith("eye_white")}
    irises = {p.semantic_role.value[-1]: (p, m) for p, m in fig.head if p.semantic_role.value.startswith("pupil")}
    rooms = {"left": [], "right": [], "up": [], "down": []}
    drawn = lambda part, mesh: DRAWN.get(part.id) or box(mesh.vertices)
    for side, iris in irises.items():
        ix0, iy0, ix1, iy1 = drawn(*iris)
        wx0, wy0, wx1, wy1 = drawn(*whites[side]) if side in whites else (ix0, iy0, ix1, iy1)
        wide, high = ix1 - ix0, iy1 - iy0
        rooms["left"].append(min(LOOK * wide, max(0.0, ix0 - wx0) + HIDE * wide))
        rooms["right"].append(min(LOOK * wide, max(0.0, wx1 - ix1) + HIDE * wide))
        rooms["down"].append(min(LOOK_UP * high, max(0.0, iy0 - wy0) + HIDE_UP * high))
        rooms["up"].append(min(LOOK_UP * high, max(0.0, wy1 - iy1) + HIDE_UP * high))
    reach = {way: min(room) for way, room in rooms.items() if room}
    for part, mesh in irises.values():
        write_moves(rig, "ParamEyeBallX", part, mesh, lambda a, x, y: (a * reach["right" if a > 0 else "left"], 0.0))
        write_moves(rig, "ParamEyeBallY", part, mesh, lambda a, x, y: (0.0, a * reach["up" if a > 0 else "down"]))
    masks = {part.id: whites[side][0].id for side, (part, _) in irises.items() if side in whites}
    if irises and by_id(rig, "ParamEyeBallForm") is None:  # Cubism's own name for it
        rig.parameters.append(Parameter(id="ParamEyeBallForm", min=-1.0, max=1.0, default=0.0,
                                        keyforms=[Keyform(value=-1.0), Keyform(value=0.0)]))
        for iris in irises.values():
            x0, y0, x1, y1 = drawn(*iris)
            write_moves(rig, "ParamEyeBallForm", *iris, lambda a, x, y, cx=(x0 + x1) / 2, cy=(y0 + y1) / 2: (
                abs(a) * (SMALL_IRIS - 1) * (x - cx), abs(a) * (SMALL_IRIS - 1) * (y - cy)))
    return reach, masks


# Her "O" mouth (parts.py mouth-oh), a second open mouth for a fright or a surprise: ParamMouthO
# swaps it for her open mouth, and ParamMouthOpenY opens whichever is showing, so lip sync goes on
# as it does. The expressions that want it (scared, surprised) set it; nothing else does.
def mouth_shapes(rig, fig):
    opened = [p for p, _ in fig.drawn if LAYER_OF.get(p.id) == "mouth_open"]
    oh = [p for p, _ in fig.drawn if LAYER_OF.get(p.id) == "mouth_oh"]
    if not opened or not oh or by_id(rig, "ParamMouthO") is not None:
        return
    rig.parameters.append(Parameter(id="ParamMouthO", min=0.0, max=1.0, default=0.0, keyforms=[
        Keyform(value=0.0, opacity_overrides={**{p.id: 1.0 for p in opened}, **{p.id: 0.0 for p in oh}}),
        Keyform(value=1.0, opacity_overrides={**{p.id: 0.0 for p in opened}, **{p.id: 1.0 for p in oh}})]))


def lids(rig, fig):
    """Rewrite how each eye shuts (ParamEyeLOpen, ParamEyeROpen)."""
    drawn = lambda part, mesh: DRAWN.get(part.id) or box(mesh.vertices)
    for side in "lr":
        param = by_id(rig, f"ParamEye{side.upper()}Open")
        eye = {kind: (p, m) for p, m in fig.head for kind in ("eye", "eye_white", "pupil", "eye_closed")
               if p.semantic_role.value == f"{kind}_{side}"}
        if param is None or "eye" not in eye:
            continue
        for key in param.keyforms:
            for part, _ in eye.values():
                key.mesh_offsets.pop(part.id, None)
                key.opacity_overrides.pop(part.id, None)
        if "eye_closed" in eye:  # the line her closed eye is drawn on
            _, y0, _, y1 = drawn(*eye["eye_closed"])
            line = (y0 + y1) / 2
        else:  # a quarter of the way up her open eye
            _, y0, _, y1 = drawn(*eye.get("eye_white", eye["eye"]))
            line = y0 + (y1 - y0) / 4
        keys = {key.value: key for key in param.keyforms}
        for value in (0.0, SQUINT, 1.0):
            if value not in keys:
                keys[value] = Keyform(value=value)
                param.keyforms.append(keys[value])
        for value, shut in ((0.0, 1.0), (SQUINT, 1 - SQUINT)):
            for kind in ("eye", "eye_white"):
                if kind in eye:
                    part, mesh = eye[kind]
                    keys[value].mesh_offsets[part.id] = [(0.0, (line - y) * shut) for _, y in mesh.vertices]
        if "eye_closed" in eye:
            for value in keys:
                keys[value].opacity_overrides[eye["eye_closed"][0].id] = 1.0 if value == 0 else 0.0
        for kind in ("eye", "eye_white", "pupil"):
            if kind in eye and (kind != "eye" or "eye_closed" in eye):  # with no drawn closed eye, her lashes are it
                keys[0.0].opacity_overrides[eye[kind][0].id] = 0.0
        smile_eye(rig, fig, side, eye, drawn)


def smile_eye(rig, fig, side, eye, drawn):
    """Rewrite ParamEye?Smile for one eye (see SMILE_BEND)."""
    param = by_id(rig, f"ParamEye{side.upper()}Smile")
    if param is None or "eye_white" not in eye:
        return
    _, wy0, _, wy1 = drawn(*eye["eye_white"])
    high = wy1 - wy0  # her open eye's height
    for key in param.keyforms:
        key.mesh_offsets.clear()
        key.opacity_overrides.clear()
    keys = {key.value: key for key in param.keyforms}
    for value in (0.0, 1.0):
        if value not in keys:
            keys[value] = Keyform(value=value)
            param.keyforms.append(keys[value])
    smiled = keys[1.0]
    # Open: the lower part of her eye rises, the most at its bottom, nothing at its top.
    for kind in ("eye", "eye_white", "pupil"):
        if kind in eye:
            part, mesh = eye[kind]
            smiled.mesh_offsets[part.id] = [(0.0, SMILE_OPEN * high * max(0.0, 1 - (y - wy0) / high) ** 1.5)
                                            for _, y in mesh.vertices]
    # Shut: her closed eye's line bends up, the most at the middle of the eye. Its corners are her
    # eye's corners; the drawn line runs a little past the outer one (its droop), which stays.
    if "eye_closed" in eye:
        part, mesh = eye["eye_closed"]
        x0, _, x1, _ = drawn(*eye["eye_closed"])
        middle = (fig.face[0] + fig.face[2]) / 2 if fig.face else 0.5
        inner, outer = (x0, x1) if abs(x0 - middle) < abs(x1 - middle) else (x1, x0)
        corner = inner + (outer - inner) / 1.15  # parts.py draws the lid to 1.15 of the corner-to-corner span
        lift = lambda x: SMILE_BEND * high * math.sin(math.pi * min(1.0, max(0.0, (x - inner) / (corner - inner))))
        smiled.mesh_offsets[part.id] = [(0.0, lift(x)) for x, _ in mesh.vertices]


def turn_parts(rig, fig, reach):
    """Write each head part's slide into the rig's ParamAngleX and ParamAngleY keys. Returns what it
    did, for the log."""
    if fig.face is None:
        return ["no face layer: her head won't turn"]
    fx0, fy0, fx1, fy1 = fig.face
    width, height, middle = fx1 - fx0, fy1 - fy0, (fx0 + fx1) / 2
    side_of = lambda x: 0 if abs(x - middle) < 0.08 * width else (1 if x > middle else -1)

    # The parts of one eye share one middle, so they stay on top of each other as they narrow.
    eyes = {}
    for part, mesh in fig.head:
        if KINDS.get(part.semantic_role.value) == "eye":
            x0, _, x1, _ = box(mesh.vertices)
            eyes.setdefault(side_of((x0 + x1) / 2), []).extend(mesh.vertices)
    eye_boxes = {side: box(points) for side, points in eyes.items()}

    said = []
    for part, mesh in fig.head:
        role = part.semantic_role
        kind = KINDS.get(role.value)
        if not kind:
            continue
        x0, y0, x1, y1 = box(mesh.vertices)
        centre = (x0 + x1) / 2
        side = side_of(centre)
        if kind == "eye":
            ex0, _, ex1, _ = eye_boxes[side]
            centre = (ex0 + ex1) / 2
        elif role is SemanticRole.accessory and len(eye_boxes) == 2 and all(
                x0 < (b[0] + b[2]) / 2 < x1 and y0 < b[3] and y1 > b[1] for b in eye_boxes.values()):
            kind, side = "glasses", 0  # it lies across both her eyes, and it stays on them:
            clear_moves(rig, lambda pid: pid.startswith("ParamAcc"), [(part, mesh)])  # no swinging
        elif kind in ("face", "hair"):
            centre, side = middle, 0
        slide, less, toward, away, up, down = TURNS[kind]
        iris = role.value.startswith("pupil") and reach

        def turn(a, x, y, centre=centre, side=side, slide=slide, less=less, toward=toward, away=away, iris=iris):
            wide = (toward if side * a > 0 else away) if side else (toward + away) / 2
            move = width * (a * slide - side * abs(a) * less) + abs(a) * (wide - 1) * (x - centre)
            if iris:
                move += a * TURN_LOOK * reach["right" if a > 0 else "left"]
            return move, 0.0

        def nod(a, x, y, up=up, down=down, iris=iris):
            move = height * a * (up if a > 0 else down)
            if iris:
                move += a * TURN_LOOK * reach["up" if a > 0 else "down"]
            return 0.0, move

        write_moves(rig, "ParamAngleX", part, mesh, turn)
        write_moves(rig, "ParamAngleY", part, mesh, nod)
        said.append(f"{part.id} as {kind}" + ("" if not side else " (left)" if side < 0 else " (right)"))
    return said


def body_move(fig, param_id, a, x, y):
    """Where her body's move takes the point (x, y) of her, as (dx, dy)."""
    t = fig.height(y)
    if param_id == "ParamBodyAngleX":
        return a * SWAY * ease(0.3, 1.0, t), 0.0
    if param_id == "ParamBodyAngleY":
        return 0.0, a * (RISE if a > 0 else DIP) * ease(0.0, 0.6, t)
    if param_id == "ParamBreath":
        return 0.0, a * BREATH * ease(WAIST, 0.98, t)
    tx, ty = turned((x, y), (fig.middle, fig.hips), math.radians(a * LEAN) * ease(0.45, 0.9, t))
    return tx - x, ty - y


class Arm:
    """One arm as a chain: shoulder, elbow, and how much of the elbow's bend each point takes."""

    def __init__(self, rig, fig, letter):
        self.swing, self.bend = by_id(rig, f"ParamArm{letter}A"), by_id(rig, f"ParamArm{letter}B")
        self.parts = fig.of(ARM_ROLES[letter])
        self.ok = bool(self.parts and self.swing and self.bend)
        if not self.ok:
            return
        self.shoulder, self.elbow, wrist = author._limb_joints([m for _, m in self.parts])
        self.side = 1 if self.shoulder[0] >= fig.middle else -1
        ax, ay = wrist[0] - self.shoulder[0], wrist[1] - self.shoulder[1]
        along = lambda p: ((p[0] - self.shoulder[0]) * ax + (p[1] - self.shoulder[1]) * ay) / (ax * ax + ay * ay)
        at = along(self.elbow)
        self.weights = {p.id: [ease(at - ELBOW_BAND, at + ELBOW_BAND, along(v)) for v in m.vertices]
                        for p, m in self.parts}
        self.below_elbow = lambda points: along([sum(p[i] for p in points) / len(points) for i in (0, 1)]) >= at
        set_keys(rig, self.swing.id, SWING_KEYS)
        set_keys(rig, self.bend.id, BEND_KEYS)

    def angles(self, values):
        a, b = share(self.swing, values[self.swing.id]), share(self.bend, values[self.bend.id])
        return (math.radians(self.side * a * (ARM_OUT if a > 0 else ARM_IN)),
                math.radians(self.side * b * (ELBOW_OUT if b > 0 else ELBOW_IN)))

    def pose(self, part, mesh, values):
        at_shoulder, at_elbow = self.angles(values)
        return [turned(turned(v, self.elbow, at_elbow * w), self.shoulder, at_shoulder)
                for v, w in zip(mesh.vertices, self.weights[part.id])]

    def in_front(self, part, values):
        """Whether her forearm is in front of her clothes."""
        return values[self.bend.id] < 0

    def pieces(self, mesh):
        """The mesh's triangles above the elbow, and from the elbow down."""
        lower = [self.below_elbow([mesh.vertices[i] for i in t]) for t in mesh.triangles]
        return ([tuple(t) for t, low in zip(mesh.triangles, lower) if not low],
                [tuple(t) for t, low in zip(mesh.triangles, lower) if low])


class Leg:
    """One leg, and how far each height of it goes with its knee."""

    def __init__(self, rig, fig, letter):
        self.bend = by_id(rig, f"ParamLeg{letter}B")
        self.parts = fig.of({LEG_ROLES[letter]})
        self.ok = bool(self.parts and self.bend)
        if not self.ok:
            return
        x0, _, x1, _ = box([v for _, m in self.parts for v in m.vertices])
        self.side = 1 if (x0 + x1) / 2 >= fig.middle else -1
        self.sway = by_id(rig, "ParamBodyAngleX")

        def knee(y):  # 1 at her knee, down to 0 at her hip and at her ankle
            if not fig.ankle < y < fig.hips:
                return 0.0
            return (fig.hips - y) / (fig.hips - fig.knee) if y >= fig.knee else (y - fig.ankle) / (fig.knee - fig.ankle)

        for part, mesh in self.parts:
            write_moves(rig, self.bend.id, part, mesh,
                        lambda a, x, y: (-self.side * a * (KNEE_IN if a > 0 else KNEE_OUT) * knee(y), 0.0))
            if self.sway:  # on top of the body's own sway, which every part gets from its warp deformer
                write_moves(rig, self.sway.id, part, mesh,
                            lambda a, x, y: (-self.side * abs(a) * SWAY_KNEE * KNEE_IN * knee(y) * (self.side * a < 0), 0.0))

    def in_front(self, part, values):
        return values.get(self.bend.id, 0) > 0 or bool(self.sway and self.side * values.get(self.sway.id, 0) < 0)


ELBOW_IDLE = 0.8  # in the idle, how far an elbow bends for each step her arm swings out


def liven_idle(rig, arms):
    """image2live2d's idle swings her arms a little from the shoulder, stiff. Add her elbows."""
    idle = next((a for a in rig.animations if a.name == "idle"), None)
    if idle is None:
        return
    lanes = {lane.param_id: lane for lane in idle.lanes}
    for arm in arms:
        swing = lanes.get(arm.swing.id)
        if swing and arm.bend.id not in lanes:
            idle.lanes.append(swing.model_copy(deep=True, update={
                "param_id": arm.bend.id,
                "keyframes": [k.model_copy(update={"value": abs(k.value) * ELBOW_IDLE}) for k in swing.keyframes]}))


def bounce(rig, fig, limbs):
    """Rewrite her chest's bounce, if image2live2d gave her one."""
    bust = by_id(rig, "ParamBustY")
    if bust is None:
        return
    clear_moves(rig, lambda pid: pid == bust.id, fig.drawn)
    cx, cy = fig.middle, fig.feet + CHEST * fig.tall
    wide, high = BUST_WIDE * fig.tall, BUST_HIGH * fig.tall

    def move(a, x, y):
        far = ((x - cx) / wide) ** 2 + ((y - cy) / high) ** 2
        return (0.0, a * BUST * (1 - far) ** 2) if far < 1 else (0.0, 0.0)

    limbs = {p.id for limb in limbs for p, _ in limb.parts}
    for part, mesh in fig.body:
        if part.id not in limbs and part.semantic_role is not SemanticRole.neck:
            write_moves(rig, bust.id, part, mesh, move)


def pose_rig(rig, fig):
    """Rewrite how she moves in the rig. Returns what the .moc3 writer needs besides the rig."""
    clear_moves(rig, lambda pid: pid in BODY or pid.startswith(("ParamArm", "ParamLeg")), fig.drawn)
    clear_moves(rig, lambda pid: pid.startswith("ParamCloth"),
                [(p, m) for p, m in fig.drawn if LAYER_OF.get(p.id) in STILL])
    reach, masks = look(rig, fig)
    # Her blush stays on her face: where a mark reaches past her cheek it is cut off there.
    face = next((p for p, _ in fig.head if p.semantic_role is SemanticRole.face_base), None)
    if face:
        masks.update({p.id: face.id for p, _ in fig.head if p.semantic_role is SemanticRole.blush})
    lids(rig, fig)
    mouth_shapes(rig, fig)
    print("head turn: " + "; ".join(turn_parts(rig, fig, reach)))
    arms = [arm for arm in (Arm(rig, fig, "L"), Arm(rig, fig, "R")) if arm.ok]
    legs = [leg for leg in (Leg(rig, fig, "L"), Leg(rig, fig, "R")) if leg.ok]
    liven_idle(rig, arms)
    bounce(rig, fig, arms + legs)
    print(f"body: her feet at {fig.feet:.3f}, knees {fig.knee:.3f}, hips {fig.hips:.3f}, neck "
          f"{fig.feet + fig.tall:.3f}; {len(arms)} arms that bend, {len(legs)} legs that bend; "
          f"irises go {', '.join(f'{way} {far:.4f}' for way, far in reach.items())}")
    return masks, arms, legs


def combos(params):
    """Every combination of these parameters' keys, as {parameter id: value}, the first parameter
    changing fastest: the order a .moc3 lists a part's keyforms in."""
    keys = [sorted(k.value for k in p.keyforms) for p in params]
    out = []
    for index in range(math.prod(len(k) for k in keys)):
        values = {}
        for param, its in zip(params, keys):
            values[param.id] = its[index % len(its)]
            index //= len(its)
        out.append(values)
    return out


def rig_to_moc3(rig, *, atlas_uv=None, log=print):
    """The rig as a .moc3, in place of image2live2d's rig_to_moc3 (whose mesh loop and warp deformer
    this follows, and whose build_moc3 packs the result)."""
    from image2live2d.backends.live2d.moc3_emit import EmitMesh, EmitParam, EmitPart, EmitWarp
    print("head: " + straighten(rig, Figure(rig)))
    fig = Figure(rig)
    masks, arms, legs = pose_rig(rig, fig)
    index = {p.id: i for i, p in enumerate(rig.parameters)}
    to_moc = lambda x, y: ((x - 0.5) * 2.0, (0.5 - y) * 2.0)  # the rig's units to the .moc3's
    head_ids = {p.id for p, _ in fig.head}

    # Draw order, ten apart so a part can come in front of others as she moves.
    order = {p.id: 100 + 10 * i for i, (p, _) in enumerate(fig.drawn)}
    over_body = max((order[p.id] for p, _ in fig.body), default=100) + 3
    over_legs = max((order[p.id] for leg in legs for p, _ in leg.parts), default=100) + 3
    limb_of = {p.id: limb for limb in arms + legs for p, _ in limb.parts}

    # The body's warp deformer: a grid over the whole picture, moved by her body's parameters.
    bx, by, bw, bh = BODY_BOX
    in_body = lambda x, y: ((x - bx) / bw, (y - by) / bh)
    rows, cols = BODY_GRID
    body_params = [p for p in rig.parameters if p.id in BODY]
    grids = []
    for values in combos(body_params):
        grid = []
        for r in range(rows + 1):
            for c in range(cols + 1):
                x, y = bx + bw * c / cols, by + bh * r / rows
                moves = [body_move(fig, p.id, share(p, values[p.id]), x, y) for p in body_params if values[p.id]]
                grid.append(to_moc(x + sum(m[0] for m in moves), y + sum(m[1] for m in moves)))
        grids.append(grid)
    warps = [EmitWarp(id="D_BODY", parent_part_index=0, param_indices=[index[p.id] for p in body_params],
                      rows=rows, columns=cols, keyforms=grids, child_ids={p.id for p, _ in fig.body})]

    # The head's, inside the body's (so its grid is in the body grid's own 0-to-1 space): the tilt,
    # and the whole head's share of a nod.
    in_head = None
    if fig.head:
        hx0, hy0, hx1, hy1 = box([v for _, m in fig.head for v in m.vertices])
        hx0, hx1 = hx0 - (hx1 - hx0) * 0.12, hx1 + (hx1 - hx0) * 0.12  # room for a part to slide
        hy0, hy1 = hy0 - (hy1 - hy0) * 0.12, hy1 + (hy1 - hy0) * 0.12
        in_head = lambda x, y: ((x - hx0) / (hx1 - hx0), (y - hy0) / (hy1 - hy0))
        tilt, nod = by_id(rig, "ParamAngleZ"), by_id(rig, "ParamAngleY")
        head_params = [p for p in (tilt, nod) if p]
        if fig.face:
            chin, face_high = fig.face[1], fig.face[3] - fig.face[1]
            under_jaw = ((fig.face[0] + fig.face[2]) / 2, chin - TILT_UNDER_JAW * face_high)
        else:
            chin, face_high = hy0, 0.0
            under_jaw = ((hx0 + hx1) / 2, hy0)

        def head_point(x, y, values):
            if nod and values[nod.id] and face_high:
                a = share(nod, values[nod.id])
                y += a * (NOD_UP if a > 0 else NOD_DOWN) * face_high * (1 - ease(0.0, HANGS * face_high, chin - y))
            angle = share(tilt, values[tilt.id]) * TILT if tilt else 0.0
            return in_body(*turned((x, y), under_jaw, angle))

        rows, cols = HEAD_GRID
        grids = [[head_point(hx0 + (hx1 - hx0) * c / cols, hy0 + (hy1 - hy0) * r / rows, values)
                  for r in range(rows + 1) for c in range(cols + 1)] for values in combos(head_params)]
        warps.append(EmitWarp(id="D_HEAD", parent_part_index=0, param_indices=[index[p.id] for p in head_params],
                              rows=rows, columns=cols, keyforms=grids, child_ids=head_ids))

    # Her parts: each one's points at every combination of the keys of the parameters that move it.
    meshes, orders = [], {}
    for part_index, (part, mesh) in enumerate(fig.drawn):
        limb = limb_of.get(part.id)
        arm = limb if isinstance(limb, Arm) else None
        mine = [p for p in rig.parameters
                if (arm and p.id in (arm.swing.id, arm.bend.id))
                or any(part.id in k.opacity_overrides or any(dx or dy for dx, dy in k.mesh_offsets.get(part.id, []))
                       for k in p.keyforms)]
        place = in_head if part.id in head_ids else in_body
        keyforms, opacities, behind, front, keyed = [], [], [], [], False
        for values in combos(mine):
            points = [list(v) for v in (arm.pose(part, mesh, values) if arm else mesh.vertices)]
            opacity = part.opacity
            for param in mine:
                for point, (dx, dy) in zip(points, moc3_emit._offset_at(param, values[param.id], part.id, len(points))):
                    point[0] += dx
                    point[1] += dy
                faded = moc3_emit._opacity_at(param, values[param.id], part.id)
                if faded is not None:
                    opacity, keyed = opacity * faded, True
            keyforms.append([place(x, y) for x, y in points])
            opacities.append(opacity)
            behind.append(order[part.id])
            front.append((over_body if arm else over_legs) + [p.id for p, _ in limb.parts].index(part.id)
                         if limb is not None and limb.in_front(part, values) else order[part.id])
        if len(keyforms) > 3000:
            log(f"{part.id}: {len(keyforms)} keyforms from {[p.id for p in mine]}")
        if atlas_uv is not None and part.id in atlas_uv:
            uvs, texture = [moc3_emit._remap_uv(u, v, atlas_uv[part.id]) for u, v in mesh.uvs], 0
        else:
            uvs = [(u, v) for u, v in mesh.uvs]
            texture = [t.id for t in rig.textures].index(part.texture_id)
        if arm:  # above the elbow it stays behind her clothes
            upper, lower = arm.pieces(mesh)
            pieces = [(part.id, upper, behind), (part.id + "_lo", lower, front)]
        else:
            pieces = [(part.id, [tuple(t) for t in mesh.triangles], front)]
        for mesh_id, triangles, its_orders in pieces:
            if triangles:
                orders[mesh_id] = its_orders
                if part.id not in head_ids:
                    warps[0].child_ids.add(mesh_id)  # a forearm is in the body's warp deformer too
                meshes.append(EmitMesh(id=mesh_id, part_index=part_index, texture_no=texture, uvs=uvs,
                                       triangles=triangles, param_indices=[index[p.id] for p in mine],
                                       keyforms=keyforms, opacities=opacities if keyed else []))

    params = [EmitParam(p.id, p.min, p.max, p.default, sorted(k.value for k in p.keyforms)) for p in rig.parameters]
    parts = [EmitPart(p.id, float(order[p.id])) for p, _ in fig.drawn]
    canvas = {"pixelsPerUnit": 500.0, "originX": 500.0, "originY": 500.0, "width": 1000.0, "height": 1000.0,
              "flags": 0}
    moc = moc3_emit.build_moc3(canvas, params, parts, meshes, warps=warps)

    # What build_moc3 has no way to say: a deformer inside another, draw order by keyform, masks.
    S = moc.sections
    if len(warps) == 2:
        S["deformers"]["parentDeformerIndices"][1] = 0
    art = S["artMeshes"]
    for i, part_id in enumerate(art["ids"]):
        begin = art["keyformSourcesBeginIndices"][i]
        S["artMeshKeyforms"]["drawOrders"][begin:begin + len(orders[part_id])] = [float(o) for o in orders[part_id]]
    begins, counts, masked = [], [], []
    for part_id in art["ids"]:
        begins.append(len(masked))
        counts.append(1 if part_id in masks else 0)
        if part_id in masks:
            masked.append(art["ids"].index(masks[part_id]))
    art["drawableMaskSourcesBeginIndices"], art["drawableMaskSourcesCounts"] = begins, counts
    S["drawableMasks"]["artMeshSourcesIndices"] = masked
    moc.counts["drawableMasks"] = len(masked)
    return moc


moc3_emit.rig_to_moc3 = rig_to_moc3  # image2live2d's bundle tool looks it up there
_build_atlas = moc3_emit.build_atlas


def sharp_cell(part, copy, at, per):
    """A part's picture from its layer's sharp copy: (the picture, the box of her frame it covers
    from 0 to 1, how far it is from the part on average), or None if the part is empty. copy is the
    layer at the head pass's own size; its corner is at `at` in her frame and each of its pixels is
    `per` of hers."""
    import numpy as np
    from PIL import ImageChops, ImageFilter
    W, H = part.size
    alpha = part.getchannel("A")
    box = alpha.point(lambda a: 255 if a > 8 else 0).getbbox()  # what the atlas keeps of the part
    if not box:
        return None
    # That box in the copy's own pixels, whole ones, so the copy isn't resampled.
    sx0, sy0 = math.floor((box[0] - at[0]) / per[0]), math.floor((box[1] - at[1]) / per[1])
    sx1, sy1 = math.ceil((box[2] - at[0]) / per[0]), math.ceil((box[3] - at[1]) / per[1])
    cell = Image.new("RGBA", (sx1 - sx0, sy1 - sy0))
    cell.paste(copy, (-sx0, -sy0))
    fx0, fy0 = at[0] + sx0 * per[0], at[1] + sy0 * per[1]  # the cell's corner in her frame
    fx1, fy1 = at[0] + sx1 * per[0], at[1] + sy1 * per[1]
    # The part's own alpha, at the copy's size: which of the copy's pixels belong to this part.
    mine = alpha.transform(cell.size, Image.AFFINE, (per[0], 0, fx0, 0, per[1], fy0), resample=Image.BILINEAR)
    mine = mine.point(lambda a: 255 if a > 8 else 0).filter(ImageFilter.MaxFilter(5))
    cell.putalpha(ImageChops.multiply(cell.getchannel("A"), mine))
    # How well it still matches: the cell brought to her frame's own pixels, where the part is, and
    # both softened a little, so a thin line a fraction of a pixel off doesn't count as a change.
    soft = cell.filter(ImageFilter.GaussianBlur(0.5 / per[0]))
    small = soft.transform((box[2] - box[0], box[3] - box[1]), Image.AFFINE,
                           (1 / per[0], 0, (box[0] - fx0) / per[0], 0, 1 / per[1], (box[1] - fy0) / per[1]), resample=Image.BILINEAR)
    a = np.asarray(small.filter(ImageFilter.BoxBlur(1)), np.float32) / 255
    b = np.asarray(part.crop(box).filter(ImageFilter.BoxBlur(1)), np.float32) / 255
    where = (a[..., 3] > 0.05) | (b[..., 3] > 0.05)
    apart = float(np.abs(a[..., :3] * a[..., 3:4] - b[..., :3] * b[..., 3:4])[where].mean()) if where.any() else 1.0
    return cell, (fx0 / W, fy0 / H, fx1 / W, fy1 / H), apart


def sharp_atlas(rig, asset_root, *, atlas_size=4096, pad=2):
    """The model's texture atlas, as image2live2d's build_atlas makes it (whose packing this
    follows), with her head's parts at the head pass's own size where SHARP has them. Returns the
    atlas and, for each part, the box of its picture it holds and where in the atlas that is."""
    if not SHARP:
        return _build_atlas(rig, asset_root, atlas_size=atlas_size, pad=pad)
    import numpy as np
    root = Path(asset_root)
    textures = {t.id: t for t in rig.textures}
    crops = []  # [part id, picture, the box of her frame it covers from 0 to 1]
    for part in (p for p in rig.parts_in_draw_order() if rig.mesh_for(p.id) is not None):
        path = root / textures[part.texture_id].path
        if path.stem in SHARP:
            cell, rect = SHARP[path.stem]
            crops.append([part.id, cell, *rect])
            continue
        img = Image.open(path).convert("RGBA")
        W, H = img.size
        ys, xs = np.where(np.array(img)[:, :, 3] > 8)
        x0, y0, x1, y1 = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())) if len(xs) else (0, 0, W - 1, H - 1)
        crops.append([part.id, img.crop((x0, y0, x1 + 1, y1 + 1)), x0 / W, y0 / H, (x1 + 1) / W, (y1 + 1) / H])
    order = sorted(range(len(crops)), key=lambda i: -crops[i][1].height)  # shelves, the tallest first

    def packed(scale):
        places, x, y, row = {}, pad, pad, 0
        for i in order:
            w, h = max(1, int(crops[i][1].width * scale)), max(1, int(crops[i][1].height * scale))
            if x + w + pad > atlas_size:
                x, y, row = pad, y + row + pad, 0
            if y + h + pad > atlas_size:
                return None
            places[i] = (x, y, w, h)
            x, row = x + w + pad, max(row, h)
        return places

    scale = 1.0
    places = packed(scale)
    while places is None and scale > 0.1:  # everything a little smaller until it fits
        scale *= 0.8
        places = packed(scale)
    if places is None:
        raise ValueError("her parts don't fit the texture atlas")
    atlas, remap = Image.new("RGBA", (atlas_size, atlas_size), (0, 0, 0, 0)), {}
    for i, (part_id, crop, cx0, cy0, cx1, cy1) in enumerate(crops):
        x, y, w, h = places[i]
        atlas.alpha_composite(crop.resize((w, h), Image.LANCZOS) if (w, h) != crop.size else crop, (x, y))
        remap[part_id] = (cx0, cy0, cx1, cy1, x / atlas_size, y / atlas_size, (x + w) / atlas_size, (y + h) / atlas_size)
    return atlas, remap


moc3_emit.build_atlas = sharp_atlas  # ...and this
# Left roles split into left and right: image2live2d's own (eyes, whites, irises, brows) and ours.
SIDES = dict(sources._SIDE_FLIP)
SIDES[SemanticRole.eye_closed_l] = SemanticRole.eye_closed_r
SIDES[SemanticRole.ear_l] = SemanticRole.ear_r


def i2l_tool(name):
    """One of image2live2d's command-line tools (vendor/tools/), loaded as a module."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(VENDOR, "tools", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# A pale rim: where a part's edge met the drawing's light background, the split leaves edge pixels
# that are part her and part background, lighter than anything of hers beside them. On a dark
# background, or over a darker part of her, they show as a thin light line round hair and clothes.
# Such a pixel takes the colour of her own pixels just inside it (usually her outline). Only pixels
# lighter than those are touched: a dark outline, and a highlight further in, stay as drawn.
# Her face's fine parts are left out: a mouth or a brow is a thin line with no inside, and the clean
# recoloured a faint mouth line from its darker corners.
FINE = {"mouth", "mouth_close", "mouth_open", "mouth_oh", "nose", "eyebrow", "eyelash", "eyewhite", "irides", "eye_close",
        "blush", "eyewear", "earwear"}
RIM = 3          # how far in from her edge a pixel still counts as on her rim, in her frame's pixels
RIM_PALE = 0.08  # ...and how much lighter than the inside beside it (0 to 1) makes it a pale one


def clean_rim(img, reach=RIM):
    """The picture with its pale rim pixels recoloured, and how many there were."""
    import numpy as np
    from PIL import ImageFilter
    box = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if not box:
        return img, 0
    box = (max(box[0] - 1, 0), max(box[1] - 1, 0), min(box[2] + 1, img.width), min(box[3] + 1, img.height))
    crop = img.crop(box)
    rgb = np.asarray(crop.convert("RGB"), np.float32) / 255
    alpha = np.asarray(crop.getchannel("A"), np.float32) / 255
    solid = Image.fromarray(((alpha >= 0.9) * 255).astype(np.uint8))
    inner = np.asarray(solid.filter(ImageFilter.MinFilter(2 * reach + 1))) > 0  # this far inside her edge
    if not inner.any():
        return img, 0
    colour, known = rgb * inner[..., None], inner.copy()
    for _ in range(reach + 3):  # the inside's colours carried outward, a pixel at a time
        total, count = np.zeros_like(colour), np.zeros(alpha.shape, np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    total += np.roll(colour * known[..., None], (dy, dx), axis=(0, 1))
                    count += np.roll(known, (dy, dx), axis=(0, 1))
        new = ~known & (count > 0)
        colour[new] = total[new] / count[new][:, None]
        known |= new
    light = np.array([0.3, 0.59, 0.11], np.float32)
    pale = (alpha > 0) & ~inner & known & (rgb @ light - colour @ light > RIM_PALE)
    if not pale.any():
        return img, 0
    rgb[pale] = colour[pale]
    done = img.copy()
    done.paste(Image.fromarray((np.dstack([rgb, alpha]) * 255).round().astype(np.uint8), "RGBA"), box[:2])
    return done, int(pale.sum())


def layers_dir(name):
    """Her layers folder, as in layers.py: akane, or akane/working."""
    who, _, pose = name.partition("/")
    base = os.path.join(CHARS, who, "layers")
    return os.path.join(base, pose) if pose else base


def out_dir(name):
    return os.path.join(OUT, name.replace("/", "-"))


TUCK = 0.03  # how far a tucked-in layer is grown under the one over it, in picture heights


def settings(name):
    """Her layers/live2d.json, if there is one: {"whole": [...], "tucked": {...}, "why": ...}.
    - whole: layers kept in one piece, as part of her body (the torso role). image2live2d cuts a
      layer of two arms or two legs into a left and a right limb and swings them; arms held behind
      her back (as on a semi-chibi drawing) aren't limbs it can swing. It also looks among her clothes for
      a skirt to swing and a bodice to bounce, and takes a long open coat for the skirt (on one:
      it swung her coat and its inside each on its own, and left her real skirt still); a torso
      layer is none of those.
    - rims: false leaves pale edge pixels as they are (see clean_rim), for a character drawn with
      a light outline of her own.
    - tucked: {"topwear": "bottomwear"} for a top tucked into a skirt. The layers stop where they
      meet, so when either moves a gap opens between them (first user, 2026-11-10: "extending a
      little bit of shirt and ensuring its behind the skirt would stop the gap"). The first layer
      is drawn just under the second and grown downward where the second covers it (see tuck)."""
    path = os.path.join(layers_dir(name), "live2d.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def tuck(top, over):
    """The image `top` grown downward, in its own colours, wherever `over` covers what is under its
    lower edge: nothing new shows while they stand still."""
    import numpy as np
    pixels, cover = np.array(top), np.array(over)[:, :, 3] >= 200
    solid = pixels[:, :, 3] >= 200
    high = pixels.shape[0]
    for x in np.where(solid.any(axis=0))[0]:
        low = high - 1 - int(np.argmax(solid[::-1, x]))  # its lowest solid pixel in this column
        colour = pixels[low - 3 if low >= 3 and solid[low - 3, x] else low, x].copy()
        colour[3] = 255
        rows = np.arange(low + 1, min(low + 1 + round(TUCK * high), high))
        pixels[rows[cover[rows, x]], x] = colour
    return Image.fromarray(pixels)


def drawing_order(layers, tucked={}):
    """Her layers from the back to the front, with her lashes and closed eyes moved over her irises.
    See-through puts the lashes under the whites, so an iris that slides up went over her lash line
    instead of under it."""
    order = list(layers)
    for under, over in tucked.items():  # a tucked-in layer goes just under the one it is tucked into
        if under in order and over in order and order.index(under) > order.index(over):
            order.remove(under)
            order.insert(order.index(over), under)
    lids = [layer for layer in ("eyelash", "eye_close") if layer in order]
    if "irides" in order:
        order = [layer for layer in order if layer not in lids]
        at = order.index("irides") + 1
        order = order[:at] + lids + order[at:]
    return order


# Her nose goes under her blush, just over her face. See-through often gives it as a patch of her
# skin with the line in it, and over the blush that patch left a hole the shape of her nose in a
# blush across it (first user, 2026-11-13). The blush is see-through, so her nose shows through it,
# a little pink, as a blush over a nose is drawn; her glasses stay over both.
UNDER_BLUSH = ("nose",)


def write_layers(name):
    """Her layers as image2live2d's {order}_{role}.png, cleaned and split as its own PSD import does
    (sources.raws_to_stack), apart from the layers she keeps whole."""
    src = layers_dir(name)
    with open(os.path.join(src, "layers.json"), encoding="utf-8") as f:
        info = json.load(f)
    whole = set(settings(name).get("whole", []))
    tucked = {under: over for under, over in settings(name).get("tucked", {}).items()
              if under in info["order"] and over in info["order"]}
    dst = os.path.join(out_dir(name), "layers")
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    images, copies, sharp, changed = {}, {}, [], []
    rims = settings(name).get("rims", True)  # "rims": false in her live2d.json leaves her edges as they are
    if os.path.exists(os.path.join(src, "sharp.json")):  # her head's layers at the head pass's own size
        with open(os.path.join(src, "sharp.json"), encoding="utf-8") as f:
            for layer, where in json.load(f).items():
                path = os.path.join(src, "parts", layer + "@head.png")
                if layer in info["order"] and os.path.exists(path):
                    copy = Image.open(path).convert("RGBA")
                    if rims and layer not in FINE:
                        copy = clean_rim(copy, round(RIM / where["per"][0]))[0]
                    copies[layer] = (copy, where["at"], where["per"])
    SHARP.clear()
    pale = 0
    for layer in info["order"]:
        if layer not in LEFT_OUT:
            img = Image.open(os.path.join(src, "parts", layer + ".png")).convert("RGBA")
            # A blush is faint and soft on purpose: the cleaning would take its edge and its strokes.
            images[layer] = img if layer == "blush" else sources.drop_specks(sources._clean_alpha(img))
            if rims and layer not in FINE:
                images[layer], n = clean_rim(images[layer])
                pale += n
    if pale:
        print(f"   pale rim: {pale} edge pixels that were lighter than her beside them took her colour")
    for under, over in tucked.items():
        images[under] = tuck(images[under], images[over])
    names = drawing_order(info["order"], tucked)
    if "face" in images:
        face_box = images["face"].getchannel("A").point(lambda a: 255 if a >= 64 else 0).getbbox()
        FACE_WIDE[0] = (face_box[2] - face_box[0]) / images["face"].width if face_box else None
    if "blush" not in images and "face" in images:
        import numpy as np
        alpha = lambda layer: np.asarray(images[layer].getchannel("A"), np.float32) / 255
        eyes = [alpha(layer) for layer in ("eyewhite", "eyelash", "irides") if layer in images]
        found = blush_marks.eyes_of(eyes, alpha("face")) if eyes else None
        if found:
            face = np.asarray(images["face"], np.float32) / 255
            images["blush"] = blush_marks.as_image(blush_marks.draw(face.shape, found, blush_marks.skin_of(face)))
            names.insert(names.index("face") + 1, "blush")
            print("   her blush: the kit's style 1, drawn from her eyes (`parts blush` makes another her layer)")
        else:
            print("   her blush: image2live2d's own, as no eye was found on each side of her face")
    if "blush" in names and "blush" in images:  # see UNDER_BLUSH
        for layer in UNDER_BLUSH:
            if layer in names and names.index(layer) > names.index("blush"):
                names.remove(layer)
                names.insert(names.index("blush"), layer)
    order = 0
    for layer in names:
        if layer not in images:
            continue
        img = images[layer]
        role = ROLES.get(layer) or sources.role_from_layer_name(layer)
        if layer in whole:
            role = SemanticRole.torso
        outputs = [(role, img)]
        legs = sources._split_lr(img) if layer == "legwear" and layer not in whole else None
        if legs:  # her right leg is the one on the left of the picture, as with her arms
            outputs = [(SemanticRole.leg_r, legs[0]), (SemanticRole.leg_l, legs[1])]
        elif role in SIDES:
            split = sources._split_lr(img)
            if split:
                outputs = [(role, split[0]), (SIDES[role], split[1])]
        elif role in sources._LIMB_CANDIDATE_ROLES and layer not in whole:
            limb = sources._limb_split(img)
            if limb:
                outputs = [(limb[0], limb[2]), (limb[1], limb[3])]
        for out_role, part in outputs:
            file = f"{order:02d}_{out_role.value}.png"
            LAYER_OF[file[:-4]] = layer
            inked = part.getchannel("A").point(lambda a: 255 if a >= 64 else 0).getbbox()
            if inked:  # the rig's units: 0 to 1 across the picture, y up
                DRAWN[file[:-4]] = (inked[0] / part.width, 1 - inked[3] / part.height,
                                    inked[2] / part.width, 1 - inked[1] / part.height)
                import numpy as np
                solid = np.array(part.getchannel("A").crop(inked)) >= 64
                ys, xs = np.nonzero(solid)
                low = ys >= solid.shape[0] - max(1, round(0.04 * solid.shape[0]))  # its lowest rows
                MIDDLE[file[:-4]] = (((inked[0] + xs.mean()) / part.width, 1 - (inked[1] + ys.mean()) / part.height),
                                     ((inked[0] + xs[low].mean()) / part.width, 1 - inked[3] / part.height))
            part.save(os.path.join(dst, file))
            cell = sharp_cell(part, *copies[layer]) if layer in copies else None
            if cell and cell[2] <= SHARP_SAME:
                SHARP[file[:-4]] = cell[:2]
                sharp.append(layer)
            elif cell:
                changed.append(f"{layer} ({cell[2]:.2f} apart)")
            print(f"   {file:24} {layer}" + (f"  ({1 / copies[layer][2][0]:.1f} times as sharp)" if file[:-4] in SHARP else ""))
            order += 1
    if copies:
        print(f"   in the texture at the head pass's own size: {', '.join(dict.fromkeys(sharp)) or 'none'}")
    if changed:
        print(f"   changed since the head pass, so at her frame's size: {', '.join(dict.fromkeys(changed))}")
    return dst


def build(name):
    out = out_dir(name)
    print(f"{name}: layers")
    layers = write_layers(name)
    model = os.path.join(out, "model")
    shutil.rmtree(model, ignore_errors=True)
    i2l_tool("emit_cubism_bundle").emit_bundle(Path(layers), Path(model))
    acting.write_acting(model, name)
    sway_hair(model)

    from image2live2d.backends.live2d.cmo3 import rig_to_cmo3
    rig = rig_from_stack(decompose.from_layer_dir(Path(layers)), name=name.replace("/", "-"))
    cmo3 = os.path.join(out, name.replace("/", "-") + ".cmo3")
    with open(cmo3, "wb") as f:
        f.write(rig_to_cmo3(rig, asset_root=Path(layers)))
    print(f"wrote {cmo3}")

    archive = acting.zip_model(name)
    print(f"wrote {archive} ({os.path.getsize(archive) // 1024} KB)")


# What her hair listens to. image2live2d swings each section from her head's turn and tilt alone,
# so with her head still her hair is still, though her body sways and she breathes all through her
# idle. Cubism's own sample models feed her body's sway and lean into each strand as well, at two
# thirds of the head's weight, and her body's bob into the hair's rise and fall. So do we.
HAIR_FROM_BODY = 40.0  # the weight of each of her body's moves on her hair (her head's are 60)


def sway_hair(model):
    """Add her body's moves to what drives her hair, in the model's physics file."""
    path = os.path.join(model, "model.physics3.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    with open(os.path.join(model, "model.cdi3.json"), encoding="utf-8") as f:
        hers = {p["Id"] for p in json.load(f)["Parameters"]}
    added = 0
    for setting in doc["PhysicsSettings"]:
        outs = [o["Destination"]["Id"] for o in setting["Output"]]
        if not all(o.startswith("ParamHair") for o in outs):
            continue
        there = {i["Source"]["Id"] for i in setting["Input"]}
        rise = all(o.endswith("V") for o in outs)  # a section's rise and fall, not its swing
        kind = setting["Input"][0]["Type"] if rise and setting["Input"] else None
        wanted = [("ParamBodyAngleY", kind or "Angle")] if rise else [("ParamBodyAngleX", "X"), ("ParamBodyAngleZ", "Angle")]
        for param, how in wanted:
            if param in hers and param not in there:
                setting["Input"].append({"Source": {"Target": "Parameter", "Id": param}, "Weight": HAIR_FROM_BODY,
                                         "Type": how, "Reflect": False})
                added += 1
    doc["Meta"]["TotalInputCount"] = sum(len(s["Input"]) for s in doc["PhysicsSettings"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    sections = sorted(o["Destination"]["Id"] for s in doc["PhysicsSettings"] for o in s["Output"]
                      if o["Destination"]["Id"].startswith("ParamHair") and not o["Destination"]["Id"].endswith("V"))
    print(f"hair: {len(sections)} sections that swing each by itself ({', '.join(sections)}); her body's sway moves them too")


COMMANDS = {"build": build}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]](sys.argv[2])
