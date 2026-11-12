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
  closed line out and the drawn open mouth in, growing it from 40% of its height to all of it
  (see mouth_swap): image2live2d's own open pulls the lips apart in proportion to their height, and
  a drawn closed mouth is a line a few pixels high, so it hardly opened (2026-11-10).

Her stockinged legs (legwear) go in as two legs, so each knee can bend, and her lashes and closed
eyes go over her irises (see drawing_order).

Her blush is the kit's own (blush.py): her `blush` layer if parts.py made one, else style 1 drawn
here from her eyes, so image2live2d paints none. Its mesh covers all of it (see soft_mesh).

How she moves is ours, and so is the .moc3's writing (see "The rig" below): her head's turn and nod
(each part of her face sliding a little, her irises doing most of the looking), her irises cut off
at the edge of her eyes, her body's sway, bob, lean and breath with her feet on the floor, arms
that lift and bend at the elbow, and knees that bend.

<name> can be a character's other drawing, akane/working, as in layers.py."""
import importlib.util, json, math, os, shutil, sys, zipfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
from image2live2d.irr.schema import Keyform, Parameter, SemanticRole
from image2live2d import pipeline
from image2live2d.pipeline import rig_from_stack

LEFT_OUT = set()
ROLES = {
    "eye_close": SemanticRole.eye_closed_l,
    "ears": SemanticRole.ear_l,
    "mouth_close": SemanticRole.mouth,
    "mouth_open": SemanticRole.mouth_cavity,
}
SHUT_HEIGHT = 0.4  # the drawn open mouth's height, as a share of its own, as it starts to fade in
_mouth_open = author._mouth_open


def mouth_swap(param_id, lips, cavity, open_fn):
    """ParamMouthOpenY as a swap, as image2live2d does a blink: her closed line at 0, her drawn open
    mouth at 1, crossfading between and the open mouth growing as it shows."""
    if not cavity:
        return _mouth_open(param_id, lips, cavity, open_fn)
    shut = Keyform(value=0.0,
                   mesh_offsets={**{pid: author._zeros(m) for pid, m in lips},
                                 **{pid: author._collapse_vertical(m, 1 - SHUT_HEIGHT) for pid, m in cavity}},
                   opacity_overrides={**{pid: 1.0 for pid, _ in lips}, **{pid: 0.0 for pid, _ in cavity}})
    opened = Keyform(value=1.0,
                     mesh_offsets={pid: author._zeros(m) for pid, m in lips + cavity},
                     opacity_overrides={**{pid: 0.0 for pid, _ in lips}, **{pid: 1.0 for pid, _ in cavity}})
    return author._set_keyforms(param_id, [shut, opened])


author._mouth_open = mouth_swap

_build_mesh = mesh_build.build_mesh


def soft_mesh(layer, **how):
    """A blush's mesh over all of it. image2live2d lays a part's mesh over the box of its solid
    pixels (alpha 64 and up), which keeps a decomposer's stray specks out of it; a blush is soft all
    the way to nothing, so that box cut it off in a rectangle with hard edges (its first user, 2026-11-12:
    "cheeks have hard cut offs"). Its mesh here is a whole lattice over the box of everything the
    texture atlas keeps of it (alpha above 8), the same box the atlas cuts."""
    if layer.semantic_role is not SemanticRole.blush:
        return _build_mesh(layer, **how)
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
    images = {}
    for layer in info["order"]:
        if layer not in LEFT_OUT:
            img = Image.open(os.path.join(src, "parts", layer + ".png")).convert("RGBA")
            # A blush is faint and soft on purpose: the cleaning would take its edge and its strokes.
            images[layer] = img if layer == "blush" else sources.drop_specks(sources._clean_alpha(img))
    for under, over in tucked.items():
        images[under] = tuck(images[under], images[over])
    names = drawing_order(info["order"], tucked)
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
            print(f"   {file:24} {layer}")
            order += 1
    return dst


