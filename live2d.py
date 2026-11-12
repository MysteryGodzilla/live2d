"""The Live2D kit's one command: a character's drawing to a Live2D model, a step at a time.
Any Python 3.10 or newer runs it (standard library only); it hands each step to the script and the
Python that step needs, and prints the command it runs.

  live2d.py init [--like <project>]    set a project up for the kit: its settings file, a looks file
                                       and the skill's pointer, each only if it isn't there yet
  live2d.py check                      what is installed, and what is missing for which step
  live2d.py status <name>              where a character is in the steps, and what comes next

  live2d.py comfy start|stop|status    our ComfyUI (the drawing, cut-out and upscale steps use it)
  live2d.py draw <round> --character <name> --seeds 1,2,3    candidate drawings of a character in the
                                       looks file, or --look "..." (scripts/draw.py has the rest)
  live2d.py pick <name> <picture.png>  that picture becomes her drawing: <characters>/<name>/full/base.png,
                                       with how it was drawn beside it, base.json
  live2d.py cutout <name>              her drawing without its background: full/cutout.png
  live2d.py upscale <name>             her drawing twice the size (full/base-2x.png) and four times
  live2d.py split <name> body          See-through on all of her, and her layers imported
  live2d.py split <name> head [box]    See-through on her head alone, for a sharper face
  live2d.py layers <command> <name> ...    look at and fix her layers (scripts/layers.py lists them)
  live2d.py parts <command> <name> ...     her closed eyes, open mouth and blush, and numbered sheets
                                       of the mouths and blushes to choose from (scripts/parts.py)
  live2d.py build <name>               her model: <out>/live2d/<name>-full/model/ and <name>-full.zip
  live2d.py view [port]                the viewer, to try her model: http://127.0.0.1:8777/live2d/

<name> is a character's folder under the project's characters folder; her full-size drawing is
meant (<name>/full) unless you write another, <name>/<pose>.

The project is the folder with live2d-kit.json in it, found from where you run this: it says where
the characters are, where output goes and where each tool is installed. README.md, beside this
file, has what to download, each step in order, and what to do when a step goes wrong. SKILL.md is
the same for an agent.
"""
import datetime, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "scripts"))
import kit  # noqa: E402

SEETHROUGH_MODELS = ("models--layerdifforg--seethroughv0.0.2_layerdiff3d", "models--24yearsold--seethroughv0.0.1_marigold")


def script(name):
    return os.path.join(HERE, "scripts", name)


def run(python, name, *args, env=None):
    """One of the kit's scripts with the Python it needs, from the project's folder."""
    command = [python, "-I", script(name), *args]
    print("> " + " ".join(f'"{a}"' if " " in a else a for a in command), flush=True)
    done = subprocess.run(command, cwd=kit.project(), env=dict(os.environ, PYTHONUTF8="1", **(env or {})))
    if done.returncode:
        sys.exit(done.returncode)


def comfy_python():
    return kit.need("comfyui", "python")


def seethrough_python():
    return kit.need("seethrough", "python")


def build_python():
    """The Python that builds her model: the one the layer steps use, unless the settings name another
    (build.python). A settings file from when image2live2d was a separate install may still name its
    Python, which has what the build needs: that is used while it is there."""
    s = kit.settings()
    for named in (s.get("build", {}).get("python"), s.get("image2live2d", {}).get("python")):
        if named and os.path.isfile(named):
            return named
    return seethrough_python()


def paths(name):
    """Where a character's files are."""
    name = kit.pose_of(name)
    char, _, pose = name.partition("/")
    slug = name.replace("/", "-")
    full, layers = kit.characters(char, pose), kit.characters(char, "layers", pose)
    return {"name": name, "slug": slug, "drawing": os.path.join(full, "base.png"), "cutout": os.path.join(full, "cutout.png"),
            "twice": os.path.join(full, "base-2x.png"), "four": kit.out("upscale", slug + "-4x.png"), "layers": layers,
            "model": kit.out("live2d", slug, "model", "model.moc3"), "zip": kit.out("live2d", slug + ".zip")}


