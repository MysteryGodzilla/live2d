"""Candidate drawings of a character with Qwen Image 2.1: several seeds of one prompt, to pick the
one that becomes her Live2D model. Standard library only (ffmpeg makes the contact sheet).

usage:
  draw.py <round> --character <name[:look]> --seeds 1,2,3 [options]
  draw.py <round> --look "<what she looks like>" --seeds 1,2,3 [options]
  draw.py <round> --prompt "<the whole prompt>" --seeds 1,2,3 [options]
  draw.py <round> --edit <picture.png> --prompt "<what to change>" --seeds 1 [options]

  --character  a character from the looks file (<characters>/looks.json, or the settings' "looks";
               the kit's templates/looks.example.json shows how it is written). mika is her
               "default" look, mika:summer the look called "summer"
  --look       her description here on the command line instead (hair, eyes, clothes, build)
               Round either one the kit puts its own opening and closing (STYLE and POSE below):
               a full-body front view, standing straight, arms a little away from her sides, mouth
               shut, eyes open, on plain light grey. That pose is the one that splits into layers
               and rigs well; see the README, "A drawing that rigs"
  --style      an art style from the looks file's "styles": its words take the place of the kit's
               own art style words, and it can name a LoRA or another model with its own settings
  --lora       a LoRA file in <models>/loras/, as file.safetensors or file.safetensors:0.8
  --prompt     the prompt as it is, nothing added
  --edit       redraw a picture with a change ("Keep the same character ... Change only this: ...")
  --name       what the pictures are called, <name>-<seed>.png (default: the character, else the round)
  --size       WxH (default 928x1664: tall enough for a whole figure, and what Qwen draws well)
  --negative   a negative prompt (only has an effect with --cfg above 1)
  --steps, --cfg   sampler settings (default 8 and 1, the turbo model's, or the style's own)
  --unet       another diffusion model file than the settings' draw.unet
  --show       print the prompt and settings and stop: nothing is drawn, ComfyUI isn't needed
  --runpod     draw on a RunPod endpoint instead of this PC's ComfyUI: RUNPOD_API_KEY and
               RUNPOD_ENDPOINT_ID from the environment or the project's .env (never printed). It is
               paid: ask whoever pays first. The endpoint has to be a ComfyUI worker that takes
               {"input": {"workflow": ..., "images": [...], "loras": [...]}} and answers with
               output.images[0].data

Pictures go to <out>/<round>/, with prompts.txt (every prompt, seed, size and model) and a labelled
contact sheet, sheet.jpg. On this PC it needs ComfyUI running (`live2d.py comfy start`) with the
three Qwen Image 2.1 files in its models (the README lists them), and the GPU to itself. It uses
ComfyUI's own nodes only: no custom nodes to install.

Other scripts use this as a module: workflow() builds the graph, run() draws a list of jobs. A
project with its own way of writing prompts (several styles, a paid account, records of what was
picked) can keep a script of its own on top of these two.
"""
import base64, json, os, re, shutil, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfy, kit

# The opening is two sentences: how she is framed, which the split and the rig depend on, and the
# art style, which is taste. A style from the looks file replaces only the second.
FRAME = ("Anime character concept art, full body character reference sheet style, one character standing in a "
         "relaxed front-facing pose, whole body visible from head to shoes, plain light grey background.")
ART = "Clean cel-shaded anime illustration, crisp line art, soft even lighting."
STYLE = FRAME + " " + ART
POSE = ("The character stands straight, facing the viewer, head upright, arms relaxed and held a little away from "
        "the body, hands open and empty, mouth closed, eyes open.")
EDIT = "Keep the same character, art style, outfit and background. Change only this:"
SIZE = (928, 1664)