def build(name):
    out = out_dir(name)
    print(f"{name}: layers")
    layers = write_layers(name)
    model = os.path.join(out, "model")
    shutil.rmtree(model, ignore_errors=True)
    i2l_tool("emit_cubism_bundle").emit_bundle(Path(layers), Path(model))
    write_acting(model)

    from image2live2d.backends.live2d.cmo3 import rig_to_cmo3
    rig = rig_from_stack(decompose.from_layer_dir(Path(layers)), name=name.replace("/", "-"))
    cmo3 = os.path.join(out, name.replace("/", "-") + ".cmo3")
    with open(cmo3, "wb") as f:
        f.write(rig_to_cmo3(rig, asset_root=Path(layers)))
    print(f"wrote {cmo3}")

    archive = out + ".zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in os.walk(model):
            for file in files:
                path = os.path.join(folder, file)
                z.write(path, os.path.relpath(path, model))
    print(f"wrote {archive} ({os.path.getsize(archive) // 1024} KB)")


# ---- Acting -----------------------------------------------------------------------------------
# What she can show, under the same names for every character, so the agent's prompts and the
# desktop app's wiring are written once. Three kinds, all files beside the model:
# - expressions (expressions/<name>.exp3.json): a face and pose she holds until told otherwise. The
#   agent app offers them to the model by name (<|ACT {"expression": {"name": "tired"}}|>).
# - emotion motions: the agent app plays the motion group named for each emotion the model writes
#   (AIRI, packages/stage-ui/src/constants/emotions.ts): Happy, Sad, Angry, Awkward, Think,
#   Surprise, Question, Curious, and Idle. Ours ease into an expression, hold it and ease out; the
#   rest borrow a motion image2live2d makes (Sad, Surprise and Idle are its own, under those names).
# - taps: the agent app plays TapHead for a click or a stroke on her head and TapBody for one on
#   her body (packages/stage-ui-live2d/src/composables/live2d/touch.ts). Live2D's sample mao_pro
#   has big set pieces there; ours are small (first user's wish, 2026-11-10): a head pat she takes with an
#   embarrassed smile, and a poke she flinches at and pouts about.
# A value is added to the parameter; times(v) multiplies it (her eyes can still blink). A parameter
# a character doesn't have is left out.
def times(value):
    return ("x", value)