def drawn_how(picture):
    """What draw's prompts.txt, beside a picture, says about it: its prompt, seed, size and model."""
    log = os.path.join(os.path.dirname(os.path.abspath(picture)), "prompts.txt")
    if not os.path.exists(log):
        return {}
    stem, found = os.path.splitext(os.path.basename(picture))[0], {}
    with open(log, encoding="utf-8") as f:
        for entry in f.read().split("\n\n"):
            head, _, prompt = entry.strip().partition("\n")
            cells = head.split("\t")
            if cells[0] == stem and prompt and len(cells) >= 8:  # the last one, if it was drawn more than once
                found = {"seed": cells[1].removeprefix("seed "), "size": cells[2], "model": cells[4], "sampler": cells[5],
                         "negative": cells[6].removeprefix("neg ").strip("'\""), "drawn_on": cells[7], "prompt": prompt.strip()}
                if cells[3]:
                    found["note"] = cells[3]
    return found


def pick(name, picture):
    p = paths(name)
    if not os.path.isfile(picture):
        sys.exit(f"{picture}: no such picture")
    os.makedirs(os.path.dirname(p["drawing"]), exist_ok=True)
    if os.path.exists(p["drawing"]):
        print(f"replacing {p['drawing']} (keep the old one first if it isn't in version control)")
    shutil.copy(picture, p["drawing"])
    try:
        source = os.path.relpath(picture, kit.project()).replace("\\", "/")
    except ValueError:  # another drive
        source = os.path.abspath(picture).replace("\\", "/")
    record = {"picked": datetime.date.today().isoformat(), "from": source, **drawn_how(picture)}
    with open(os.path.splitext(p["drawing"])[0] + ".json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"{p['drawing']}: her drawing" + (", and base.json beside it: the prompt and seed it was drawn with"
                                           if "prompt" in record else "") + f". Next: `live2d.py cutout {name}`")


def init(like=None):
    """A project made ready for the kit. Nothing that is already there is changed."""
    top, made = os.getcwd(), []
    if os.path.exists(os.path.join(kit.project(), kit.FILE)):
        top = kit.project()
        print(f"{os.path.join(top, kit.FILE)}: already there, left as it is")
    else:
        with open(os.path.join(HERE, "settings.example.json"), encoding="utf-8") as f:
            wanted = json.load(f)
        if like:
            source = like if like.endswith(".json") else os.path.join(like, kit.FILE)
            if not os.path.isfile(source):
                sys.exit(f"{source}: no such settings file")
            with open(source, encoding="utf-8") as f:
                theirs = json.load(f)
            for section in ("comfyui", "seethrough", "build", "draw", "ffmpeg"):  # where the tools are; not its folders
                if section in theirs:
                    wanted[section] = theirs[section]
            old = theirs.get("image2live2d", {}).get("python")  # from when image2live2d was a separate install
            if old and not wanted.get("build", {}).get("python"):
                wanted["build"] = {"python": old}
        with open(os.path.join(top, kit.FILE), "w", encoding="utf-8", newline="\n") as f:
            json.dump(wanted, f, indent=2)
            f.write("\n")
        made.append(os.path.join(top, kit.FILE) + (f": the tools' paths as in {source}" if like else ": put your own paths in it"))
        kit._found.clear()
    looks = kit.looks_file()
    if os.path.exists(looks):
        print(f"{looks}: already there, left as it is")
    else:
        os.makedirs(os.path.dirname(looks), exist_ok=True)
        shutil.copy(os.path.join(HERE, "templates", "looks.example.json"), looks)
        made.append(looks + ": an example character and style; write your own in their place")
    pointer = os.path.join(top, ".claude", "skills", "live2d-from-drawing", "SKILL.md")
    if os.path.exists(pointer):
        print(f"{pointer}: already there, left as it is")
    else:
        try:
            where = os.path.relpath(HERE, top).replace("\\", "/")
        except ValueError:
            where = ".."
        if where.startswith(".."):  # the kit is outside the project: name it in full
            where = HERE.replace("\\", "/")
        with open(os.path.join(HERE, "SKILL.md"), encoding="utf-8") as f:
            head = f.read().split("---", 2)[1]
        with open(os.path.join(HERE, "templates", "skill-pointer.md"), encoding="utf-8") as f:
            body = f.read()
        if where == ".":  # the kit is the project's own top folder
            body = body.replace("`{kit}/`", "this folder").replace("`{kit}/SKILL.md`", "`SKILL.md` there")
        body = body.replace("{kit}", where)
        os.makedirs(os.path.dirname(pointer), exist_ok=True)
        with open(pointer, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"---{head}---\n\n{body}")
        made.append(pointer + ": so an agent working in this project finds the skill")
    for line in made:
        print("made " + line)
    rel = os.path.relpath(kit.out(), top).replace("\\", "/")
    print(f"\nIf the project is in git, keep these out of it (.gitignore): {rel}/  __pycache__/  .env"
          f"\nNext: `live2d.py check`, then the kit's README ({os.path.join(HERE, 'README.md')})")


