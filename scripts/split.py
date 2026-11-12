"""See-through on a character: her drawing split into layers (hair, face, eyes, clothes, each with
what is hidden behind it painted in), which is what a rig needs. Two passes, each about 10 minutes
of a 12 GB card to itself (much longer, even hours, if another program holds part of the card):

  split.py body <name>
      her whole drawing. The PSD is kept as <her layers>/<date>-seethrough.psd, and her layers are
      imported from it (layers.py import): one PNG per layer in <her layers>/parts/
  split.py head <name> [x0 y0 x1 y1]
      her head alone, cut from her drawing upscaled four times (<out>/upscale/<name>-4x.png, from
      upscale.py), so her face gets several times the pixels the whole-body pass gives it. The cut
      is worked out from her face layer (the whole-body pass has to be imported first), or is the
      box given, in her drawing's own pixels. The PSD is kept as <her layers>/<date>-seethrough-head.psd
      and the cut as <her layers>/head-crop.json; then bring it in:
        layers.py scale <name> 2          (once: her layers to twice the size, sharp from base-2x.png)
        layers.py head <name> <the head PSD> <her layers>/head-crop.json

`live2d.py split <name> body|head` runs it. By hand, with See-through's own Python:
  <see-through python> -I split.py body <name>

See-through (github.com/shitagaki-lab/see-through, Apache-2.0) works at 1280 px: it fits the longer
side of what it is given to that and centres it. Its models come from Hugging Face the first time
(into the settings' seethrough.hf_home); after that it runs without the internet. Its own output
goes to <its repo>/workspace/layerdiff_output/. Each run's log is in <out>/seethrough/.
"""
import datetime, json, os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit
import layers as L

SIDE, TOP, BELOW = 0.6, 0.6, 0.3  # the head cut: this much of her face's width each side, of its height above and below


def base_drawing(name):
    """Her drawing as it was drawn (not the upscaled one): See-through works at 1280 px either way."""
    char, pose = L.split(name)
    if pose == "full":
        return os.path.join(L.CHARS, char, "full", "base.png")
    return L.drawing_files(name)[0]


def see_through(picture, stem):
    """Run See-through on one picture; returns the PSD it made."""
    repo, python = kit.need("seethrough", "repo"), kit.need("seethrough", "python")
    work = kit.out("seethrough", stem)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    shutil.copy(picture, os.path.join(work, stem + ".png"))
    made = os.path.join(repo, "workspace", "layerdiff_output", stem + ".psd")
    if os.path.exists(made):
        os.remove(made)
    env = dict(os.environ, PYTHONUTF8="1")
    home = kit.settings()["seethrough"].get("hf_home")
    if home:
        env["HF_HOME"] = home
        if os.path.isdir(os.path.join(home, "hub")) and os.listdir(os.path.join(home, "hub")):
            env["HF_HUB_OFFLINE"] = "1"  # its models are here already: no call to Hugging Face
    log = kit.out("seethrough", stem + ".log")
    print(f"See-through on {picture}: about 10 minutes with the GPU to itself. Log: {log}", flush=True)
    with open(log, "w", encoding="utf-8") as f:
        done = subprocess.run([python, "inference/scripts/inference_psd.py", "--srcp", work, "--save_to_psd", "--group_offload"],
                              cwd=repo, env=env, stdout=f, stderr=subprocess.STDOUT)
    if done.returncode or not os.path.exists(made):
        sys.exit(f"See-through stopped without a PSD (exit {done.returncode}): see the end of {log}")
    return made


def short(name):
    """akane/full -> akane: what live2d.py takes for her full-size drawing."""
    return name.removesuffix("/full")


def quoted(path):
    return f'"{path}"' if " " in path else path


def body(name):
    stem = L.slug(name)
    psd = see_through(base_drawing(name), stem)
    os.makedirs(L.folder(name), exist_ok=True)
    kept = os.path.join(L.folder(name), f"{datetime.date.today()}-seethrough.psd")
    shutil.copy(psd, kept)
    print(f"kept {kept}")
    L.do_import(name, kept)
    print(f"next: `live2d.py layers check {short(name)}`, fix what is off (the README, \"Fixing the layers\"), then the head pass")


def head_box(name):
    """A cut round her head from her face layer, in her drawing's own pixels."""
    from PIL import Image
    info = L.load(name)
    W, H = info["frame"]
    bw, bh = Image.open(base_drawing(name)).size
    s = H / bh  # her drawing in her frame: scaled to its height, centred
    X = (W - round(bw * s)) // 2
    face = Image.open(L.part_path(name, "face")).getchannel("A").point(lambda a: 255 if a >= 64 else 0).getbbox()
    if not face:
        sys.exit(f"{name}: her face layer is empty; give the cut as x0 y0 x1 y1 in her drawing's pixels")
    x0, y0, x1, y1 = (face[0] - X) / s, face[1] / s, (face[2] - X) / s, face[3] / s
    wide, high = x1 - x0, y1 - y0
    return [max(0, round(x0 - SIDE * wide)), max(0, round(y0 - TOP * high)),
            min(bw, round(x1 + SIDE * wide)), min(bh, round(y1 + BELOW * high))]


def head(name, box=None):
    from PIL import Image
    stem = L.slug(name)
    big = kit.out("upscale", stem + "-4x.png")
    if not os.path.exists(big):
        sys.exit(f"{big} isn't there: run upscale first (`live2d.py upscale {name}`)")
    box = box or head_box(name)
    base = base_drawing(name)
    cut = kit.out("seethrough", stem + "-head-cut.png")
    os.makedirs(os.path.dirname(cut), exist_ok=True)
    Image.open(big).crop([v * 4 for v in box]).save(cut)
    print(f"her head: {box} in {os.path.basename(base)}'s pixels ({(box[2] - box[0]) * 4}x{(box[3] - box[1]) * 4} cut: {cut})")
    psd = see_through(cut, stem + "-head")
    kept = os.path.join(L.folder(name), f"{datetime.date.today()}-seethrough-head.psd")
    shutil.copy(psd, kept)
    crop = os.path.join(L.folder(name), "head-crop.json")
    with open(crop, "w", encoding="utf-8") as f:
        json.dump({"box_in_base": box, "scale_of_crop": 4,
                   "base": os.path.relpath(base, kit.project()).replace("\\", "/")}, f)
    print(f"kept {kept} and {crop}")
    n = short(name)
    twice = "" if L.load(name)["frame"][1] >= 2000 else f"`live2d.py layers scale {n} 2`, then "
    print(f"next: {twice}`live2d.py layers head {n} {quoted(kept)} {quoted(crop)}`, "
          f"then `live2d.py layers under {n} neck face`")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "body":
        body(args[1])
    elif len(args) in (2, 6) and args[0] == "head":
        head(args[1], [int(v) for v in args[2:]] or None)
    else:
        sys.exit(__doc__)
