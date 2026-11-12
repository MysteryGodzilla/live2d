"""ComfyUI for the kit: starting and stopping our own copy of it, and running a graph on it.
Standard library only.

usage:
  comfy.py start     start ComfyUI on the address in the settings (comfyui.url), with the kit's
                     models folder added to its own; waits until it answers. Its input, output and
                     temp folders, its log and its PID go in <out>/comfy/
  comfy.py stop      stop the ComfyUI that start started (the PID in <out>/comfy/comfy.pid), no other
  comfy.py status    whether it answers, who started it (this project, or another folder), how much
                     of the graphics card it holds, and the models the kit's steps need that it can't see

It needs the GPU to itself: stop it before See-through runs, and don't run it beside another
program that fills the card. The install itself isn't changed: the models folder is passed with
--extra-model-paths-config, written fresh to <out>/comfy/ each start.
"""
import base64, json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit

MODEL_FOLDERS = ("diffusion_models", "text_encoders", "vae", "loras", "background_removal", "upscale_models")
NEEDED = {  # step -> (ComfyUI node, its input, the file): what each step loads
    "cutout": ("LoadBackgroundRemovalModel", "bg_removal_name", "birefnet.safetensors"),
    "upscale": ("UpscaleModelLoader", "model_name", "RealESRGAN_x4plus_anime_6B.pth"),
}


def url():
    return kit.settings()["comfyui"]["url"].rstrip("/")


def http(method, address, body=None, headers=None, raw=False, timeout=120):
    data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
    req = urllib.request.Request(address, method=method, data=data,
                                 headers=headers or {"Content-Type": "application/json", "User-Agent": "live2d-kit/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, (r.read() if raw else json.load(r))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except (urllib.error.URLError, OSError) as e:
        return 0, str(e)


def answers():
    return http("GET", url() + "/system_stats", timeout=3)[0] == 200


def pid_path():
    return kit.out("comfy", "comfy.pid")


def pid_alive(pid):
    """Whether a process with this PID is running."""
    if os.name == "nt":
        done = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"], capture_output=True, text=True)
        return f'"{pid}"' in done.stdout
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def state():
    """What is on ComfyUI's address: {"running", "url", "ours", "where", "pid", "held_gb", "stale"}.
    It is ours when its output folder is this project's <out>/comfy/output (comfy start passes it):
    then comfy stop here stops it. Otherwise "where" is the folder its output goes to, which says who
    started it, or "" when it wasn't started by the kit. "held_gb" is the graphics memory ComfyUI's
    own torch holds (its models stay loaded until it needs the room). "stale" is a comfy.pid left by
    a ComfyUI that has since stopped."""
    out = {"running": False, "url": url(), "ours": False, "where": "", "pid": None, "held_gb": None, "stale": False}
    path = pid_path()
    if os.path.exists(path):
        out["pid"] = open(path).read().strip()
    status, stats = http("GET", url() + "/system_stats", timeout=3)
    if status != 200 or not isinstance(stats, dict):
        out["stale"] = out["pid"] is not None and not pid_alive(out["pid"])
        return out
    out["running"] = True
    argv = stats.get("system", {}).get("argv", [])
    given = argv[argv.index("--output-directory") + 1] if "--output-directory" in argv[:-1] else ""
    mine = kit.out("comfy", "output")
    out["ours"] = bool(given) and os.path.normcase(os.path.normpath(given)) == os.path.normcase(mine)
    if given and not out["ours"]:
        out["where"] = os.path.dirname(os.path.dirname(os.path.normpath(given)))  # <its out>/comfy/output -> <its out>
    devices = stats.get("devices") or []
    if devices and "torch_vram_total" in devices[0]:
        out["held_gb"] = round(devices[0]["torch_vram_total"] / 2 ** 30, 1)
    return out


def describe(s=None):
    """One plain line on ComfyUI's state."""
    s = s or state()
    if not s["running"]:
        return f"ComfyUI is not running on {s['url']}" + (" (a comfy.pid was left from one that has stopped)" if s["stale"] else "")
    held = f", holding {s['held_gb']:g} GB of the graphics card" if s["held_gb"] else ""
    if s["ours"]:
        return f"ComfyUI is running on {s['url']}, started from this project" + (f" (PID {s['pid']})" if s["pid"] else "") + held
    whose = f"started from another folder, {s['where']}" if s["where"] else "started outside the kit"
    return f"ComfyUI is running on {s['url']}, {whose}{held}. The steps here can use it; stop it where it was started"


class Local:
    """A graph run on our ComfyUI. submit(graph, extra) -> id; result(id) -> None while it runs,
    (png bytes, note) when done, (None, why) when it failed. The picture is the SaveImage node "8"'s.
    extra["images"] are uploaded and given to the LoadImage node "11"."""

    def __init__(self):
        if not answers():
            sys.exit(f"ComfyUI isn't answering on {url()}: start it with `live2d.py comfy start`")
        self.started = {}

    def submit(self, wf, extra):
        for img in extra.get("images", []):
            name, boundary = uuid.uuid4().hex + ".png", uuid.uuid4().hex
            body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
                    f"Content-Type: image/png\r\n\r\n").encode() + base64.b64decode(img["image"]) + \
                   f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{boundary}--\r\n".encode()
            status, up = http("POST", url() + "/upload/image", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
            if status != 200:
                sys.exit(f"upload failed: {status} {up}")
            wf["11"]["inputs"]["image"] = up["name"]
        status, sub = http("POST", url() + "/prompt", {"prompt": wf, "client_id": "live2d-kit"})
        if status != 200:
            sys.exit(f"submit failed: {status} {sub}")
        self.started[sub["prompt_id"]] = time.time()
        return sub["prompt_id"]

    def result(self, prompt_id):
        status, hist = http("GET", f"{url()}/history/{prompt_id}")
        if status != 200 or prompt_id not in hist:
            return None
        h = hist[prompt_id]
        if h.get("status", {}).get("status_str") != "success":
            return None, json.dumps(h.get("status"))[:400]
        img = h["outputs"]["8"]["images"][0]
        q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]})
        status, png = http("GET", f"{url()}/view?{q}", raw=True)
        times = [m[1].get("timestamp", 0) for m in h.get("status", {}).get("messages", []) if m[0] in ("execution_start", "execution_success")]
        took = f"run {(times[-1] - times[0]) / 1000:.0f} s" if len(times) == 2 else ""
        return (png, took) if status == 200 else (None, f"view failed: {status}")

    def picture(self, wf, extra, what, wait=600):
        """Run a graph and wait for its picture's bytes."""
        job = self.submit(wf, extra)
        for _ in range(wait):
            res = self.result(job)
            if res is not None:
                png, note = res
                if png is None:
                    sys.exit(f"{what}: failed: {note}")
                return png
            time.sleep(1)
        sys.exit(f"{what}: nothing after {wait // 60} minutes")