def cutout(name):
    p = paths(name)
    run(comfy_python(), "cutout.py", p["drawing"], p["cutout"])


def upscale(name):
    p = paths(name)
    os.makedirs(os.path.dirname(p["four"]), exist_ok=True)
    run(comfy_python(), "upscale.py", p["drawing"], p["four"])
    run(comfy_python(), "upscale.py", p["drawing"], p["twice"], "2")


def have(python, *modules):
    """Whether a Python is there and can import these."""
    if not python or not os.path.isfile(python):
        return "its Python isn't there"
    done = subprocess.run([python, "-I", "-c", "import " + ", ".join(modules)], capture_output=True, text=True)
    return "" if done.returncode == 0 else "its Python can't import them: " + (done.stderr.strip().splitlines() or ["?"])[-1]


def check():
    s = kit.settings()
    found = os.path.exists(os.path.join(kit.project(), kit.FILE))
    print(f"project: {kit.project()}" + ("" if found else f"  (no {kit.FILE} here or above: the kit's own defaults)"))
    print(f"characters: {kit.characters()}" + ("" if os.path.isdir(kit.characters()) else "  (not there yet)"))
    print(f"output: {kit.out()}")
    print(f"looks: {kit.looks_file()}" + ("" if os.path.exists(kit.looks_file()) else "  (not there: `live2d.py init` makes one, or draw with --look)") + "\n")
    rows = []

    def row(what, problem, steps):
        rows.append((what, problem, steps))

    c = s["comfyui"]
    row("ComfyUI", have(c["python"], "numpy", "scipy", "PIL") or
        ("" if os.path.isfile(os.path.join(c["main"], "main.py")) else "comfyui.main has no main.py"), "draw, cutout, upscale")
    models = c["models"]
    for folder, file, steps in (("background_removal", "birefnet.safetensors", "cutout"),
                                ("upscale_models", "RealESRGAN_x4plus_anime_6B.pth", "upscale"),
                                ("diffusion_models", s["draw"]["unet"], "draw on this PC"),
                                ("text_encoders", s["draw"]["text_encoder"], "draw on this PC"),
                                ("vae", s["draw"]["vae"], "draw on this PC")):
        there = bool(models) and os.path.isfile(os.path.join(models, folder, file))
        row(f"  {folder}/{file}", "" if there else "not in the models folder", steps)
    t = s["seethrough"]
    row("See-through", have(t["python"], "torch", "psd_tools", "numpy", "scipy", "PIL") or
        ("" if os.path.isfile(os.path.join(t["repo"], "inference", "scripts", "inference_psd.py")) else "seethrough.repo isn't its clone"),
        "split, layers, parts")
    hub = os.path.join(t["hf_home"], "hub") if t["hf_home"] else ""
    missing = [m for m in SEETHROUGH_MODELS if not os.path.isdir(os.path.join(hub, m))]
    row("  its models", "" if hub and not missing else "not downloaded yet (the first split fetches about 10 GB from Hugging Face)", "split")
    builder = build_python() if t["python"] or s.get("build", {}).get("python") or s.get("image2live2d", {}).get("python") else ""
    row("the build's Python", have(builder, "numpy", "PIL", "pydantic").replace("its Python can't import them", "it can't import them")
        or ("" if os.path.isfile(os.path.join(HERE, "vendor", "image2live2d", "pipeline.py")) else "the kit's vendor folder is missing"),
        "build" + (f"  ({builder})" if builder and builder != t["python"] else ""))
    row("ffmpeg", "" if s.get("ffmpeg") or shutil.which("ffmpeg") else "not on the PATH", "draw's contact sheet (the pictures are made without it)")
    wide = max(len(r[0]) for r in rows)
    for what, problem, steps in rows:
        print(f"{what:{wide}}  {'ok' if not problem else 'MISSING: ' + problem:58}  for: {steps}")
    gpu = shutil.which("nvidia-smi")
    if gpu:
        said = subprocess.run([gpu, "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader"], capture_output=True, text=True)
        print(f"\nGPU: {said.stdout.strip()}  (the GPU steps want it to themselves: close what else is on it)")
    if any(problem for _, problem, _ in rows):
        print(f"\nWhat to download and where it goes: {os.path.join(HERE, 'README.md')}, \"What you need\"")


