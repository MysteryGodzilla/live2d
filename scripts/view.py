"""The kit's viewer: a page on this PC that draws each built model with the real Cubism renderer,
with buttons for her motions and expressions and a slider for each of her parameters.
Standard library only.

usage:
  view.py [port]        (8777 unless given) then open http://127.0.0.1:<port>/live2d/

It shows every <out>/live2d/<name>/model/model.model3.json, and the models in the settings'
"examples" folder if there is one (each <example>/runtime/*.model3.json), to compare with. The page
loads pixi.js, pixi-live2d-display and Live2D's Cubism Core from the internet. Nothing is cached, so
a rebuilt model shows on reload. It listens on this PC only, and a POST has to come from its own page.

The page's "Change an expression" saves a character's own expressions into her layers' live2d.json
(acting.py says how) and writes them into her model again: GET /live2d/acting/<model> gives the
kit's and hers, and POST /live2d/acting/<model>/<expression> with {"pose": {...}} saves one, or
with {"pose": null} puts the kit's back.

The page's Sheet button, and sheets.save(name) from its console, save a picture to
<out>/live2d/checks/<name>.png: see the top of viewer/index.html for the check sheets an agent can
make without looking at the screen.
"""
import glob, json, os, re, subprocess, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acting
import kit

PAGE = os.path.join(kit.SCRIPTS, "viewer", "index.html")
TYPES = {".html": "text/html; charset=utf-8", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg",
         ".moc3": "application/octet-stream", ".js": "text/javascript"}


def models():
    out = []
    for path in sorted(glob.glob(os.path.join(kit.out("live2d"), "*", "model", "model.model3.json"))):
        name = os.path.basename(os.path.dirname(os.path.dirname(path)))
        out.append({"name": name, "url": f"/live2d/models/{name}/model/model.model3.json"})
    examples = kit.settings().get("examples")
    if examples:
        folder = os.path.join(kit.project(), examples)
        for path in sorted(glob.glob(os.path.join(folder, "*", "runtime", "*.model3.json"))):
            name = os.path.basename(os.path.dirname(os.path.dirname(path)))
            out.append({"name": name, "url": f"/live2d/examples/{name}/runtime/{os.path.basename(path)}", "example": True})
    return out


class Viewer(BaseHTTPRequestHandler):
    def send(self, status, body=b"", kind="text/plain; charset=utf-8", **headers):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def file(self, root, rest):
        """A file under root, or nothing if the address climbs out of it."""
        path = os.path.realpath(os.path.join(root, *unquote(rest).split("/")))
        if not path.startswith(os.path.realpath(root) + os.sep) or not os.path.isfile(path):
            return self.send(404, b"not found")
        with open(path, "rb") as f:
            self.send(200, f.read(), TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/live2d"):
            return self.send(302, Location="/live2d/")
        if path == "/live2d/":
            with open(PAGE, "rb") as f:
                return self.send(200, f.read(), TYPES[".html"])
        if path == "/live2d/models.json":
            return self.send(200, json.dumps(models()).encode(), TYPES[".json"])
        if path.startswith("/live2d/models/"):
            return self.file(kit.out("live2d"), path[len("/live2d/models/"):])
        m = re.fullmatch(r"/live2d/acting/([A-Za-z0-9][A-Za-z0-9._-]{0,80})", path)
        if m:
            name = acting.character_of(m.group(1))
            if not name:
                return self.send(404, b"no character for this model: build her again")
            mine = (acting.settings(name).get("expressions") or {})
            return self.send(200, json.dumps({"name": name, "hers": mine, "kit": {k: acting.as_json(v) for k, v in acting.EXPRESSIONS.items()},
                                              "rests_at_one": list(acting.RESTS_AT_ONE)}).encode(), TYPES[".json"])
        if path.startswith("/live2d/examples/") and kit.settings().get("examples"):
            return self.file(os.path.join(kit.project(), kit.settings()["examples"]), path[len("/live2d/examples/"):])
        self.send(404, b"not found")

    def do_POST(self):
        path = urlparse(self.path).path
        host = self.headers.get("Host", "")
        if self.headers.get("Origin") != "http://" + host:
            return self.send(403, b"posts only from this page")
        m = re.fullmatch(r"/live2d/acting/([A-Za-z0-9][A-Za-z0-9._-]{0,80})/(%s)" % acting.EXPRESSION_NAME, unquote(path))
        if m:
            return self.save_expression(m.group(1), m.group(2))
        m = re.fullmatch(r"/live2d/save/([A-Za-z0-9][A-Za-z0-9._-]{0,80})", unquote(path))
        size = int(self.headers.get("Content-Length") or 0)
        if not m or not 0 < size < 40_000_000:
            return self.send(400, b"a name of letters, digits, dots and dashes, and a picture under 40 MB")
        body = self.rfile.read(size)
        if body[:8] != b"\x89PNG\r\n\x1a\n":
            return self.send(400, b"not a PNG")
        folder = kit.out("live2d", "checks")
        os.makedirs(folder, exist_ok=True)
        saved = os.path.join(folder, m.group(1) + ".png")
        with open(saved, "wb") as f:
            f.write(body)
        self.send(200, ("saved " + saved).encode())

    def save_expression(self, model, exp):
        """Her own expression saved (or the kit's put back), and her model's acting written again."""
        name = acting.character_of(model)
        size = int(self.headers.get("Content-Length") or 0)
        if not name:
            return self.send(404, b"no character for this model: build her again")
        if not 0 < size < 20_000:
            return self.send(400, b"an expression as JSON, under 20 KB")
        try:
            pose = json.loads(self.rfile.read(size)).get("pose")
            acting.save_expression(name, exp, pose)
        except (ValueError, AttributeError) as e:
            return self.send(400, str(e).encode())
        done = subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(kit.SCRIPTS, "acting.py"), "acting", name],
                              cwd=kit.project(), capture_output=True, text=True, timeout=120)
        said = (done.stdout + done.stderr).strip()
        self.send(200 if done.returncode == 0 else 500, said.encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and not sys.argv[1].isdigit()):
        sys.exit(__doc__)
    port = int(sys.argv[1]) if len(sys.argv) == 2 else 8777
    server = ThreadingHTTPServer(("127.0.0.1", port), Viewer)
    print(f"Live2D viewer: http://127.0.0.1:{port}/live2d/  ({len(models())} models; Ctrl+C stops it)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