def workflow(prompt, seed, size, source=None, unet=None, steps=8, cfg=1.0, negative="", lora=None):
    """The ComfyUI graph for one picture, and what a RunPod job needs besides it (a LoRA to fetch, the
    picture an edit starts from). lora: {"name", "strength"}, and "url" and "sha256" for RunPod."""
    files = kit.settings()["draw"]
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet or files["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": files["text_encoder"], "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": files["vae"]}},
        "4": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["2", 0], "prompt": prompt, "negative_prompt": negative, "resolution": 1024}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": size[0], "height": size[1], "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "euler", "scheduler": "simple",
                                                   "denoise": 1.0, "model": ["1", 0], "positive": ["4", 0], "negative": ["4", 1], "latent_image": ["5", 0]}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "live2d-kit", "images": ["7", 0]}},
    }
    extra = {}
    if lora:
        wf["20"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora["name"], "strength_model": lora.get("strength", 1.0)}}
        wf["6"]["inputs"]["model"] = ["20", 0]
        if lora.get("url"):
            extra["loras"] = [{"name": lora["name"], "url": lora["url"], "sha256": lora.get("sha256", "")}]
    if source:
        wf["11"] = {"class_type": "LoadImage", "inputs": {"image": "src.png"}}
        wf["4"]["inputs"].update({"vae": ["3", 0], "images.image_1": ["11", 0]})
        wf["6"]["inputs"]["latent_image"] = ["4", 2]
        del wf["5"]
        extra["images"] = [{"name": "src.png", "image": base64.b64encode(open(source, "rb").read()).decode()}]
    return wf, extra


def looks():
    """The looks file: {"characters": {name: {"looks": {"default": ...}, "negative": ...}}, "styles": {...}}."""
    path = kit.looks_file()
    if not os.path.exists(path):
        sys.exit(f"{path}: no looks file. Copy {os.path.join(kit.KIT, 'templates', 'looks.example.json')} there "
                 "(`live2d.py init` does), or describe her with --look")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def named(entries):
    return sorted(k for k in entries if not k.startswith("_"))


def look_of(char):
    """mika, or mika:summer -> her look's words and her negative prompt."""
    name, _, which = char.partition(":")
    people = looks().get("characters", {})
    if name.startswith("_") or name not in people:
        sys.exit(f"{name} isn't in {kit.looks_file()}: it has {', '.join(named(people)) or 'no characters'}")
    theirs = people[name].get("looks", {})
    if (which or "default") not in theirs:
        sys.exit(f"{name} has no look called '{which or 'default'}': she has {', '.join(named(theirs)) or 'none'}")
    return theirs[which or "default"].strip(), people[name].get("negative", "")


def style_of(name):
    styles = looks().get("styles", {})
    if name.startswith("_") or not isinstance(styles.get(name), dict):
        sys.exit(f"no style called '{name}' in {kit.looks_file()}: it has {', '.join(named(styles)) or 'no styles'}")
    return styles[name]


def secret(name):
    """A key from the environment or the project's .env. Never printed."""
    if os.environ.get(name):
        return os.environ[name]
    path = os.path.join(kit.project(), ".env")
    if os.path.exists(path):
        m = re.search(rf'^{name}=\s*"?([^"\s#]+)', open(path, encoding="utf-8").read(), re.M)
        if m:
            return m.group(1)
    return None