def status(name):
    p = paths(name)
    info = {}
    if os.path.exists(os.path.join(p["layers"], "layers.json")):
        with open(os.path.join(p["layers"], "layers.json"), encoding="utf-8") as f:
            info = json.load(f)
    order = info.get("order", [])
    psds = sorted(f for f in os.listdir(p["layers"]) if f.endswith(".psd")) if os.path.isdir(p["layers"]) else []
    took_head = any("head layers from" in c for c in info.get("changes", []))
    n = p["name"].removesuffix("/full")  # what the commands take for her full-size drawing
    steps = [
        ("her drawing", os.path.exists(p["drawing"]), f"draw candidates (`live2d.py draw ...`), then `live2d.py pick {n} <picture>`"),
        ("cut-out", os.path.exists(p["cutout"]), f"`live2d.py comfy start`, `live2d.py cutout {n}`"),
        ("upscaled", os.path.exists(p["twice"]) and os.path.exists(p["four"]), f"`live2d.py upscale {n}`, then `live2d.py comfy stop`"),
        ("layers from the whole-body pass", bool(order), f"`live2d.py split {n} body` (about 10 minutes of the GPU)"),
        ("head pass run", any("head" in f for f in psds), f"fix her layers first (`live2d.py layers check {n}`), then `live2d.py split {n} head`"),
        ("layers at twice the size", bool(info) and info["frame"][1] >= 2000, f"`live2d.py layers scale {n} 2`"),
        ("head layers taken", took_head, f"`live2d.py layers head {n} <the head PSD> {os.path.join(p['layers'], 'head-crop.json')}`"),
        ("closed eyes and open mouth", "eye_close" in order and "mouth_open" in order,
         f"`live2d.py parts closed-eyes {n}` and `live2d.py parts mouth {n}`"),
        ("model built", os.path.exists(p["model"]), f"`live2d.py build {n}`"),
    ]
    print(f"{n}: her files are in {os.path.dirname(p['drawing'])} and {p['layers']}")
    nxt = None
    for what, done, how in steps:
        print(f"  [{'x' if done else ' '}] {what}")
        if not done and nxt is None:
            nxt = how
    if order:
        print(f"  layers ({info['frame'][0]}x{info['frame'][1]}): {', '.join(order)}")
    if nxt:
        print(f"next: {nxt}")
    else:
        newer = [f for f in (os.path.join(p["layers"], "layers.json"), os.path.join(p["layers"], "live2d.json"))
                 if os.path.exists(f) and os.path.getmtime(f) > os.path.getmtime(p["model"])]
        print("next: " + (f"her layers changed since her model was built: `live2d.py build {n}`" if newer else
                          f"try her in the viewer (`live2d.py view`); her zip for an app is {p['zip']}"))


def main(args):
    if not args:
        sys.exit(__doc__)
    step, rest = args[0], args[1:]
    if step == "init" and (not rest or (len(rest) == 2 and rest[0] == "--like")):
        init(*rest[1:])
    elif step == "check" and not rest:
        check()
    elif step == "status" and len(rest) == 1:
        status(rest[0])
    elif step == "comfy" and len(rest) == 1:
        run(sys.executable, "comfy.py", rest[0])
    elif step == "draw" and rest:
        run(sys.executable, "draw.py", *rest)
    elif step == "pick" and len(rest) == 2:
        pick(*rest)
    elif step == "cutout" and len(rest) == 1:
        cutout(rest[0])
    elif step == "upscale" and len(rest) == 1:
        upscale(rest[0])
    elif step == "split" and len(rest) in (2, 6) and rest[1] in ("body", "head"):
        run(seethrough_python(), "split.py", rest[1], kit.pose_of(rest[0]), *rest[2:])
    elif step in ("layers", "parts") and len(rest) >= 2:
        run(seethrough_python(), step + ".py", rest[0], kit.pose_of(rest[1]), *rest[2:])
    elif step == "parts" and rest in (["mouth-masters"], ["mouth-sheet"]):  # the kit's own, no character
        run(seethrough_python(), "parts.py", rest[0])
    elif step == "build" and len(rest) == 1:
        run(build_python(), "rig.py", "build", kit.pose_of(rest[0]))
    elif step == "view" and len(rest) <= 1:
        run(sys.executable, "view.py", *rest)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