EXPRESSIONS = {
    "happy": {"ParamEyeLSmile": 1, "ParamEyeRSmile": 1, "ParamMouthForm": 1, "ParamMouthOpenY": 0.2,
              "ParamBrowLY": 0.4, "ParamBrowRY": 0.4, "ParamCheek": 0.3, "ParamAngleZ": 5},
    "tired": {"ParamEyeLOpen": times(0.55), "ParamEyeROpen": times(0.55), "ParamBrowLY": -0.4, "ParamBrowRY": -0.4,
              "ParamBrowLForm": -0.6, "ParamBrowRForm": -0.6, "ParamMouthForm": -0.35, "ParamEyeBallY": -0.5,
              "ParamAngleY": -14, "ParamAngleZ": -5, "ParamBodyAngleY": -6},
    "blushing": {"ParamCheek": 1, "ParamMouthForm": 0.35, "ParamEyeBallX": 0.7, "ParamEyeBallY": -0.5,
                 "ParamBrowLY": 0.15, "ParamBrowRY": 0.15, "ParamBrowLForm": -0.5, "ParamBrowRForm": -0.5,
                 "ParamEyeLOpen": times(0.85), "ParamEyeROpen": times(0.85), "ParamAngleX": -8, "ParamAngleY": -6,
                 "ParamAngleZ": 4},
    # Cute anime angry: a pout with flushed cheeks, chin down, hands on her hips.
    "angry": {"ParamBrowLY": -0.6, "ParamBrowRY": -0.6, "ParamBrowLForm": 1, "ParamBrowRForm": 1,
              "ParamMouthForm": -0.8, "ParamCheek": 0.5, "ParamEyeLOpen": times(0.85), "ParamEyeROpen": times(0.85),
              "ParamAngleY": -6, "ParamEyeBallY": 0.3, "ParamArmLA": 10, "ParamArmLB": -10, "ParamArmRA": 10,
              "ParamArmRB": -10},
    # Small irises, brows up, mouth a little open, hands drawn up in front of her.
    "scared": {"ParamEyeBallForm": -1, "ParamBrowLY": 0.9, "ParamBrowRY": 0.9, "ParamBrowLForm": -0.7,
               "ParamBrowRForm": -0.7, "ParamMouthOpenY": 0.3, "ParamMouthForm": -0.7, "ParamAngleY": 4,
               "ParamArmLA": 4, "ParamArmLB": -9, "ParamArmRA": 4, "ParamArmRB": -9},
}
EMOTIONS = {"Happy": "happy", "Angry": "angry", "Awkward": "blushing"}  # group -> the expression it plays
BORROWED = {"Think": "brow_form", "Question": "head_roll", "Curious": "look"}  # group -> image2live2d's motion
EMOTION_TIMES = (0.35, 2.5, 3.2)  # seconds: there, starts back, back
# Each parameter's keys as (seconds, value), eased between; every one starts and ends at rest.
TAPS = {
    "TapHead": {  # a pat: her head dips under the hand twice, eyes shut, blushing, a wavering smile
        "ParamAngleY": [(0, 0), (0.25, -9), (0.55, -5), (0.85, -10), (1.15, -5), (1.45, -9), (1.9, -6), (2.5, 0)],
        "ParamAngleZ": [(0, 0), (0.4, 4), (1.9, 3), (2.5, 0)],
        "ParamBodyAngleY": [(0, 0), (0.3, -4), (0.6, -2), (0.9, -4), (1.2, -2), (2.4, 0)],
        "ParamEyeLOpen": [(0, 1), (0.3, 0), (1.9, 0), (2.3, 1)],
        "ParamEyeROpen": [(0, 1), (0.3, 0), (1.9, 0), (2.3, 1)],
        "ParamCheek": [(0, 0), (0.4, 1), (2.0, 1), (2.6, 0)],
        "ParamMouthForm": [(0, 0), (0.35, 0.7), (0.9, 0.4), (1.3, 0.75), (1.8, 0.45), (2.5, 0)],
        "ParamBrowLY": [(0, 0), (0.3, -0.3), (1.9, -0.3), (2.4, 0)],
        "ParamBrowRY": [(0, 0), (0.3, -0.3), (1.9, -0.3), (2.4, 0)],
        "ParamBrowLForm": [(0, 0), (0.3, -0.7), (1.9, -0.7), (2.4, 0)],
        "ParamBrowRForm": [(0, 0), (0.3, -0.7), (1.9, -0.7), (2.4, 0)],
    },
    "TapBody": {  # a poke: she flinches with a start, then pouts about it
        "ParamBodyAngleX": [(0, 0), (0.12, -7), (0.4, 3), (0.65, -1), (0.9, 0)],
        "ParamBodyAngleZ": [(0, 0), (0.14, -4), (0.45, 1.5), (0.8, 0)],
        "ParamAngleY": [(0, 0), (0.12, 8), (0.7, 0)],
        "ParamArmLB": [(0, 0), (0.12, 3), (0.6, 0)],
        "ParamArmRB": [(0, 0), (0.12, 3), (0.6, 0)],
        "ParamBrowLY": [(0, 0), (0.1, 1), (0.5, 1), (0.9, -0.3), (1.4, -0.3), (1.7, 0)],
        "ParamBrowRY": [(0, 0), (0.1, 1), (0.5, 1), (0.9, -0.3), (1.4, -0.3), (1.7, 0)],
        "ParamEyeBallForm": [(0, 0), (0.1, -0.8), (0.45, -0.8), (0.9, 0)],
        "ParamMouthOpenY": [(0, 0), (0.12, 0.6), (0.4, 0.5), (0.75, 0)],
        "ParamMouthForm": [(0, 0), (0.7, 0), (0.95, -0.7), (1.4, -0.7), (1.7, 0)],
        "ParamBrowLForm": [(0, 0), (0.7, 0), (0.95, 0.7), (1.4, 0.7), (1.7, 0)],
        "ParamBrowRForm": [(0, 0), (0.7, 0), (0.95, 0.7), (1.4, 0.7), (1.7, 0)],
        "ParamCheek": [(0, 0), (0.7, 0), (1.0, 0.5), (1.4, 0.5), (1.7, 0)],
    },
}
RESTS_AT_ONE = ("ParamEyeLOpen", "ParamEyeROpen")  # every other parameter here rests at 0


