---
name: live2d-from-drawing
description: Make a rigged Live2D model (a .moc3 bundle with physics, expressions and motions) from one full-body anime drawing, with no Cubism Editor and no hand rigging, using this kit's scripts - candidate drawings with Qwen Image, cut-out, upscale, See-through layer split, layer fixes, rig and build, then checking in a viewer. Use this whenever the user wants a Live2D model, avatar, VTuber model or rig of a character, wants another character put through this pipeline, says something looks wrong with a model made here (a second jaw line, a gap at the waist, eyes or irises, arms, knees, hair, a tilted head), or wants its expressions, motions or the way it moves changed - even if they only say "make her a model" or "fix her eyes".
---

# Live2D model from one drawing

This kit takes one full-body drawing of a character to a Live2D model that an app such as AIRI or
Open-LLM-VTuber loads. The scripts do the work. Your part is to run the steps in order, look at
the result of each one, and fix what is off before the next step builds on it. A fault you let
through early (a layer in the wrong place) shows up later as something much harder to trace (a leg
behind a coat).

Everything is one command, run from inside the project:

```
python <this folder>/live2d.py <step> <name> ...
```

`<name>` is the character's folder name. `live2d.py` picks the Python each step needs and prints
the command it runs. Read `README.md` in this folder once before your first character: it has the
downloads, the settings file, every step with its command, and the table of layer fixes. This file
is how to work through it well.

There is also a GUI for people (`live2d.py gui`: the same steps as buttons in a page); an agent should use the commands.

## Before anything

1. Run `live2d.py check`. It says what is installed and what is missing for which step. If
   something is missing, tell the user what and where it comes from (README, "What you need").
   Downloads are many gigabytes: ask before you start one. In a project the kit has not been used
   in yet (check says there is no `live2d-kit.json`), run `live2d.py init` first, from the
   project's top folder. It makes the settings file, a looks file and this skill's pointer, and
   changes nothing that is already there. `init --like <another project>` copies the tools' paths
   from a project that already has them.
2. Run `live2d.py status <name>`. It ticks off the steps done and names the next command. Use it
   whenever you pick a character up again, rather than guessing from the files.
3. Ask the user before a step that takes the graphics card (draw, cutout, upscale, split). Those
   steps need the card to themselves, and the user may be running something on it. `split` takes about
   10 minutes a pass on a free card, and can take hours if anything else holds part of it: say
   so, and run it in the background.
