"""What a built model can show: her expressions, emotion motions and taps, written as files beside
her model (rig.py's build calls write_acting). Standard library only, so the viewer can read and
save a character's own expressions, and `acting` rewrites them without building her again.

usage:
  acting.py acting <name>     her expressions and motions written again into her built model (and
                              its zip), from the kit's and her own; about a second

Her own expressions are in her layers' live2d.json, under "expressions": each one there takes the
place of the kit's of the same name, or is a new one. A value is added to the parameter at rest;
{"times": v} multiplies it instead (for her eyes' open, so she can still blink):

  "expressions": {"happy": {"ParamMouthForm": 0.6, "ParamEyeLSmile": 1, "ParamEyeRSmile": 1,
                            "ParamEyeLOpen": {"times": 0}, "ParamEyeROpen": {"times": 0}}}

The viewer's "Change an expression" saves these for you. The emotion motions (Happy, Angry, Awkward,
Surprise) play her expressions, so they follow.
"""
import json, os, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402

# ---- Acting -----------------------------------------------------------------------------------
# What she can show, under the same names for every character, so the agent's prompts and the
# desktop app's wiring are written once. Three kinds, all files beside the model:
# - expressions (expressions/<name>.exp3.json): a face and pose she holds until told otherwise. The
#   agent app offers them to the model by name (<|ACT {"expression": {"name": "tired"}}|>).
# - emotion motions: the agent app plays the motion group named for each emotion the model writes
#   (AIRI, packages/stage-ui/src/constants/emotions.ts): Happy, Sad, Angry, Awkward, Think,
#   Surprise, Question, Curious, and Idle. Ours ease into an expression, hold it and ease out; the
#   rest borrow a motion image2live2d makes (Sad and Idle are its own, under those names).
# - taps: the agent app plays TapHead for a click or a stroke on her head and TapBody for one on
#   her body (packages/stage-ui-live2d/src/composables/live2d/touch.ts). Live2D's sample mao_pro
#   has big set pieces there; ours are small (first user's wish, 2026-11-10): a head pat she takes with an
#   embarrassed smile, and a poke she flinches at and pouts about.
# A value is added to the parameter; times(v) multiplies it (her eyes can still blink). A parameter
# a character doesn't have is left out: ParamMouthO, her "O" mouth (parts.py mouth-oh), is there
# only for a character who has one.
def times(value):
    return ("x", value)


