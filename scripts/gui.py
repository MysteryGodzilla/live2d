"""The kit's GUI: a page on this PC with each step of the README as a button. It only ever runs the
kit's own commands (`live2d.py <step> <name> ...`, the same as typing them) and shows what they print.
Standard library only.

usage:
  gui.py [port]         (8780 unless given) then open http://127.0.0.1:<port>/

It listens on this PC only, and a POST has to come from its own page. It runs one command at a time,
from a fixed list of steps, each with its arguments checked: a character's name is letters, digits,
dashes and underscores; a number is a number; a picture is one of the project's own. Nothing typed
in the page is ever run as it is. The page shows each command before it runs it, and the GPU steps
(draw, cutout, upscale, split, ComfyUI's start) need a second click.

The viewer (view.py) is served from the same address, under /live2d/, and shown in the page's last step.
Pictures come from the project only: /files/characters/... and /files/out/....
"""
import json, os, re, subprocess, sys, threading, time
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comfy
import kit
import view
import live2d

PAGE = os.path.join(kit.SCRIPTS, "gui", "index.html")
LIVE2D = os.path.join(kit.KIT, "live2d.py")
NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")
ROUND = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,40}")
CHARACTER = re.compile(r"[a-z0-9][a-z0-9_-]*(:[A-Za-z0-9_-]{1,30})?")
SEEDS = re.compile(r"[0-9]{1,9}(,[0-9]{1,9}){0,15}")
STRENGTHS = re.compile(r"[01]?\.?[0-9]{1,3}(,[01]?\.?[0-9]{1,3}){0,5}")
IRIS_STYLE = re.compile(r"[0-9]{1,2}(,[0-9]{1,2})?")
COLOUR = re.compile(r"(#[0-9a-fA-F]{6}|[a-zA-Z]{3,20})(, ?(#[0-9a-fA-F]{6}|[a-zA-Z]{3,20}))?")
NEW_LAYER = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_ -]{0,29}")
PICTURE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.(png|jpg)")
GPU_STEPS = ("draw", "cutout", "upscale", "split")


class Refuse(Exception):
    """A request the page may not make, with the reason in plain words."""


# ---- the fixed list of steps -------------------------------------------------------------------

def text(args, key, what, pattern=None, low=1, high=100):
    value = args.get(key)
    if not isinstance(value, str) or not low <= len(value) <= high:
        raise Refuse(f"{what}: write it as text")
    if pattern is not None and not pattern.fullmatch(value):
        raise Refuse(f"{what}: not an allowed form")
    return value


def number(args, key, what, low, high, whole=False):
    value = args.get(key)
    try:
        if isinstance(value, bool):
            raise ValueError
        value = int(value) if whole else float(value)
    except (TypeError, ValueError):
        raise Refuse(f"{what}: write a number") from None
    if not low <= value <= high:
        raise Refuse(f"{what}: between {low:g} and {high:g}")
    return value


def character(name):
    if not isinstance(name, str) or not NAME.fullmatch(name) or len(name) > 40:
        raise Refuse("A character's name is lower-case letters, digits, dashes and underscores")
    return name


def her_layers(name):
    try:
        return live2d.status_data(name)["order"]
    except Exception:
        return []


def layer(args, key, name):
    value = args.get(key)
    if not isinstance(value, str) or value not in her_layers(name):
        raise Refuse(f"{key}: pick one of her layers")
    return value


def head_psd(args, name):
    folder = live2d.paths(name)["layers"]
    value = args.get("psd")
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*head[A-Za-z0-9._-]*\.psd", value) \
            or not os.path.isfile(os.path.join(folder, value)):
        raise Refuse("psd: pick one of the head PSDs in her layers folder (the head pass makes it)")
    return os.path.join(folder, value), os.path.join(folder, "head-crop.json")


def relative(path):
    """A path as the commands show it: from the project's folder, with forward slashes."""
    try:
        return os.path.relpath(path, kit.project()).replace("\\", "/")
    except ValueError:
        raise Refuse("That file is on another drive than the project") from None


def inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root + os.sep)