def motion(lanes):
    """A .motion3.json from {parameter id: [(seconds, value), ...]}, eased between the keys the way
    image2live2d's own motions are (flat-ended Bezier segments)."""
    curves, segments, points = [], 0, 0
    for param_id, keys in lanes.items():
        line = [keys[0][0], keys[0][1]]
        for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
            third = (t1 - t0) / 3
            line += [1, round(t0 + third, 4), v0, round(t1 - third, 4), v1, t1, v1]
        curves.append({"Target": "Parameter", "Id": param_id, "Segments": line})
        segments += len(keys) - 1
        points += 1 + 3 * (len(keys) - 1)
    return {"Version": 3,
            "Meta": {"Duration": max(keys[-1][0] for keys in lanes.values()), "Fps": 30.0, "Loop": False,
                     "AreBeziersRestricted": True, "CurveCount": len(curves), "TotalSegmentCount": segments,
                     "TotalPointCount": points, "UserDataCount": 0, "TotalUserDataSize": 0,
                     "FadeInTime": 0.25, "FadeOutTime": 0.4},
            "Curves": curves}


def write_acting(model):
    """Add the expressions, emotion motions and taps to a built model."""
    path = os.path.join(model, "model.model3.json")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    with open(os.path.join(model, "model.cdi3.json"), encoding="utf-8") as f:
        hers = {p["Id"] for p in json.load(f)["Parameters"]}
    motions = doc["FileReferences"]["Motions"]
    os.makedirs(os.path.join(model, "expressions"), exist_ok=True)

    def save(file, content):
        with open(os.path.join(model, file), "w", encoding="utf-8") as f:
            json.dump(content, f, indent=1)

    doc["FileReferences"]["Expressions"] = []
    for name, pose in EXPRESSIONS.items():
        save(f"expressions/{name}.exp3.json", {"Type": "Live2D Expression", "FadeInTime": 0.4, "FadeOutTime": 0.5, "Parameters": [
            {"Id": pid, "Value": v[1] if isinstance(v, tuple) else v, "Blend": "Multiply" if isinstance(v, tuple) else "Add"}
            for pid, v in pose.items() if pid in hers]})
        doc["FileReferences"]["Expressions"].append({"Name": name, "File": f"expressions/{name}.exp3.json"})
    there, back, done = EMOTION_TIMES
    for group, name in EMOTIONS.items():
        lanes = {}
        for pid, v in EXPRESSIONS[name].items():
            rest = 1.0 if pid in RESTS_AT_ONE else 0.0
            value = rest * v[1] if isinstance(v, tuple) else rest + v
            if pid in hers:
                lanes[pid] = [(0, rest), (there, value), (back, value), (done, rest)]
        save(f"model.{name}.motion3.json", motion(lanes))
        motions[group] = [{"File": f"model.{name}.motion3.json"}]
    for group, lanes in TAPS.items():
        save(f"model.{group.lower()}.motion3.json", motion({pid: keys for pid, keys in lanes.items() if pid in hers}))
        motions[group] = [{"File": f"model.{group.lower()}.motion3.json"}]
    for group, name in BORROWED.items():
        file = f"model.{name}.motion3.json"
        if group not in motions and os.path.exists(os.path.join(model, file)):
            motions[group] = [{"File": file}]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


COMMANDS = {"build": build}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]](sys.argv[2])