EXPRESSIONS = {
    # Her eyes shut and smiling: the anime "^" (see SMILE_BEND in rig.py).
    "happy": {"ParamEyeLSmile": 1, "ParamEyeRSmile": 1, "ParamEyeLOpen": times(0), "ParamEyeROpen": times(0),
              "ParamMouthForm": 1, "ParamMouthOpenY": 0.2,
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
    # A sulk: cheeks puffed out, her pout mouth if she has one (else her own, turned down), brows
    # down and angled as in a glare, lids lowered, a flush, her head tipped.
    "pouting": {"ParamCheekPuff": 1, "ParamMouthPout": 1, "ParamMouthForm": -0.5, "ParamBrowLY": -0.5,
                "ParamBrowRY": -0.5, "ParamBrowLForm": 0.9, "ParamBrowRForm": 0.9, "ParamCheek": 0.6,
                "ParamEyeLOpen": times(0.8), "ParamEyeROpen": times(0.8), "ParamAngleZ": 5, "ParamAngleY": -4},
    # Small irises, brows up, mouth a little open (her "O" mouth if she has one), hands drawn up in
    # front of her.
    "scared": {"ParamEyeBallForm": -1, "ParamBrowLY": 0.9, "ParamBrowRY": 0.9, "ParamBrowLForm": -0.7,
               "ParamBrowRForm": -0.7, "ParamMouthOpenY": 0.3, "ParamMouthO": 1, "ParamMouthForm": -0.7, "ParamAngleY": 4,
               "ParamArmLA": 4, "ParamArmLB": -9, "ParamArmRA": 4, "ParamArmRB": -9},
    # Brows high, an "O" mouth open (her "O" mouth if she has one), head back a little.
    "surprised": {"ParamBrowLY": 1, "ParamBrowRY": 1, "ParamBrowLForm": -0.3, "ParamBrowRForm": -0.3,
                  "ParamMouthOpenY": 0.55, "ParamMouthO": 1, "ParamEyeBallForm": -0.35, "ParamAngleY": 6,
                  "ParamBodyAngleY": 2},
}
# group -> the expression it plays (Surprise was image2live2d's own until her "O" mouth, 2026-11-13)
EMOTIONS = {"Happy": "happy", "Angry": "angry", "Awkward": "blushing", "Surprise": "surprised"}
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
        "ParamEyeLSmile": [(0, 0), (0.3, 1), (1.9, 1), (2.3, 0)],  # shut as a "^"
        "ParamEyeRSmile": [(0, 0), (0.3, 1), (1.9, 1), (2.3, 0)],
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
# Our own Smile, in place of image2live2d's, which raised ParamEye?Smile with her eyes open: they
# now only narrow then, and its smile peaked so briefly that eyes shut along with it stopped
# half-way, a squashed slit (first user, 2026-11-13: "smile eye doesn't seem to display
# correctly"). Her eyes shut quickly, as in a blink, into the "^", hold, and open.
SMILES = {
    "Smile": {
        "ParamEyeLOpen": [(0, 1), (0.2, 0), (1.3, 0), (1.55, 1)],
        "ParamEyeROpen": [(0, 1), (0.2, 0), (1.3, 0), (1.55, 1)],
        "ParamEyeLSmile": [(0, 0), (0.15, 1), (1.35, 1), (1.6, 0)],
        "ParamEyeRSmile": [(0, 0), (0.15, 1), (1.35, 1), (1.6, 0)],
        "ParamMouthForm": [(0, 0), (0.3, 1), (1.3, 1), (1.7, 0)],
        "ParamCheek": [(0, 0), (0.35, 0.4), (1.3, 0.4), (1.7, 0)],
    },
}
RESTS_AT_ONE = ("ParamEyeLOpen", "ParamEyeROpen")  # every other parameter here rests at 0
EXPRESSION_NAME = r"[a-z][a-z0-9_-]{0,30}"
PARAMETER = r"Param[A-Za-z0-9_]{1,40}"


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


# ---- Hers -------------------------------------------------------------------------------------

def settings_path(name):
    """Her layers' live2d.json (akane/full -> <characters>/akane/layers/full/live2d.json)."""
    who, _, pose = name.partition("/")
    return kit.characters(who, "layers", *([pose] if pose else []), "live2d.json")


def settings(name):
    path = settings_path(name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def as_json(pose):
    """An expression as live2d.json holds it: times(v) as {"times": v}."""
    return {pid: {"times": v[1]} if isinstance(v, tuple) else v for pid, v in pose.items()}


def from_json(pose):
    return {pid: times(v["times"]) if isinstance(v, dict) else v for pid, v in pose.items()}


def expressions_of(name=None):
    """The kit's expressions with hers in place of any of the same name, and hers that are new."""
    out = dict(EXPRESSIONS)
    for exp, pose in ((settings(name).get("expressions") or {}) if name else {}).items():
        if isinstance(pose, dict):
            out[exp] = from_json(pose)
    return out


def check_pose(pose):
    """A pose sent from the viewer, checked: {Param...: number, or {"times": number}}."""
    import re
    if not isinstance(pose, dict) or not 0 < len(pose) <= 60:
        raise ValueError("an expression is 1 to 60 parameters")
    for pid, v in pose.items():
        if not re.fullmatch(PARAMETER, pid):
            raise ValueError(f"not a parameter: {pid[:40]}")
        n = v.get("times") if isinstance(v, dict) and set(v) == {"times"} else v
        if isinstance(n, bool) or not isinstance(n, (int, float)) or not -100 <= n <= 100:
            raise ValueError(f"{pid}: a number, or {{\"times\": a number}}")
    return pose


def save_expression(name, exp, pose):
    """Her own `exp` (live2d.json), or back to the kit's with pose None. Keeps the rest of the file."""
    import re
    if not re.fullmatch(EXPRESSION_NAME, exp):
        raise ValueError("an expression's name: small letters, digits, - and _, starting with a letter")
    path = settings_path(name)
    doc = settings(name)
    mine = doc.setdefault("expressions", {})
    if pose is None:
        mine.pop(exp, None)
        if not mine:
            doc.pop("expressions")
    else:
        mine[exp] = check_pose(pose)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ---- Writing them -------------------------------------------------------------------------------

def out_dir(name):
    return kit.out("live2d", name.replace("/", "-"))


def write_acting(model, name=None):
    """Add the expressions, emotion motions and taps to a built model: the kit's, and hers."""
    path = os.path.join(model, "model.model3.json")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    with open(os.path.join(model, "model.cdi3.json"), encoding="utf-8") as f:
        hers = {p["Id"] for p in json.load(f)["Parameters"]}
    motions = doc["FileReferences"]["Motions"]
    os.makedirs(os.path.join(model, "expressions"), exist_ok=True)
    expressions = expressions_of(name)

    def save(file, content):
        with open(os.path.join(model, file), "w", encoding="utf-8") as f:
            json.dump(content, f, indent=1)

    doc["FileReferences"]["Expressions"] = []
    for exp, pose in expressions.items():
        save(f"expressions/{exp}.exp3.json", {"Type": "Live2D Expression", "FadeInTime": 0.4, "FadeOutTime": 0.5, "Parameters": [
            {"Id": pid, "Value": v[1] if isinstance(v, tuple) else v, "Blend": "Multiply" if isinstance(v, tuple) else "Add"}
            for pid, v in pose.items() if pid in hers]})
        doc["FileReferences"]["Expressions"].append({"Name": exp, "File": f"expressions/{exp}.exp3.json"})
    there, back, done = EMOTION_TIMES
    for group, exp in EMOTIONS.items():
        lanes = {}
        for pid, v in expressions[exp].items():
            rest = 1.0 if pid in RESTS_AT_ONE else 0.0
            value = rest * v[1] if isinstance(v, tuple) else rest + v
            if pid in hers:
                lanes[pid] = [(0, rest), (there, value), (back, value), (done, rest)]
        if lanes:
            save(f"model.{exp}.motion3.json", motion(lanes))
            motions[group] = [{"File": f"model.{exp}.motion3.json"}]
    for group, lanes in {**TAPS, **SMILES}.items():
        save(f"model.{group.lower()}.motion3.json", motion({pid: keys for pid, keys in lanes.items() if pid in hers}))
        motions[group] = [{"File": f"model.{group.lower()}.motion3.json"}]
    for group, file in BORROWED.items():
        file = f"model.{file}.motion3.json"
        if group not in motions and os.path.exists(os.path.join(model, file)):
            motions[group] = [{"File": file}]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    if name:  # which character this model is, for the viewer's "Change an expression"
        with open(os.path.join(os.path.dirname(model), "character.json"), "w", encoding="utf-8") as f:
            json.dump({"name": name}, f)


def zip_model(name):
    """Her model folder as <out>/live2d/<name>.zip, for an app's model import."""
    model = os.path.join(out_dir(name), "model")
    archive = out_dir(name) + ".zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in os.walk(model):
            for file in files:
                path = os.path.join(folder, file)
                z.write(path, os.path.relpath(path, model))
    return archive


def act(name):
    model = os.path.join(out_dir(name), "model")
    if not os.path.exists(os.path.join(model, "model.model3.json")):
        sys.exit(f"{name}: no model yet: `live2d.py build` first")
    write_acting(model, name)
    archive = zip_model(name)
    mine = sorted((settings(name).get("expressions") or {}))
    print(f"{name}: expressions and motions written again" + (f"; hers: {', '.join(mine)}" if mine else "; all the kit's own")
          + f"\nwrote {archive} ({os.path.getsize(archive) // 1024} KB). Reload the viewer's page.")


def character_of(slug):
    """The character a built model is (akane-full -> akane/full), from the note write_acting leaves."""
    path = kit.out("live2d", slug, "character.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("name")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "acting":
        sys.exit(__doc__)
    act(sys.argv[2])