4. `draw --runpod` costs money. Use it only when the user asks for it.
5. Start and stop only what you started. `live2d.py comfy status` says whether ComfyUI is
   running and who started it: this project, or another folder (then it is someone else's: use
   it, but don't stop it). `comfy stop` stops only the one this project's `comfy start` started.
   Stop yours when the drawing, cut-out and upscale steps are done.

## The steps, and what to check after each

| Step | Command | It is right when |
|---|---|---|
| Draw | `comfy start`, then `draw <round> --character <name> --seeds ...` | The user picks one. Show them the contact sheet. Don't pick for them unless they ask |
| Pick | `pick <name> <picture>` | The drawing fits "A drawing that rigs" in the README. If it doesn't (arms on her body, legs together, a prop in her hand), say what will go wrong before you go on |
| Cut-out, upscale | `cutout <name>`, `upscale <name>`, `comfy stop` | `full/cutout.png` shows all of her and no background. A drawing from `draw` has its own transparency: `pick` already made the cut-out, so `cutout` does nothing and only `upscale` is needed |
| Split | `split <name> body` | It prints her layers. Expect about 17: hair, face, eyes, brows, nose, mouth, neck, clothes, arms, legs, shoes |
| Check layers | `layers check <name>` | The count is a few thousand pixels of thin outline. Look at the picture it saves. A solid block of red is a layer covering what it shouldn't |
| Head pass | `split <name> head`, `layers scale <name> 2`, `layers head ...`, `layers under <name> neck face` | `layers check` again: the count should not jump. Her face layer should line up with her drawing's face |
| Parts | `parts closed-eyes <name>`, `parts mouth <name>` | Her layers now include `eye_close` and `mouth_open`. Which open mouth and which blush she has is the user's taste: make `parts mouth-sheet <name>` and `parts blush-sheet <name>`, show them the two pictures, and let them pick a number (the README's "Mouths and blushes"). If the mouth is too big, small, high, low or tilted, `--size`, `--down`, `--right` and `--turn` fix it, on `mouth-sheet` first to show them; the blush takes `--size`, `--in`, `--down` and `--turn` the same way. `parts mouth-oh <name>` gives her an "O" mouth for scared and surprised. For another iris (sharper, a clean oval, a heart or a slit or a crest, another colour), `parts iris-sheet <name>` shows the kit's irises in her own eyes and `parts iris <name> --style <number>` gives her one, with `--colour` (`hers` keeps each eye's own colour), `--tall`, `--size`, `--mirror` and two numbers or colours for an eye each (README, "Her irises, from the kit"); no card, and the choice is the user's. If her irises look soft or flat (upscaled), `parts eyes <name> --try` (ComfyUI and the card: ask first) makes a sheet of redrawn eyes to show the user; they pick a number, `parts eyes <name> <number>`. `--seeds`, `--strength`, `--colour` and `--iris-only` are theirs to choose (README, "Her eyes, drawn again"). If her closed mouth is too thin or faint to see, `parts mouth-line <name> --try` shows a redraw, `parts mouth-line <name>` makes it, then `parts mouth <name>` again |
| Build | `build <name>` | Read what it prints (below) |
| View | `view`, then check sheets (below) | The list in the README, "Trying her model" |