def build_command(req):
    """The arguments after live2d.py for one request, or a Refuse. The only place a command is made."""
    if not isinstance(req, dict):
        raise Refuse("The request is not what the page sends")
    step, args = req.get("step"), req.get("args") or {}
    if not isinstance(args, dict):
        raise Refuse("The arguments are not what the page sends")
    name = req.get("name")
    if step == "check":
        return ["check"], False
    if step == "comfy":
        action = args.get("action")
        if action not in ("start", "stop", "status"):
            raise Refuse("ComfyUI: start, stop or status")
        if action != "status":
            s = comfy.state()
            if action == "start" and s["running"]:
                raise Refuse("Not starting another: " + comfy.describe(s))
            if action == "stop" and s["running"] and not s["ours"]:
                raise Refuse("Not stopping it: " + comfy.describe(s))
            if action == "stop" and not s["running"] and not s["stale"]:
                raise Refuse("ComfyUI isn't running: nothing to stop")
        return ["comfy", action], action == "start"
    if step == "draw":
        name = name or None
        rnd = text(args, "round", "Round name", ROUND, 1, 41)
        seeds = text(args, "seeds", "Seeds", SEEDS, 1, 200)
        grey = ["--background"] if args.get("background") is True else []
        if args.get("look"):
            look = text(args, "look", "Look", None, 5, 1500)
            if look.startswith("-") or any(ord(c) < 32 for c in look):
                raise Refuse("Look: plain words, not starting with a dash")
            return ["draw", rnd, "--look", look, "--seeds", seeds] + grey, True
        who = text(args, "character", "Character", CHARACTER, 1, 72) if args.get("character") else (name and character(name))
        if not who:
            raise Refuse("Write a look, or pick a character from the looks file")
        return ["draw", rnd, "--character", who, "--seeds", seeds] + grey, True
    if step == "pick":
        name = character(name)
        picture = args.get("picture")
        if not isinstance(picture, str) or picture.count("/") != 1:
            raise Refuse("Picture: one of a round's pictures")
        folder, file = picture.split("/")
        if not ROUND.fullmatch(folder) or not PICTURE.fullmatch(file):
            raise Refuse("Picture: one of a round's pictures")
        full = os.path.join(kit.out(), folder, file)
        if not os.path.isfile(full) or not inside(full, kit.project()):
            raise Refuse("Picture: that picture is not in the project")
        return ["pick", name, relative(full)], False
    name = character(name)
    if step in ("status", "cutout", "upscale", "build"):
        return [step, name], step in ("cutout", "upscale")
    if step == "split":
        if args.get("mode") not in ("body", "head"):
            raise Refuse("Split: body or head")
        return ["split", name, args["mode"]], True
    if step == "parts":
        sub = args.get("command")
        if sub == "closed-eyes":
            return ["parts", sub, name], False
        if sub in ("mouth", "mouth-oh", "blush", "mouth-sheet", "blush-sheet", "mouth-line"):
            out = ["parts", sub, name]
            if sub in ("mouth", "mouth-oh", "blush") and args.get("style") not in (None, ""):
                out += ["--style", str(number(args, "style", "Style", 1, 99, whole=True))]
            # Size, place and tilt; each left out when it is what she has.
            ranges = {"mouth": MOUTH_RANGES, "mouth-oh": MOUTH_RANGES, "mouth-sheet": MOUTH_RANGES, "blush": BLUSH_RANGES,
                      "blush-sheet": BLUSH_RANGES, "mouth-line": LINE_RANGES}[sub]
            for key, low, high in ranges:
                if args.get(key) not in (None, ""):
                    out += [f"--{key}", f"{number(args, key, key.capitalize(), low, high):g}"]
            if sub == "mouth-line" and args.get("mode") in ("try", "back"):
                out = ["parts", sub, name, "--" + args["mode"]] + (out[3:] if args["mode"] == "try" else [])
            return out, False
        if sub == "mouth-pout":
            out = ["parts", sub, name]
            if args.get("mode") == "try":
                out.append("--try")
            elif args.get("style") not in (None, ""):
                out += ["--style", str(number(args, "style", "Style", 1, 9, whole=True))]
            for key, low, high in POUT_RANGES:
                if args.get(key) not in (None, ""):
                    out += [f"--{key}", f"{number(args, key, key.capitalize(), low, high):g}"]
            return out, False
        if sub in ("iris", "iris-sheet"):
            if sub == "iris" and args.get("mode") == "back":
                return ["parts", "iris", name, "--back"], False
            out = ["parts", sub, name]
            if sub == "iris" and args.get("style") not in (None, ""):
                out += ["--style", text(args, "style", "Iris", IRIS_STYLE, 1, 5)]
            if args.get("colour") not in (None, ""):
                out += ["--colour", text(args, "colour", "Colour", COLOUR, 1, 60)]
            for key, low, high in IRIS_RANGES:
                if args.get(key) not in (None, ""):
                    out += [f"--{key}", f"{number(args, key, key.capitalize(), low, high):g}"]
            if sub == "iris" and args.get("mirror") is True:
                out.append("--mirror")
            return out, False
        if sub == "eyes":
            mode = args.get("mode")
            if mode == "back":
                return ["parts", "eyes", name, "--back"], False
            if mode == "take":
                return ["parts", "eyes", name, str(number(args, "number", "Eyes", 1, 9999, whole=True))], False
            if mode == "clear":
                return ["parts", "eyes", name, "--clear"], False
            if mode != "try":
                raise Refuse("Eyes: try, take or back")
            out = ["parts", "eyes", name, "--try"]
            if args.get("seeds") not in (None, ""):
                out += ["--seeds", text(args, "seeds", "Seed", SEEDS, 1, 60)]
            if args.get("strength") not in (None, ""):
                strengths = text(args, "strength", "Strength", STRENGTHS, 1, 40)
                if any(not 0 < float(s) <= 1 for s in strengths.split(",")):
                    raise Refuse("Strength: numbers from 0 to 1, as 0.4,0.55")
                out += ["--strength", strengths]
            if args.get("colour") not in (None, ""):
                out += ["--colour", text(args, "colour", "Colour", COLOUR, 1, 60)]
            if args.get("iris_only") is True:
                out.append("--iris-only")
            return out, True
        raise Refuse("Parts: not a command the page runs")
    if step == "layers":
        sub = args.get("command")
        if sub == "check":
            return ["layers", "check", name], False
        if sub == "repair":
            names = args.get("layers")
            if not isinstance(names, list) or not 1 <= len(names) <= 12:
                raise Refuse("Repair: pick one or more of her layers")
            return ["layers", "repair", name] + [layer({"x": n}, "x", name) for n in names], False
        if sub == "lining":
            low, high = number(args, "low", "Light, from", 0, 1), number(args, "high", "Light, to", 0, 1)
            if low >= high:
                raise Refuse("Light: the first number is the lower one")
            return ["layers", "lining", name, layer(args, "layer", name), text(args, "new", "New layer", NEW_LAYER, 1, 30),
                    "--above", layer(args, "above", name), "--light", f"{low:g}", f"{high:g}"], False
        if sub == "strays":
            return ["layers", "strays", name, layer(args, "layer", name)], False
        if sub == "move":
            return ["layers", "move", name, layer(args, "layer", name), "--above", layer(args, "above", name)], False
        if sub == "under":
            return ["layers", "under", name, layer(args, "layer", name), layer(args, "over", name)], False
        if sub == "scale":
            return ["layers", "scale", name, f"{number(args, 'factor', 'Factor', 1, 4):g}"], False
        if sub == "head":
            psd, crop = head_psd(args, name)
            return ["layers", "head", name, relative(psd), relative(crop)], False
        if sub == "sharp":
            return ["layers", "sharp", name], False
        raise Refuse("Layers: not a command the page runs")
    raise Refuse("That is not a step the page runs")


