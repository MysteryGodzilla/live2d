"""A drawing made bigger with an anime upscaler on the kit's ComfyUI: Real-ESRGAN's
RealESRGAN_x4plus_anime_6B (BSD-3, xinntao/Real-ESRGAN release v0.2.2.4, in the models folder's
upscale_models/), four times, then scaled to the size asked for. Sharper lines than resizing, for See-through's head pass
and the full-size Live2D frame; it adds no detail the drawing doesn't have.

usage (`live2d.py upscale <name>` runs it on a character's drawing; by hand, with ComfyUI's own
Python, which has Pillow, and ComfyUI started):
  <comfyui python> -I upscale.py <in.png> <out.png> [scale]
scale is 4 (the model's own) unless given, such as 2."""
import base64, io, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import comfy

MODEL = "RealESRGAN_x4plus_anime_6B.pth"


def upscale(backend, path):
    wf = {
        "11": {"class_type": "LoadImage", "inputs": {"image": "src.png"}},
        "1": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": MODEL}},
        "2": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["1", 0], "image": ["11", 0]}},
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "live2d-kit-upscale", "images": ["2", 0]}},
    }
    extra = {"images": [{"name": "src.png", "image": base64.b64encode(open(path, "rb").read()).decode()}]}
    return Image.open(io.BytesIO(backend.picture(wf, extra, path))).convert("RGB")


def main(args):
    if len(args) not in (2, 3):
        sys.exit(__doc__)
    src, dst = args[:2]
    scale = float(args[2]) if len(args) == 3 else 4
    im = Image.open(src)
    big = upscale(comfy.Local(), src)
    size = (round(im.width * scale), round(im.height * scale))
    if big.size != size:
        big = big.resize(size, Image.LANCZOS)
    big.save(dst, optimize=True)
    print(f"{dst}: {big.width}x{big.height}")


if __name__ == "__main__":
    main(sys.argv[1:])
