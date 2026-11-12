"""ComfyUI for the kit: starting and stopping our own copy of it, and running a graph on it.
Standard library only.

usage:
  comfy.py start     start ComfyUI on the address in the settings (comfyui.url), with the kit's
                     models folder added to its own; waits until it answers. Its input, output and
                     temp folders, its log and its PID go in <out>/comfy/
  comfy.py stop      stop the ComfyUI that start started (the PID in <out>/comfy/comfy.pid), no other
  comfy.py status    whether it answers, and the models the kit's steps need that it can't see

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
    if answers():
        print(f"ComfyUI already answers on {url()}: not starting another")
        return
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
    path = kit.out("comfy", "comfy.pid")
    if not os.path.exists(path):
        sys.exit("no ComfyUI of ours to stop (no comfy.pid): one started another way is left alone")
    pid = open(path).read().strip()
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
    if not answers():
        print(f"ComfyUI isn't answering on {url()}")
        return False
    print(f"ComfyUI answers on {url()}")
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