The character's description comes from the project's looks file (`check` prints where it is; the
README's "Looks and styles" has its format). Write her look there, or change it there, before you
draw: it is the one place that says what she looks like, so the next round and the next agent draw
the same character. A look is her hair, eyes, build and clothes only. The kit adds the framing and
the pose itself, and a look that repeats them, or asks for another pose, works against the rig.
`draw ... --show` prints the whole prompt without drawing: read it before you spend the graphics
card on a round. `--look "..."` is for a one-off.

After the split, look at each layer picture in `<characters>/<name>/layers/full/parts/` once. You
are looking for three things: a layer that holds two things that must move apart (a coat's front
and the inside of its back), a layer in the wrong order, and a pair (arms, legs, eyes) that came
out as one shape. The README's "Fixing the layers" says what to do for each. Put the reason for a
setting in her `live2d.json` under `"why"`: the next person can't see what you saw.

## Reading what build prints

- `head: her head turned -9.9 degrees ...`: how far it straightened her. "No pair of eyes or brows"
  means an eye layer didn't split into left and right: fix that layer first.
- `head turn: 13_face_base as face; 16_accessory as glasses; ...`: what it took each head part to
  be. A part taken for the wrong thing moves wrongly: glasses that aren't listed as glasses will
  drift off her eyes.
- `body: her feet at ..., knees ..., hips ..., neck ...; 2 arms that bend, 2 legs that bend; ...`:
  0 arms or 0 legs means that pair is one shape in her layers. Feet at 0.000 means a stray pixel
  at the bottom of a layer.
- `hair: 6 sections that swing each by itself (...)`: how her hair was divided. One section for
  the front and one for the back means her hair is narrow, or its layer is in pieces: that is
  not a fault.
- `in the texture at the head pass's own size: face, eyelash, ...`: the head parts that went into
  her texture sharp. No such line means she has no sharp copies: `layers sharp <name>` makes them
  from her kept head PSD. `changed since the head pass` names head layers edited after it, which
  are used at her frame's size: that is right, not a fault.

## Checking her model without watching the screen

Start the viewer (`live2d.py view`, in the background) and open
`http://127.0.0.1:8777/live2d/` in a browser tool. The page has `window.sheets`, which draws
labelled pictures of held poses, motion frames and expressions and saves them as files you can
read. It reads the renderer's pixels back, so it is right even when the page is hidden. A
screenshot of a hidden page is not: it shows stale frames.

```js
const u = "/live2d/models/akane-full/model/model.model3.json";
await sheets.poses([
  ["face", u, /face/i, 2.6, [["rest", {}], ["turn", {ParamAngleX: 30, ParamEyeBallX: 1}],
                              ["half shut", {ParamEyeLOpen: 0.5, ParamEyeROpen: 0.5}], ["tilt", {ParamAngleZ: -30}]]],
  ["body", u, [0.15, 0, 0.85, 1], 0, [["rest", {}], ["sway", {ParamBodyAngleX: 10}],
                                      ["arms", {ParamArmLA: 10, ParamArmLB: -10}], ["knee", {ParamLegLB: 10}]]],
], 200, 300);
await sheets.save("akane-check");                 // -> <out>/live2d/checks/akane-check.png
await sheets.expressions(u, ["(none)", "happy", "tired", "blushing", "angry", "scared"], /face/i, 1.6, 133, 170);
await sheets.save("akane-expressions");
await sheets.motion(u, "TapHead", /face/i, 1.6, 133, 170, 6, 13);
await sheets.save("akane-taphead");
sheets.done();
```

A frame is `[x0, y0, x1, y1]` in shares of the model's box, or a pattern for a drawable's name
(`/face/i`, `/neck/i`) with a zoom. Pass a green background (`"#30c060"` as the last argument of
`poses`) when you are looking for gaps: a gap shows green.

Look closely at the pictures. Zoom in on the place a fault would be (the chin, the waist, an
eye) rather than judging from a whole-figure thumbnail: most of the faults found so far were a few
pixels wide. Check both ends of each movement, and two movements together (a turn with a look, a
lift with a bend), because that is where parts come away from each other.

When you show the user a result, send them the picture and say plainly what you checked and what
you did not. The viewer is not the app: say so if you have not seen her in the app.

## When something looks wrong

1. Find which part it is. Hold the pose with the sliders, or make a sheet zoomed on it.
2. Decide where the fault lives. It is in her **layers** if the part's picture is wrong, cut
   short, in the wrong order, or carries something that belongs to another part. It is in the
   **rig** if her layers are right and she moves wrongly.
3. Look it up in `references/problems.md`. It lists what has gone wrong before, why, and the fix.
4. Layer faults are fixed with `layers` commands or her `live2d.json`, then `build` again.
5. Rig faults that every character would have are fixed in `scripts/rig.py`, where each number
   and table has a comment saying why it is what it is. Add your reason when you change one. A
   fault only one character has belongs in her `live2d.json`, read by `rig.py`.
6. Build, reload the page, make the same sheet again, and compare. The reload matters: the page
   keeps the model it loaded, so a sheet made without it shows her as she was before the build.

Be careful with a fix that touches more than you meant. Before you change a layer for every
character, check whether the others had the problem: one fix here painted dark stripes into hair
that had nothing wrong with it.

## Changing how she moves, or what she can show

The README's "Changing how she moves" maps each thing to its name in `scripts/rig.py`.
Expressions are `EXPRESSIONS`, the click reactions are `TAPS`, and the emotion motions an app plays
are `EMOTIONS` and `BORROWED`. Keep the names the same for every character, so the app's settings
and prompts are written once.

How far to move things is the user's taste. The standing guidance from this kit's first user:
head movement is for looking at things, so features slide a little and the irises do most of the
looking; body movement is subtle and keeps her feet on the floor. Show a picture and let them
decide.

## Finishing

- Tell the user where her model is: `<out>/live2d/<name>-full.zip` is what an app imports.
- Keep her drawing, cut-out, upscaled drawing and everything in `layers/full/` in version
  control. Everything in `<out>` can be made again.
- If you learned something a future run needs (a new kind of fault and its fix), add a row to
  `references/problems.md`.
- Stop the viewer and ComfyUI if you started them.
