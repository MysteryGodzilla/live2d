"""What every script of the kit shares: which project it is working on, that project's settings, and
its folders. Standard library only, so any Python can load it.

The kit works on a project: a folder with the characters' drawings and layers in it, and somewhere
for what the kit makes. The project is the folder that holds live2d-kit.json, looked for in the
folder you run from and then in each folder above it. With no such file, the project is the folder
you run from and the settings are the ones below.

live2d-kit.json (see settings.example.json beside the kit's README):
  characters    the folder with one folder per character, from the project's folder
  out           the folder for everything the kit makes that isn't kept (models, check pictures, logs)
  comfyui       python: ComfyUI's own Python; main: the folder with ComfyUI's main.py;
                url: where ours listens; models: the folder with diffusion_models/, text_encoders/,
                vae/, background_removal/ and upscale_models/ in it
  seethrough    repo: See-through's clone; python: its venv's Python; hf_home: where its models are
  build         python: another Python for the build step, if not See-through's (it needs numpy,
                Pillow and pydantic). Optional
  draw          unet, text_encoder, vae: the Qwen Image 2.1 files draw.py loads
  looks         the file that says what each character looks like, for `draw --character`
                (optional: <characters>/looks.json without it; templates/looks.example.json)
  ffmpeg        ffmpeg's program, if it isn't on the PATH (contact sheets)
  examples      a folder of other Live2D models for the viewer to show beside ours, each as
                <model>/runtime/*.model3.json (optional)
"""
import json, os, sys

FILE = "live2d-kit.json"
DEFAULTS = {
    "characters": "characters",
    "out": "out",
    "comfyui": {"python": "", "main": "", "url": "http://127.0.0.1:8189", "models": ""},
    "seethrough": {"repo": "", "python": "", "hf_home": ""},
    "build": {"python": ""},
    "draw": {"unet": "qwen_image_2.1_turbo_int8_convrot.safetensors",
             "text_encoder": "qwen3vl_8b_int8_convrot.safetensors",
             "vae": "qwen_image_2.1_vae_bf16.safetensors"},
    "ffmpeg": "",
    "looks": "",
}
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(SCRIPTS)
_found = {}


def project():
    """The project's folder."""
    if "project" not in _found:
        folder = start = os.getcwd()
        while not os.path.exists(os.path.join(folder, FILE)):
            up = os.path.dirname(folder)
            if up == folder:
                folder = start
                break
            folder = up
        _found["project"] = folder
    return _found["project"]


def settings():
    if "settings" not in _found:
        merged = json.loads(json.dumps(DEFAULTS))
        path = os.path.join(project(), FILE)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for key, value in json.load(f).items():
                    if isinstance(value, dict) and isinstance(merged.get(key), dict):
                        merged[key].update(value)
                    else:
                        merged[key] = value
        _found["settings"] = merged
    return _found["settings"]


def characters(*more):
    return os.path.normpath(os.path.join(project(), settings()["characters"], *more))


def out(*more):
    return os.path.normpath(os.path.join(project(), settings()["out"], *more))


def looks_file():
    """Where the characters' looks are written down (templates/looks.example.json shows how)."""
    s = settings()
    return os.path.normpath(os.path.join(project(), s.get("looks") or os.path.join(s["characters"], "looks.json")))


def need(section, key):
    """A setting the step can't run without, or a stop that says where to put it."""
    value = settings().get(section, {}).get(key)
    if not value:
        sys.exit(f"{section}.{key} isn't set in {os.path.join(project(), FILE)}: see the kit's README, "
                 f"\"What you need\" ({os.path.join(KIT, 'README.md')})")
    return value


def pose_of(name):
    """akane -> akane/full: the kit's own scripts take a character's full-size drawing unless told another."""
    return name if "/" in name else name + "/full"