def command_text(argv):
    return "python live2d.py " + " ".join(f'"{a}"' if (" " in a or not a) else a for a in argv)


# ---- one job at a time -------------------------------------------------------------------------

class Job:
    def __init__(self, ident, argv, step, name):
        self.id, self.argv, self.step, self.name = ident, argv, step, name
        self.output, self.code, self.stopped = "", None, False
        self.started, self.ended = time.time(), None
        self.lock = threading.Lock()
        env = dict(os.environ, PYTHONUTF8="1", PYTHONUNBUFFERED="1")
        extra = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        self.proc = subprocess.Popen([sys.executable, LIVE2D, *argv], cwd=kit.project(), env=env, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **extra)
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        import codecs
        decode = codecs.getincrementaldecoder("utf-8")("replace")
        while True:
            chunk = self.proc.stdout.read1(4096)
            if not chunk:
                break
            with self.lock:
                self.output = (self.output + decode.decode(chunk))[-400_000:]
        self.code = self.proc.wait()
        self.ended = time.time()

    @property
    def state(self):
        if self.ended is None:
            return "running"
        return "stopped" if self.stopped else ("done" if self.code == 0 else "failed")

    def stop(self):
        if self.ended is not None:
            return
        self.stopped = True
        try:
            if os.name == "nt":  # the command and what it started
                subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True)
            else:
                import signal
                os.killpg(self.proc.pid, signal.SIGTERM)
        except Exception:
            self.proc.kill()

    def data(self):
        with self.lock:
            output = self.output
        return {"id": self.id, "state": self.state, "step": self.step, "name": self.name, "command": command_text(self.argv),
                "code": self.code, "output": output, "started": self.started, "ended": self.ended}