class RunPod:
    """The same graphs on a RunPod ComfyUI worker. Paid by the second."""
    name = "runpod"

    def __init__(self, endpoint=None, key=None):
        endpoint, key = endpoint or secret("RUNPOD_ENDPOINT_ID"), key or secret("RUNPOD_API_KEY")
        if not endpoint or not key:
            sys.exit("RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY aren't in the environment or the project's .env "
                     f"({os.path.join(kit.KIT, 'templates', 'env.example')} shows how)")
        self.base = "https://api.runpod.ai/v2/" + endpoint
        self.head = {"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "live2d-kit/1"}

    def submit(self, wf, extra):
        if "20" in wf and "loras" not in extra:
            sys.exit(f"{wf['20']['inputs']['lora_name']}: a LoRA drawn on RunPod needs a \"url\" and \"sha256\" in its style, "
                     "so the worker can fetch it")
        status, sub = comfy.http("POST", self.base + "/run", {"input": {"workflow": wf, **extra}}, self.head)
        if status != 200:
            sys.exit(f"submit failed: {status} {sub}")
        return sub["id"]

    def result(self, job_id):
        status, st = comfy.http("GET", f"{self.base}/status/{job_id}", headers=self.head)
        state = st.get("status") if isinstance(st, dict) else st
        if status == 200 and state in ("IN_QUEUE", "IN_PROGRESS"):
            return None
        out = st.get("output") if isinstance(st, dict) else None
        if state != "COMPLETED" or not out or out.get("error") or not out.get("images"):
            return None, f"{state} {json.dumps(st)[:300]}"
        data = out["images"][0]["data"]
        return base64.b64decode(data.split(",", 1)[1] if "," in data[:100] else data), f"run {st.get('executionTime')} ms"


class Local(comfy.Local):
    """This PC's ComfyUI. Before a graph goes in, the files it loads are looked for among the ones
    ComfyUI offers: its own answer to a missing file is long and cut short."""
    name = "local"
    LOADS = {"1": ("UNETLoader", "unet_name", "diffusion_models"), "2": ("CLIPLoader", "clip_name", "text_encoders"),
             "3": ("VAELoader", "vae_name", "vae"), "20": ("LoraLoaderModelOnly", "lora_name", "loras")}

    def __init__(self):
        super().__init__()
        self.offered = {}
        info = comfy.http("GET", comfy.url() + "/object_info/TextEncodeQwenImage21")[1]
        if not isinstance(info, dict) or "TextEncodeQwenImage21" not in info:
            sys.exit("this ComfyUI has no TextEncodeQwenImage21 node: it is older than Qwen Image 2.1 (0.43.0 has it)")

    def submit(self, wf, extra):
        for node, (kind, field, folder) in self.LOADS.items():
            if node not in wf:
                continue
            file = wf[node]["inputs"][field]
            if file not in self.offered.setdefault(folder, {}):
                self.offered[folder] = set(comfy.can_load(kind, field) or [])
            if file not in self.offered[folder]:
                sys.exit(f"{file} isn't among ComfyUI's {folder}: put it in "
                         f"{os.path.join(kit.settings()['comfyui']['models'] or '<models>', folder)} (the kit's README, \"What you need\")")
        return super().submit(wf, {k: v for k, v in extra.items() if k != "loras"})


def run(round_name, jobs, backend, cols=None):
    """Draw jobs, each (name, prompt, graph, extra, note): all handed in, then all waited for. Pictures,
    prompts.txt and sheet.jpg go to <out>/<round_name>/. Returns the pictures made, as (name, path)."""
    folder = kit.out(round_name)
    os.makedirs(folder, exist_ok=True)
    pending, t0 = {}, time.time()
    with open(os.path.join(folder, "prompts.txt"), "a", encoding="utf-8") as log:
        for name, prompt, wf, extra, note in jobs:
            size = wf["5"]["inputs"] if "5" in wf else {"width": "as its", "height": "source"}
            lora = f" + {wf['20']['inputs']['lora_name']} at {wf['20']['inputs']['strength_model']}" if "20" in wf else ""
            log.write(f"{name}\tseed {wf['6']['inputs']['seed']}\t{size['width']}x{size['height']}\t{note}\t"
                      f"{wf['1']['inputs']['unet_name']}{lora}\tsteps {wf['6']['inputs']['steps']} cfg {wf['6']['inputs']['cfg']}\t"
                      f"neg {wf['4']['inputs']['negative_prompt']!r}\t{backend.name}\n{prompt}\n\n")
            pending[backend.submit(wf, extra)] = name
    saved, limit = [], 1200 if backend.name == "runpod" else 600 * len(jobs)
    while pending and time.time() - t0 < limit:
        time.sleep(5)
        for job_id, name in list(pending.items()):
            res = backend.result(job_id)
            if res is None:
                continue
            del pending[job_id]
            png, note = res
            if png is None:
                print(f"{name}: failed: {note}")
                continue
            path = os.path.join(folder, name + ".png")
            open(path, "wb").write(png)
            saved.append((name, path))
            print(f"{name}: saved, {note}", flush=True)
    for name in pending.values():
        print(f"{name}: still waiting after {limit // 60} min, gave up")
    order = [job[0] for job in jobs]
    saved.sort(key=lambda s: order.index(s[0]))
    if saved:
        sheet(os.path.join(folder, "sheet.jpg"), saved, cols=cols or (5 if len(saved) > 12 else 4))
    return saved


def sheet(out, items, cols=4, w=448, h=576):
    """A labelled contact sheet of (label, picture path) items."""
    ff = kit.settings().get("ffmpeg") or shutil.which("ffmpeg")
    if not ff:
        print("no contact sheet: ffmpeg isn't on the PATH or in the settings")
        return
    font = "C\\:/Windows/Fonts/arial.ttf" if os.name == "nt" else ""
    args, chains = [ff, "-y", "-loglevel", "error"], []
    for i, (label, path) in enumerate(items):
        args += ["-i", path]
        text = label.replace(":", r"\:").replace("'", "")
        chains.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:white,"
                      f"drawbox=x=0:y=0:w=iw:h=34:color=black@0.65:t=fill,"
                      f"drawtext={f'fontfile={chr(39)}{font}{chr(39)}:' if font else ''}text='{text}':fontcolor=white:fontsize=22:x=8:y=6[v{i}]")
    cols = min(cols, len(items))
    layout = "|".join(f"{(i % cols) * w}_{(i // cols) * h}" for i in range(len(items)))
    graph = ";".join(chains) + ";" + "".join(f"[v{i}]" for i in range(len(items)))
    graph += f"xstack=inputs={len(items)}:layout={layout}:fill=white[out]" if len(items) > 1 else "null[out]"
    subprocess.run(args + ["-filter_complex", graph, "-map", "[out]", "-q:v", "3", out], check=True)
    print("sheet:", out)


