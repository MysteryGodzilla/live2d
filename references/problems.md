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
| `split` stops without a PSD | Usually out of graphics memory | Read the end of the log it names in `<out>/seethrough/`: a traceback about ports or a proxy is the next row, not the card. Otherwise free the card and run it again |
| `split` dies in a minute, its log ending in `httpx.InvalidURL: Invalid port` | A bracketed IPv6 entry (`[::1]`, as Windows ships) in `NO_PROXY`: httpx parses every entry while its client is built, before `HF_HUB_OFFLINE` can take effect | Handled: `split` unbrackets `NO_PROXY` for the See-through child. On an older kit, put `NO_PROXY=localhost,127.0.0.1,::1` in front of the command |
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
| `<step> <subcommand> --help` dies on a missing `layers.json` | Handled: `--help` was taken as the character name | Any `-h`/`--help` in a step's arguments now prints that step script's docstring, where its flags are written |

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
| A second jaw line under her chin when her head lifts or her hair sways | `layers scale` colours each layer from the drawing wherever it is on top. The whole-body face was a little smaller than the drawn one, so the drawing's jaw line and a sliver of neck went onto the layers behind it (her back hair, bits of chin on her shirt); the head pass's face hides them only at rest | Handled for new characters: `layers head` cleans them (its seams pass): cleared where the layer below is what the drawing shows, given the layer's own See-through colour where her face hides them; under her face's soft edge, a pixel nearer her face's line than what is below it (the tip of her chin line on her shirt) is cleared. For one made before: `layers seams <name>`, then `build`. Under her chin itself, `layers under <name> neck face` as before |
| A faint line across her neck where her collar or shirt meets it | `layers scale` gives the drawing's colour only where a layer is solid; a shirt's soft top edge kept See-through's darker colour over skin the drawing shows as one | Handled the same way: a layer's soft edge across her neck, where the drawing runs on through it, takes the drawing's colour (only over her neck) |
| Her hair swings out over her neck under her chin | Her back hair was moved above her neck (a braid in front of her coat), so the hair hidden under her chin covers the neck as it swings | Handled the same way: hair above her neck is cleared where her face hides it over her neck. What didn't work, 2026-11-21: painting skin onto her hair hides the seam at rest but the skin then moves with her hair; moving the whole neck above her clothes covers her collar |
| Ragged pale or dark streaks down the sides of her neck, a dark block where her collar meets it, or a hair strand over her shirt that lost its outline, after `layers seams` (its first versions, 2026-11-24) | It touched more than the seam: it took the line drawn down her neck's sides for hair colour and painted it skin; it cleared a shirt that runs up under her chin wherever See-through had painted collar there, in bits the build's pale-rim cleaning then dyed collar-navy; and it counted every head layer, so her front hair where it hangs over her shirt had the line along it painted in her shirt's colour | Now only her face counts; her neck itself and her hair below her face are left as they are; a layer is cleared only where its drawn colour is one See-through painted nowhere on it close by (skin on hair, not skin over skin); and soft edges are recoloured only across her neck. Mystery's eye was right: the drawing's colours on her neck looked better than any touching up of them. Check a seams change against the model before it, at rest and with her head turned, pixel by pixel: anything that changed away from the seam is a fault |
| Her face is soft or a little wrong close up | The whole-body split gives her face about 100 pixels | Do the head pass (step 6 of the README) |
| Her face is still soft close up after the head pass | Her frame holds her head layers at about two fifths of the head pass's size, and an older kit put them in the texture at that size | Handled for new characters: `layers head` keeps them full size and `build` uses those. For one made before: `layers sharp <name>`, then `build` |
| Her face parts are a little small after the head pass | Handled: a head cut wider than tall was once placed as a tall one | If it comes back, compare `layers check` before and after `layers head` |
| Long hair is cut off after the head pass | Handled: a layer that reaches out of the head cut stays from the whole-body pass | Nothing. `layers head` prints which layers it kept |
| Her head is tilted at rest | Handled: `build` turns her head upright from her eyes and brows, and says by how much | If it says it found no pair to read, an eye layer didn't split in two (hair over an eye). Fix her `eyewhite` and `irides` layers |
| An iris slides onto her skin, or one eye "sits funny" when she looks sideways | Handled: irises are cut off at their eye's white, and both move the same distance | If an iris is cut too early, her `eyewhite` layer is too small: `parts eyewhite <name>` draws it again |
| Half-shut eyes look see-through | Handled: lids close as solid shapes until nearly shut | Nothing |
| Her eyes close into a black line that isn't hers | She has no drawn closed eyes | `parts closed-eyes <name>` |
| Her irises look soft and flat: no clear pupil, rim or shine | The upscale keeps an iris's shape but not its detail | `parts eyes <name> --try`, then take a number. `--colour` for another eye colour, `--iris-only` for a new iris that keeps her lashes |
| A half-shut eye (as in `tired`) has a thin upper lash with a thin line just over it | An older build squashed her whole open eye flat as it shut, her lash and the fold drawn over it together | `build` again: her upper lash now rides down on the top of her eye's opening and keeps its thickness, the fold with it (rig.py, `lid_fall`) |
| An expression mark (sweat drop, anger mark, tears, sparkles, gloom) is in the wrong place or the wrong size | They are placed from her eyes, which suits most faces, not all | `"fx": {"sweat": {"size": 1.3, "right": 0.2, "down": -0.1}}` in her layers' `live2d.json` (eye widths), `parts fx-sheet <name>` to look, then `build` |
| The gloom stops above her eyes, or ends in a faint straight line across her face | Handled: it faded out at her lashes, and the alpha floor cut its last step off where that fell on bare skin | `build` again: it carries over her whole eye and fades out on the cheek below, its tail kept under the floor (fx.py, `gloom`) |
| The head pass printed its taken layers but her face stayed soft close up | Handled: a head layer the PSD simply lacked (face, on one run) was skipped in silence | `layers head` now names what the PSD lacked; such a layer stays at the whole-body pass's size |
| `layers sharp` dropped sharp copies the last build had kept | Handled: two thresholds for one question — 0.03 for keeping a copy, 0.08 for using it | One number, `kit.SHARP_SAME`, read by both; the remedy can no longer downgrade a model |
| `parts iris --colour hers` washed a strong eye colour to pastel | Handled: her shine and any pale skin in the cut dragged the saturation and value means toward white | `main_colour` answers for those two from colourful pixels only (iris.py) |
| Her puffed cheeks (the `pouting` expression) go too far out, or hardly show | The kit's amount suits a face of middling width | `"cheek_puff": 1.3` (or 0.7) in her layers' `live2d.json`, from 0 to 2, then `build` |
| Her iris has a bumpy or notched outline, or she should have another kind of iris (a heart, a slit, a crest) | The split cut her iris with lash shading or a lock of hair joined on; one drawing gives one iris | `parts iris-sheet <name>`, then `parts iris <name> --style <number>`: an iris from the kit in a clean oval fitted to hers. `--colour hers` keeps each eye's own colour, `--tall 1.12` makes it taller. `parts iris <name> --back` puts her own back |
| A kit iris shows a dark band at its top when she looks down | The picture has the upper lid's shadow drawn in it | Another iris, or rub the band out of the picture in `scripts/irises/` (a clear patch is painted in from the iris beside it) |
| A redrawn eye has skin inside the iris, or a lash line that moved | The strength was too high for a whole-eye redraw: it drew her eyes anew, moved | A lower strength, or `--iris-only`, which cuts the iris out of the redraw and fits it onto hers. `parts eyes <name> --back` puts her own back |
| `--iris-only` keeps her old iris for one eye ("an eye's iris wasn't found") | The redraw's iris isn't close enough to her iris's colour to be found | Give `--colour` (her iris and the prompt then agree), or another seed |
| At half shut, a thin line stays above her lash | Her lash layer's upper edge (a crease or loose strokes) doesn't come down with the lid. Her own eyes have it too | Not fixed yet: lashes that bend as the eye shuts are planned. A redraw keeps only new lash strokes that join her lash line, so it adds none |
| Her mouth hardly opens | A closed mouth is a line a few pixels high | `parts mouth <name>` draws an open one |
| Her open mouth is plain, or the wrong kind for her | The default is one simple shape | `parts mouth-sheet <name>` shows the kit's on her face; `parts mouth <name> --style <number>`, or `--file` for a picture of your own |
| Her open mouth is too big, too small, too high or too low, or tilted wrong | Each mouth is sized and placed from her face and her closed mouth, which suits most faces but not all | `parts mouth <name> --style <n>` with `--size`, `--down`, `--right` and `--turn` (try them first with `mouth-sheet <name>` and the same options); in the GUI, the sliders in step 7 |
| Her open mouth sits crooked | Handled: her head is tilted in her drawing, and the mouth is turned with her face | If it was drawn before 2026-11-12, run `parts mouth <name>` again |
| Two mouths at once in `pouting`: the pout drawn over her closed line | Handled: image2live2d halves her closed line into two parts whose ids carry no layer name, so the pout swap found nothing to hide and hid only the pout itself | `build` again: the swap takes her closed line by its role, halves and all (rig.py, `pout`) |
| Her closed mouth folds into a deep V or Λ at `MouthForm` ±1, and in most expressions | Handled: the corner lift was scaled by a mouth box (a landmark's, or a mesh's) far taller than the drawn line, so a line a few pixels thick folded as deep as it is wide | `build` again: the lift now comes from each mouth part's own drawn pixels, a share of the line's thickness, on a square ramp (rig.py, `mouth_form`) |
| A ghost second closed line beside hers after `parts mouth-line`, on a character with a head pass | The head pass's sharp copy of her mouth predates the redraw and sits within the match tolerance, so `build` draws the old pixels over the moved mesh | Redraw her mouth before the head pass. After one: delete `parts/mouth_close@head.png` and its entry in `sharp.json`, then `build` — her mouth stays at her frame's size, without the ghost |
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