class Jobs:
    def __init__(self):
        self.all, self.lock, self.count = {}, threading.Lock(), 0

    def running(self):
        return next((j for j in self.all.values() if j.state == "running"), None)

    def start(self, argv, step, name):
        with self.lock:
            busy = self.running()
            if busy:
                raise Refuse(f"Another step is running: {command_text(busy.argv)}. Wait for it, or stop it first.")
            self.count += 1
            job = Job(f"{self.count}-{int(time.time())}", argv, step, name)
            self.all[job.id] = job
            for old in sorted(self.all.values(), key=lambda j: j.started)[:-12]:
                self.all.pop(old.id, None)
            return job

    def last(self):
        return max(self.all.values(), key=lambda j: j.started, default=None)


JOBS = Jobs()


# ---- what the page shows -----------------------------------------------------------------------

CHECK = {"data": None, "busy": False, "at": 0}


def check_rows():
    """The check, computed in the background (it starts the other Pythons, which takes a few seconds)."""
    if CHECK["busy"]:
        return
    CHECK["busy"] = True

    def work():
        try:
            d = live2d.check_data()
            CHECK["data"] = {"project": d["project"], "found": d["found"], "gpu": d["gpu"],
                             "rows": [{"what": w.strip(), "ok": not p, "problem": p, "steps": s} for w, p, s in d["rows"]]}
        except Exception as e:  # shown as one row, not a crash
            CHECK["data"] = {"project": kit.project(), "found": True, "gpu": "", "rows": [
                {"what": "the check", "ok": False, "problem": f"it failed: {e}", "steps": ""}]}
        CHECK["busy"], CHECK["at"] = False, time.time()

    threading.Thread(target=work, daemon=True).start()


def fresh(url, file):
    """A picture's address with its time on it, so the browser fetches it again once it is redrawn
    (the same name each run; a page keeps a picture it has shown, whatever the server says)."""
    return f"{url}?v={int(os.path.getmtime(file) * 1000)}"


def url_for(kind, path):
    """A picture's address if it is there."""
    file = os.path.join(kit.characters() if kind == "characters" else kit.out(), *path.split("/"))
    return fresh(f"/files/{kind}/{path}", file) if os.path.isfile(file) else None


def pictures(name):
    slug = name + "-full"
    return {"drawing": url_for("characters", f"{name}/full/base.png"), "cutout": url_for("characters", f"{name}/full/cutout.png"),
            "twice": url_for("characters", f"{name}/full/base-2x.png"), "check": url_for("out", f"layers/{slug}-check.png"),
            "mouths": url_for("out", f"parts/{slug}-mouths.png"), "blushes": url_for("out", f"parts/{slug}-blushes.png"),
            "irises": url_for("out", f"parts/{slug}-irises.png"), "iris": url_for("out", f"parts/{slug}-iris.png"), "pouts": url_for("out", f"parts/{slug}-pouts.png"),
            "sheet": url_for("out", f"live2d/checks/{slug}-sheet.png")}