WORDS = ("character", "look", "prompt", "edit", "style", "lora", "name", "size", "negative", "steps", "cfg", "unet", "seeds")


def main(args):
    if not args or args[0].startswith("-"):
        sys.exit(__doc__)
    round_name, given, flags, i = args[0], {}, set(), 1
    while i < len(args):
        key = args[i].lstrip("-")
        if key in ("runpod", "show"):
            flags.add(key)
            i += 1
        elif key in WORDS and i + 1 < len(args):
            given[key] = args[i + 1]
            i += 2
        else:
            sys.exit(f"{args[i]}?\n\n{__doc__}")
    if "seeds" not in given or sum(k in given for k in ("character", "look", "prompt")) != 1:
        sys.exit("give --seeds, and one of --character, --look and --prompt\n\n" + __doc__)
    style = style_of(given["style"]) if "style" in given else {}
    words, negative = look_of(given["character"]) if "character" in given else (given.get("look", "").strip(), "")
    if words:
        opening = f"{style['words'].strip()} {FRAME}" if style.get("words") else STYLE
        prompt = f"{opening} {words} {POSE}"
    elif "edit" in given:
        prompt = f"{EDIT} {given['prompt'].strip().rstrip('.')}."
    else:
        prompt = given["prompt"]
    lora = None
    if "lora" in given:
        file, _, strength = given["lora"].partition(":")
        lora = {"name": file, "strength": float(strength or 1.0)}
    elif style.get("lora"):
        lora = {"name": style["lora"], "strength": float(style.get("strength", 1.0)), "url": style.get("url"), "sha256": style.get("sha256")}
    size = tuple(int(n) for n in given["size"].split("x")) if "size" in given else SIZE
    unet = given.get("unet") or style.get("unet")
    steps, cfg = int(given.get("steps", style.get("steps", 8))), float(given.get("cfg", style.get("cfg", 1.0)))
    negative = given.get("negative") or style.get("negative") or negative
    name = given.get("name") or "-".join(filter(None, [given.get("character", "").replace(":", "-"), given.get("style", "")])) or round_name
    note = " ".join(filter(None, [given.get("style", ""), "edit of " + given["edit"] if "edit" in given else ""]))
    jobs = []
    for seed in given["seeds"].split(","):
        wf, extra = workflow(prompt, int(seed), size, given.get("edit"), unet, steps, cfg, negative, lora)
        jobs.append((f"{name}-{seed}", prompt, wf, extra, note))
    if "show" in flags:
        wf = jobs[0][2]
        print(f"prompt: {prompt}\nnegative: {negative or '(none)'}\nmodel: {wf['1']['inputs']['unet_name']}"
              + (f"\nLoRA: {lora['name']} at {lora['strength']}" if lora else "")
              + f"\nsteps {steps}, cfg {cfg}, {'as its source' if 'edit' in given else f'{size[0]}x{size[1]}'}"
              + f"\npictures: {', '.join(os.path.join(kit.out(round_name), job[0] + '.png') for job in jobs)}")
        return
    run(round_name, jobs, RunPod() if "runpod" in flags else Local())


if __name__ == "__main__":
    main(sys.argv[1:])