def can_load(node, field):
    """The files ComfyUI offers for a loader node's input, or None if it has no such node."""
    status, info = http("GET", f"{url()}/object_info/{node}")
    try:
        spec = info[node]["input"]["required"][field]
        return list(spec[0] if isinstance(spec[0], list) else spec[1]["options"])  # older ComfyUI: the list itself
    except (KeyError, IndexError, TypeError):
        return None


def start():
    work, c = kit.out("comfy"), kit.settings()["comfyui"]
    s = state()
    if s["running"]:
        print(f"Not starting another: {describe(s)}")
        return
    if s["stale"]:
        os.remove(pid_path())
    python, main, models = kit.need("comfyui", "python"), kit.need("comfyui", "main"), kit.need("comfyui", "models")
    for folder in ("input", "output", "temp"):
        os.makedirs(os.path.join(work, folder), exist_ok=True)
    paths = os.path.join(work, "extra_model_paths.yaml")
    with open(paths, "w", encoding="utf-8") as f:
        f.write("# Written by the kit's comfy.py at each start: the kit's models, outside ComfyUI's own folder.\n"
                "kit:\n  base_path: " + models.replace("\\", "/").rstrip("/") + "/\n" +
                "".join(f"  {name}: {name}/\n" for name in MODEL_FOLDERS))
    host, _, port = urllib.parse.urlparse(c["url"]).netloc.partition(":")
    log = open(os.path.join(work, "comfy.log"), "w", encoding="utf-8")
    p = subprocess.Popen(
        [python, "-s", "main.py", "--listen", host, "--port", port or "8188", "--disable-auto-launch",
         "--extra-model-paths-config", paths, "--input-directory", os.path.join(work, "input"),
         "--output-directory", os.path.join(work, "output"), "--temp-directory", os.path.join(work, "temp")],
        cwd=main, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    with open(os.path.join(work, "comfy.pid"), "w") as f:
        f.write(str(p.pid))
    for _ in range(90):
        if answers():
            print(f"ComfyUI ready on {url()}, PID {p.pid}")
            return
        if p.poll() is not None:
            break
        time.sleep(2)
    sys.exit(f"ComfyUI didn't answer within 3 minutes: see {os.path.join(work, 'comfy.log')}")


def stop():
    path = pid_path()
    s = state()
    if not os.path.exists(path):
        if s["running"]:
            sys.exit(f"Not stopping it: {describe(s)}")
        sys.exit("ComfyUI isn't running: nothing to stop")
    pid = open(path).read().strip()
    if not pid_alive(pid):
        os.remove(path)
        print(f"ComfyUI (PID {pid}) had already stopped")
        return
    if os.name == "nt":
        done = subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True, text=True)
        said = (done.stdout or done.stderr).strip().splitlines()
    else:
        import signal
        try:
            os.kill(int(pid), signal.SIGTERM)
            said = [f"stopped PID {pid}"]
        except ProcessLookupError:
            said = [f"PID {pid} was not running"]
    os.remove(path)
    print(said[-1] if said else f"stopped PID {pid}")


def status():
    s = state()
    print(describe(s))
    if not s["running"]:
        return False
    fine = True
    for step, (node, field, file) in NEEDED.items():
        files = can_load(node, field)
        if files is None or file not in files:
            fine = False
            print(f"  {step}: " + (f"this ComfyUI has no {node} node (too old?)" if files is None else f"{file} is missing"))
    return fine


if __name__ == "__main__":
    command = {"start": start, "stop": stop, "status": status}.get(sys.argv[1] if len(sys.argv) == 2 else "")
    if not command:
        sys.exit(__doc__)
    command()
