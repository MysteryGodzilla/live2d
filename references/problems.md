# What has gone wrong before, and how it was fixed

Each row is something that happened while the first characters were made. "Handled" means the kit
now does the right thing by itself: the row is here so that you know what you are looking at if it
comes back in a new form. Commands are `python <kit>/live2d.py ...`.

## Contents
- [Running the steps](#running-the-steps)
- [Her layers](#her-layers)
- [Her head and face](#her-head-and-face)
- [Her body](#her-body)
- [The viewer and checking](#the-viewer-and-checking)
- [Limits you can't fix here](#limits-you-cant-fix-here)

## Running the steps

| You see | Why | Do |
|---|---|---|
| `split` takes 45 minutes or hours, not 10 | Another program holds part of the graphics card. 1.5 GB held by a chat model and a paint program made one pass 3.5 hours | Close them. `live2d.py check` prints how much of the card is in use. Under 2 GB used is good |
| `split` stops without a PSD | Usually out of graphics memory | Read the end of the log it names in `<out>/seethrough/`. Free the card and run it again |
| A split takes far longer than 10 minutes | ComfyUI was left running and holds part of the graphics card | `split` warns before it starts. `comfy status` says who started it: `comfy stop` if it was this project, else stop it where it was started |
| `comfy start` says "Not starting another" | A ComfyUI already answers on the settings' address, from this project or another folder | Nothing: the steps use the one that is running. `comfy status` says whose it is |
| `comfy start` says ComfyUI didn't answer | The port is taken, or a path in the settings is wrong | Read `<out>/comfy/comfy.log`. `comfy status` says which model files ComfyUI can't see |
| A drawing came out on a background although `draw` asked for a transparent one | The prompt was given whole with `--prompt`, or a style's words or a tuned model ignore the request | `pick` then says the background isn't transparent and leaves her to `cutout`. With `--prompt`, add the two sentences `draw --show` prints at the start and end of its own prompt |
| `layers check` shows her shoes (or another small part) all red: "no layer, but she's there in the drawing" | See-through left that part out. It happens with small dark shoes, whatever the background | Draw her again with bigger or lighter shoes, or paint a `footwear` layer and `layers add` it |
| `draw` says a file "isn't among ComfyUI's" models | The model or LoRA the prompt names isn't in the settings' models folder | Put it in the folder the message names. `draw ... --show` prints which model and LoRA a round will load |
| `draw --character` says there is no looks file, or she isn't in it | The project has no `<characters>/looks.json`, or no entry for her | `live2d.py init` makes the file. Add her under `characters`, as the example in it shows |
| Every drawing has her in the wrong pose, or the prompt says the framing twice | Her look in the looks file has a pose, a background or a whole prompt in it | Keep a look to hair, eyes, build and clothes. `draw ... --show` prints what is sent |
| A cut-out leaves a pale rim on light hair | The hair fades into a white background | Draw with a transparent background (`draw`'s default), and `pick` makes the cut-out from it. For your own picture: draw on light grey. Or redraw the picture on medium grey and run `cutout.py "<grey.png>+<original.png>" <out.png>` by hand |
| `build` stops with "No module named 'pydantic'" (or numpy, or PIL) | The Python that runs the build lacks it | `pip install pydantic` in See-through's environment. `live2d.py check` shows which Python the build uses |

## Her layers

| You see | Why | Do |
|---|---|---|
| `layers check` shows a big red block over her legs and skirt | An open coat: See-through painted the inside of its back into the same layer as its front | `layers lining <name> topwear "coat back" --above handwear --light <low> <high>`, then `layers repair` |
| Her legs are behind her coat's inside in the model | Handled: image2live2d sorts her body's parts its own way; the kit puts them back in her layers' order | If a part is still behind the wrong thing, her layers' own order is wrong: `layers move` |
| A long coat swings like a skirt, and her skirt doesn't move | image2live2d took the coat for a skirt | `"whole": ["topwear", "coat back"]` in her `live2d.json` |
| A gap opens between her shirt and skirt when she moves | The two layers stop where they meet | `"tucked": {"topwear": "bottomwear"}` in her `live2d.json` |
| Strands swing out from behind her that aren't in her drawing | See-through painted back hair down her back | `layers strays <name> "back hair"` |
| `build` says "0 arms that bend" | Her arms layer isn't two separate shapes: an arm touches her body, or her hands meet | Draw her again with her arms away from her sides. Or accept arms that don't move: `"whole": ["handwear"]` |
| `build` says "0 legs that bend" | Her legs touch all the way down, so they can't be cut apart | Draw her again with a gap between her legs. Without it she still stands and sways; her knees don't bend |

## Her head and face

| You see | Why | Do |
|---|---|---|
| A second jaw line under her chin | The drawing's jaw line was coloured into the layers behind her face | `layers under <name> neck face`. If it shows beside her neck when her head lifts: `layers under <name> "back hair" face` |
| Her face is soft or a little wrong close up | The whole-body split gives her face about 100 pixels | Do the head pass (step 6 of the README) |
| Her face is still soft close up after the head pass | Her frame holds her head layers at about two fifths of the head pass's size, and an older kit put them in the texture at that size | Handled for new characters: `layers head` keeps them full size and `build` uses those. For one made before: `layers sharp <name>`, then `build` |
| Her face parts are a little small after the head pass | Handled: a head cut wider than tall was once placed as a tall one | If it comes back, compare `layers check` before and after `layers head` |
| Long hair is cut off after the head pass | Handled: a layer that reaches out of the head cut stays from the whole-body pass | Nothing. `layers head` prints which layers it kept |
| Her head is tilted at rest | Handled: `build` turns her head upright from her eyes and brows, and says by how much | If it says it found no pair to read, an eye layer didn't split in two (hair over an eye). Fix her `eyewhite` and `irides` layers |
| An iris slides onto her skin, or one eye "sits funny" when she looks sideways | Handled: irises are cut off at their eye's white, and both move the same distance | If an iris is cut too early, her `eyewhite` layer is too small: `parts eyewhite <name>` draws it again |
| Half-shut eyes look see-through | Handled: lids close as solid shapes until nearly shut | Nothing |
| Her eyes close into a black line that isn't hers | She has no drawn closed eyes | `parts closed-eyes <name>` |
| Her mouth hardly opens | A closed mouth is a line a few pixels high | `parts mouth <name>` draws an open one |
| Her open mouth is plain, or the wrong kind for her | The default is one simple shape | `parts mouth-sheet <name>` shows the kit's on her face; `parts mouth <name> --style <number>`, or `--file` for a picture of your own |
| Her open mouth is too big, too small, too high or too low, or tilted wrong | Each mouth is sized and placed from her face and her closed mouth, which suits most faces but not all | `parts mouth <name> --style <n>` with `--size`, `--down`, `--right` and `--turn` (try them first with `mouth-sheet <name>` and the same options); in the GUI, the sliders in step 7 |
| Her open mouth sits crooked | Handled: her head is tilted in her drawing, and the mouth is turned with her face | If it was drawn before 2026-11-12, run `parts mouth <name>` again |
| Blush shows past her cheeks | Handled: blush is cut off at her face | Nothing |
| A hole in her blush the shape of her nose | Handled: her nose layer is often a patch of skin with the line in it, and it was over the blush. `build` puts her nose under the blush, which is see-through, so her nose shows through it | Rebuild a model made before 2026-11-13 |
| Her blush stops at a hard, straight edge | Handled: image2live2d laid a part's mesh over its solid middle only, which cut a soft blush off in a rectangle. A blush's mesh now covers all of it | Nothing |
| Her blush is too big, too far apart or too plain | Handled: `build` draws the kit's own, a small soft mark with strokes under each eye, in place of image2live2d's | `parts blush <name>` with `--style`, `--size`, `--in`, `--down` or `--turn` for another; `parts blush-sheet <name>` with the same shows the styles that way; in the GUI, the blush sliders in step 7 |
| A smile (`ParamEyeLSmile`) squashes her open eye, and its iris colours show under the lash line | Handled: image2live2d squashed the whole open eye onto an arch. Now a smile bends her closed eye's line into a "^" when her eyes are shut, and only narrows an open eye a little from below; `happy` and `TapHead` shut her eyes for it | Rebuild a model made before 2026-11-13. If the "^" shows the black stock line, run `parts closed-eyes <name>` |
| A half-open mouth looks faint, two mouths see-through over each other, or a smile goes flat as she talks | Handled: her closed line and open mouth crossfaded over the whole opening, and a smile bent her closed line only. Now they swap by a tenth open and the open mouth grows down solid from her upper lip; a smile or frown bends the open mouth too | Rebuild a model made before 2026-11-13 |
| Her smile eyes show no "^" (the Smile motion, or the smile slider alone) | A smile makes the "^" only with her eyes shut; with them open it narrows them. image2live2d's Smile motion smiled with her eyes open | Handled: the kit's own Smile motion shuts her eyes for it. In the viewer, move her eyes' open sliders to 0 with the smile. Rebuild a model made before 2026-11-13 |
| Her closed mouth is too thin or faint to see from afar, and a mouth smile or frown hardly shows | The drawing's mouth is a faint line a pixel or two thick | `parts mouth-line <name> --try`, then `parts mouth-line <name>` with `--size`, `--thick` or `--dark`, then `parts mouth <name>` again; `--back` undoes it |
| When she looks up or down, her features slide but her head's outline stays | Handled: a nod moves her whole head and hair a little (`NOD_UP`, `NOD_DOWN`), and hair below her chin less | More or less of it: those two numbers in `rig.py` |
| Dark stripes up her neck, under her chin, when her head lifts | `layers under` took its colour from just below her chin, where a choker or collar was | Handled: a column that finds another colour takes its neighbours'. Run `layers under <name> neck face` again if hers was done before 2026-11-12 and shows it. Don't run it again on a neck that looks right: it repaints the shading under her chin |
| Gaps in her glasses' rim, or thin strands of hair cut off at their tips | Handled: image2live2d kept a mesh cell only if one of nine points probed in it was on the part, and a thin line passes between them. The kit keeps every cell that holds any of the part | Nothing |
| A thin pale line round her hair or clothes, clearest on a dark background | Edge pixels that are part her and part the drawing's light background | Handled: `build` gives such a pixel the colour of her own pixels just inside it (hair, skin and clothes only; it says how many). `"rims": false` in her `live2d.json` switches it off |
| Her glasses drift off her eyes when her head turns | Handled: something worn across both eyes moves with them | If hers aren't found, the layer isn't called `eyewear` or doesn't span both eyes |
| A look down and sideways makes her face look like it is melting | Features that slide too far over a face that stays | Lower the numbers in `TURNS`. Head moves are for looking at things: a small slide is enough |

## Her body

| You see | Why | Do |
|---|---|---|
| All her hair swings as one board | Handled: a sheet of hair is divided into sections sized from her face, each on a pendulum of its own, and her body's sway moves them as well as her head | More or fewer: `HAIR_SECTION` and `HAIR_SECTIONS` in `rig.py`. `build` prints how many it made |
| Her legs leave her shoes, or her stockings swing | Handled: `legwear` and `footwear` are part of her, not cloth | If a new layer swings that shouldn't (socks under another name), add its name to `STILL` in `rig.py` |
| All of her slides over the floor when she sways | Handled: her body's moves keep her feet planted | Nothing |
| A lifted arm drags her skirt | Handled: arm parameters move only arms | Nothing |
| A bent arm comes apart at the elbow, or looks stumpy | Handled: an arm is a chain, bent over a short band | Nothing |
| Her hand goes behind her skirt when her elbow bends inward | Handled: a forearm bent inward comes in front of her clothes | Nothing |
| A dark step on a limb's outline at the joint | Handled: image2live2d's own limb cut is off; the kit cuts along the mesh | Nothing |
| Her whole body bounces from the belly down when she breathes | Handled: breath starts at her waist, and her chest's bounce is a small patch | Lower `BREATH` or `BUST` for less |
| Her knees or hips bend at the wrong height | She is built differently from the first characters | Change `HIPS`, `KNEE`, `ANKLE` in `rig.py`. `build` prints where it put them |

## The viewer and checking

| You see | Why | Do |
|---|---|---|
| Her parts are all over the place after a rebuild | The page kept her old texture | Handled in the kit's viewer. In another viewer or an app, reload or import her again |
| A check sheet shows her as she was before the last build | The page keeps the model it has loaded | Reload the page after every `build`, then make the sheet |
| A check picture shows every pose the same | The page was hidden, so the browser stopped drawing | Use the page's `sheets` functions: they read the pixels back and work while hidden |
| A small second figure behind her | A model left on the stage by an earlier load | Handled in the kit's viewer |
| A part is missing only when she moves | A part's points left its deformer, or two layers no longer overlap | Hold the pose with the sliders and look at which part it is. Then see "Her layers" |

## Limits you can't fix here

- She has one drawing. Nothing shows the back of a hand, a different hand shape, or her side.
- Her hair swings in sections side by side, not strand by strand: two tails swing apart, but a
  lock that crosses in front of another moves with whatever is behind it. Her bangs and the locks
  beside her face are one layer, so they blend into each other where they meet.
- Elbows bend up to 70 degrees outward and 80 inward. Hands can't reach her face.
- `ParamEyeLOpen` closes the eye on the left of the picture. Cubism's own models close the
  character's left eye, which is on the right. A wink from a shared motion file comes out mirrored.
- The `.cmo3` file `build` writes is image2live2d's own rig, without the kit's changes. It is only
  useful as a starting point in Cubism Editor. The free edition can't save a model this size.
- An app may draw her a little differently from the viewer. Try her there before you finish.