TILE = re.compile(r"([0-9]{1,2})-([a-z0-9-]+)\.png")


def choices(kind, name):
    """The open mouths or blushes to choose from, each with its picture: her own face's if her sheet
    was made (parts mouth-sheet / blush-sheet), else the kit's own on plain skin. And which one she
    has now, read from her layers' history."""
    own = os.path.join(kit.out("parts"), f"{name}-full-{kind}")
    kits = os.path.join(kit.SCRIPTS, kind, "previews")
    on_her = os.path.isdir(own) and any(TILE.fullmatch(f) for f in os.listdir(own))
    folder = own if on_her else kits
    tiles = []
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            m = TILE.fullmatch(f)
            if m:
                url = fresh(f"/files/out/parts/{name}-full-{kind}/{f}" if on_her else f"/kit/{kind}/previews/{f}", os.path.join(folder, f))
                tiles.append({"n": int(m.group(1)), "name": m.group(2).replace("-", " "), "url": url})
    tiles.sort(key=lambda t: t["n"])
    now_url = fresh(f"/files/out/parts/{name}-full-{kind}/now.png", os.path.join(own, "now.png")) \
        if on_her and os.path.isfile(os.path.join(own, "now.png")) else None
    return {"tiles": tiles, "on_her": on_her, "now": current(kind, name), "now_url": now_url,
            "adjust": kept(kind, name)}


MOUTH_RANGES = (("size", 0.3, 3), ("down", -0.3, 0.3), ("right", -0.3, 0.3), ("turn", -45, 45))
BLUSH_RANGES = (("size", 0.3, 3), ("in", -1, 1), ("down", -1, 1), ("turn", -60, 60))
LINE_RANGES = (("size", 0.5, 3), ("thick", 0.3, 4), ("dark", 0, 1))
POUT_RANGES = (("size", 0.4, 3), ("thick", 0.3, 4), ("down", -0.3, 0.3), ("right", -0.3, 0.3))
IRIS_RANGES = (("size", 0.5, 2), ("tall", 0.8, 1.6), ("down", -0.5, 0.5), ("right", -0.5, 0.5))
# What layers.json keeps for each (parts.py's MOUTH_KEY, BLUSH_KEY and LINE_KEY), and their plain values.
KEPT = {"mouths": ("open_mouth", {"size": 1.0, "down": 0.0, "right": 0.0, "turn": 0.0}),
        "blushes": ("blush_place", {"size": 1.0, "in": 0.0, "down": 0.0, "turn": 0.0}),
        "line": ("mouth_line", {"size": 1.0, "thick": 1.0, "dark": 0.35}),
        "irises": ("iris", {"size": 1.0, "tall": 1.0, "down": 0.0, "right": 0.0}),
        "pouts": ("pout_mouth", {"size": 1.0, "thick": 1.0, "down": 0.0, "right": 0.0})}


def kept(kind, name):
    """Her open mouth's, blush's or redrawn closed mouth's size and place, as layers.json keeps them."""
    key, plain = KEPT[kind]
    try:
        with open(os.path.join(live2d.paths(name)["layers"], "layers.json"), encoding="utf-8") as f:
            have = json.load(f).get(key) or {}
    except (OSError, ValueError):
        return dict(plain)
    return {k: float(have[k]) if isinstance(have.get(k), (int, float)) else v for k, v in plain.items()}


def oh_state(name):
    """Her "O" mouth (parts mouth-oh): whether she has one, and its kit style."""
    try:
        with open(os.path.join(live2d.paths(name)["layers"], "layers.json"), encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        return {"has": False, "now": None}
    now = None
    for change in reversed(info.get("changes", [])):
        m = re.search(r"mouth_oh from the kit's open mouth ([0-9]+)", change)
        if m:
            now = int(m.group(1))
            break
    return {"has": "mouth_oh" in info.get("order", []), "now": now}


def pout_state(name):
    """Her pout mouth (parts mouth-pout): whether she has one, its style, its size and place."""
    try:
        with open(os.path.join(live2d.paths(name)["layers"], "layers.json"), encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        info = {}
    style = (info.get("pout_mouth") or {}).get("style")
    return {"has": "mouth_pout" in info.get("order", []), "style": style if isinstance(style, int) else None,
            "adjust": kept("pouts", name)}


def iris_numbers(iris):
    """The numbers of the kit irises she has, found by their names where layers.json has them (the kit's
    irises may have been numbered again since), or None."""
    style, names = iris.get("style"), iris.get("names")
    if not isinstance(style, list) or not style:
        return None
    if isinstance(names, list) and names:
        folder = os.path.join(kit.SCRIPTS, "irises")
        found = {m.group(2): int(m.group(1)) for m in map(TILE.fullmatch, os.listdir(folder) if os.path.isdir(folder) else []) if m}
        return [found[n] for n in names if n in found] or None
    return [int(n) for n in style if isinstance(n, int)] or None


def iris_state(name):
    """Her iris from the kit (parts iris): whether she has one, which for each eye, its colour, and whether
    the second eye's is mirrored."""
    try:
        with open(os.path.join(live2d.paths(name)["layers"], "layers.json"), encoding="utf-8") as f:
            iris = json.load(f).get("iris") or {}
    except (OSError, ValueError):
        iris = {}
    style = iris_numbers(iris)
    return {"has": bool(iris), "style": style, "colour": iris.get("colour") or "", "mirror": bool(iris.get("mirror"))}


def eyes_state(name):
    """Her eyes (parts eyes): her drawing's seed, the candidates of the last try with their
    labels, and whether she has redrawn eyes now."""
    slug = name + "-full"
    seed, known = 1, False
    try:
        with open(os.path.join(kit.characters(name, "full", "base.json")), encoding="utf-8") as f:
            seed, known = int(json.load(f)["seed"]), True
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        with open(kit.out("parts", f"{slug}-eyes-try", "labels.json"), encoding="utf-8") as f:
            labels = json.load(f)
    except (OSError, ValueError):
        labels = {}
    tiles, folder = [], kit.out("parts", f"{slug}-eyes")
    if os.path.isdir(folder):
        for f in sorted(os.listdir(folder)):
            m = re.fullmatch(r"([0-9]{1,4})-[^/\\]+\.png", f)
            if m and m.group(1) in labels:
                url = fresh(f"/files/out/parts/{slug}-eyes/{quote(f)}", os.path.join(folder, f))
                tiles.append({"n": int(m.group(1)), "name": labels[m.group(1)].split(None, 1)[-1], "url": url})
    tiles.sort(key=lambda t: t["n"])
    now = os.path.join(folder, "now.png")
    return {"seed": seed, "seed_known": known, "tiles": tiles,
            "now_url": fresh(f"/files/out/parts/{slug}-eyes/now.png", now) if os.path.isfile(now) else None,
            "redrawn": os.path.isdir(os.path.join(live2d.paths(name)["layers"], "eyes-drawn"))}


def line_state(name):
    """Her closed mouth: whether it was drawn again (parts mouth-line), how, and its picture."""
    folder = live2d.paths(name)["layers"]
    return {"redrawn": os.path.isfile(os.path.join(folder, "mouth-close-drawn.png")), "adjust": kept("line", name),
            "picture": url_for("out", f"parts/{name}-full-mouth-line.png")}


def current(kind, name):
    """The number of the mouth or blush she has now, from her layers.json: None for a picture of
    your own or none at all. A character with no blush layer gets build's own, style 1."""
    try:
        with open(os.path.join(live2d.paths(name)["layers"], "layers.json"), encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, ValueError):
        return None
    if kind == "irises":
        style = iris_numbers(info.get("iris") or {})
        return style[0] if style else None
    pattern = r"mouth_open from the kit's open mouth ([0-9]+)" if kind == "mouths" else r"blush drawn: the kit's style ([0-9]+)"
    for change in reversed(info.get("changes", [])):
        if kind == "mouths" and "mouth_open" in change and "from" in change:
            m = re.search(pattern, change)
            return int(m.group(1)) if m else (1 if "the shared open mouth" in change else None)
        if kind == "blushes" and change.split(": ", 1)[-1].startswith("blush"):
            m = re.search(pattern, change)
            return int(m.group(1)) if m else None
    return 1 if kind == "blushes" and "blush" not in info.get("order", []) else None


def characters_found():
    folder = kit.characters()
    if not os.path.isdir(folder):
        return []
    return sorted(n for n in os.listdir(folder) if NAME.fullmatch(n) and os.path.isdir(os.path.join(folder, n)) and (
        os.path.isfile(os.path.join(folder, n, "full", "base.png")) or
        os.path.isfile(os.path.join(folder, n, "layers", "full", "layers.json"))))


def one_character(name):
    d = live2d.status_data(name)
    folder = d["paths"]["layers"]
    psds = sorted(f for f in os.listdir(folder) if f.endswith(".psd") and "head" in f) if os.path.isdir(folder) else []
    return {"name": name, "steps": [{"what": w, "done": done, "next": how} for w, done, how in d["steps"]], "next": d["next"],
            "layers": d["order"], "frame": d["frame"], "pictures": pictures(name), "head_psds": psds,
            "built": os.path.exists(d["paths"]["model"]), "model": name + "-full",
            "mouths": choices("mouths", name), "blushes": choices("blushes", name), "line": line_state(name), "oh": oh_state(name),
            "eyes": eyes_state(name), "irises": dict(choices("irises", name), **iris_state(name)), "pouts": pout_state(name)}


def rounds():
    """Each folder in the output that draw made: its contact sheet and pictures, newest first."""
    out, found = kit.out(), []
    if os.path.isdir(out):
        for n in os.listdir(out):
            path = os.path.join(out, n)
            if ROUND.fullmatch(n) and os.path.isfile(os.path.join(path, "prompts.txt")):
                pics = sorted(f for f in os.listdir(path) if PICTURE.fullmatch(f) and f != "sheet.jpg")
                found.append({"name": n, "mtime": os.path.getmtime(os.path.join(path, "prompts.txt")),
                              "sheet": f"/files/out/{n}/sheet.jpg" if os.path.isfile(os.path.join(path, "sheet.jpg")) else None,
                              "pictures": [{"file": f, "pick": f"{n}/{f}", "url": f"/files/out/{n}/{f}"} for f in pics]})
    return sorted(found, key=lambda r: -r["mtime"])


def looks():
    """The characters in the looks file, and the names of each one's looks."""
    try:
        with open(kit.looks_file(), encoding="utf-8") as f:
            found = json.load(f).get("characters", {})
        return {n: sorted(v.get("looks", {})) for n, v in found.items() if not n.startswith("_") and isinstance(v, dict)}
    except (OSError, ValueError):
        return {}


def comfy_state():
    """ComfyUI's state for the page: whether it answers, whose it is, and one line saying so."""
    s = comfy.state()
    return dict(s, line=comfy.describe(s))


def state(recheck=False):
    if recheck or CHECK["data"] is None:
        check_rows()
    chars = []
    for n in characters_found():
        try:
            chars.append(one_character(n))
        except Exception as e:
            chars.append({"name": n, "error": str(e), "steps": [], "layers": [], "pictures": {}, "head_psds": []})
    last = JOBS.last()
    return {"project": kit.project(), "kit": kit.KIT, "characters_folder": kit.characters(), "out_folder": kit.out(),
            "check": CHECK["data"] if CHECK["data"] and not (recheck and CHECK["busy"]) else {"pending": True},
            "characters": chars, "rounds": rounds(), "looks": looks(), "comfy": comfy_state(),
            "job": {"id": last.id, "state": last.state, "command": command_text(last.argv)} if last else None}


# ---- the server --------------------------------------------------------------------------------

FILE_PATTERNS = {
    "characters": re.compile(r"[a-z0-9][a-z0-9_-]*/[a-z0-9][a-z0-9_-]*/(base|cutout|base-2x)\.png"),
    "out": re.compile(r"(layers|parts|live2d/checks)/[A-Za-z0-9._-]+\.png|parts/[a-z0-9_-]+-full-(mouths|blushes|irises)/[a-z0-9-]+\.png"
                      r"|parts/[a-z0-9_-]+-full-eyes/[A-Za-z0-9._#,-]+\.png"  # an eye tile's name carries its colour words
                      r"|[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9._-]+\.(png|jpg)"),
}
KIT_PREVIEW = re.compile(r"/kit/(mouths|blushes|irises)/previews/([0-9]{1,2}-[a-z0-9-]+\.png)")


class Handler(view.Viewer):
    port = 0

    def json(self, status, data):
        self.send(status, json.dumps(data).encode(), view.TYPES[".json"])

    def host_ok(self):
        return self.headers.get("Host", "") in (f"127.0.0.1:{self.port}", f"localhost:{self.port}")

    def body(self):
        size = int(self.headers.get("Content-Length") or 0)
        if not 0 <= size < 100_000:
            raise Refuse("The request is too big")
        try:
            return json.loads(self.rfile.read(size) or b"{}")
        except ValueError:
            raise Refuse("The request is not JSON") from None

    def do_GET(self):
        if not self.host_ok():
            return self.send(403, b"this page answers on this PC's own address only")
        url = urlparse(self.path)
        path = url.path
        if path in ("/", "/index.html"):
            with open(PAGE, "rb") as f:
                return self.send(200, f.read(), view.TYPES[".html"])
        if path == "/api/state":
            return self.json(200, state(recheck="recheck" in parse_qs(url.query)))
        if path == "/api/comfy":  # cheap: one request to ComfyUI's own address, for the page's badge
            return self.json(200, comfy_state())
        m = re.fullmatch(r"/api/job/([0-9]+-[0-9]+)", path)
        if m:
            job = JOBS.all.get(m.group(1))
            return self.json(200, job.data()) if job else self.json(404, {"error": "No such job"})
        if path.startswith("/files/"):
            kind, _, rest = path[len("/files/"):].partition("/")
            rest = unquote(rest)
            parts = rest.split("/")
            if kind not in FILE_PATTERNS or any(p in ("", ".", "..") or "\\" in p or ":" in p for p in parts) \
                    or not FILE_PATTERNS[kind].fullmatch(rest):
                return self.send(404, b"not a picture of the project")
            return self.file(kit.characters() if kind == "characters" else kit.out(), rest)
        m = KIT_PREVIEW.fullmatch(path)
        if m:  # the kit's own previews of the mouths and blushes
            return self.file(os.path.join(kit.SCRIPTS, m.group(1), "previews"), m.group(2))
        if path == "/live2d" or path.startswith("/live2d/"):
            return view.Viewer.do_GET(self)
        self.send(404, b"not found")

    def do_POST(self):
        if not self.host_ok() or self.headers.get("Origin") != "http://" + self.headers.get("Host", ""):
            return self.send(403, b"posts only from this page")
        path = urlparse(self.path).path
        if path.startswith("/live2d/"):
            return view.Viewer.do_POST(self)
        try:
            if path in ("/api/run", "/api/preview"):
                req = self.body()
                argv, gpu = build_command(req)
                if path == "/api/preview":
                    return self.json(200, {"command": command_text(argv), "gpu": gpu})
                if gpu and req.get("gpu_ok") is not True:
                    raise Refuse("This step uses the graphics card. Confirm it in the page first.")
                job = JOBS.start(argv, req["step"], req.get("name"))
                return self.json(200, {"id": job.id, "command": command_text(argv)})
            m = re.fullmatch(r"/api/stop/([0-9]+-[0-9]+)", path)
            if m:
                job = JOBS.all.get(m.group(1))
                if not job:
                    raise Refuse("No such job")
                job.stop()
                return self.json(200, {"id": job.id, "state": job.state})
        except Refuse as e:
            return self.json(409 if str(e).startswith("Another") else 400, {"error": str(e)})
        self.send(404, b"not found")


if __name__ == "__main__":
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and not sys.argv[1].isdigit()):
        sys.exit(__doc__)
    port = int(sys.argv[1]) if len(sys.argv) == 2 else 8780
    Handler.port = port
    check_rows()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Live2D GUI: http://127.0.0.1:{port}/  (project {kit.project()}; Ctrl+C stops it)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
