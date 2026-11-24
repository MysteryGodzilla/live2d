# For agents

This repo is a Live2D kit: one full-body anime drawing in, a rigged Live2D model out (`.moc3` with
physics, expressions and motions), with no Cubism Editor and no hand rigging. `SKILL.md` is the same
instructions `README.md` holds, written for an agent working a character through the steps.

## Run and check
- Nothing to build: the kit is plain Python, and each step runs the tool it needs. Check what is
  installed with `python live2d.py check`.
- A character is the test. `python live2d.py status <name>` ticks off the steps done and names the
  next command; run that. Every step prints the command it actually ran, so it can be run by hand.
- A change to the rig is proven by `python live2d.py build <name>` and check sheets from the viewer
  (`python live2d.py view`, then the page's `window.sheets`; `SKILL.md`, "Checking her model without
  watching the screen"). Reload the page after each build, or a sheet shows her as she was.
- The steps that take the graphics card (`draw`, `cutout`, `upscale`, `split`, `parts eyes`,
  `layers redraw`) want it to themselves: ask before running one, and stop ComfyUI when they are
  done.

## Layout
- `live2d.py`: the one command; picks the Python each step needs.
- `scripts/`: one script per step. `kit.py` finds the project and its settings; `rig.py` decides how
  she moves and writes the `.moc3`; `acting.py` holds the expressions, emotion motions and taps.
- `references/problems.md`: every fault seen so far, why it happened and what fixed it. Add a row
  when you learn a new kind of fault.
- `vendor/`: another project's files, kept as they were written (`vendor/README.md` lists them).
  Don't edit them; the kit's own rigging that stands on top of them is `scripts/rig.py`.
- `templates/`: the files `init` copies into a project.
- `characters/`, `out/`, `live2d-kit.json`, `.env`: a project's own work, kept out of git.

## Conventions
- Each number and table in `scripts/rig.py` has a comment saying what it does and why it has that
  value. Add your reason when you change one. A fault one character has belongs in her `live2d.json`
  (read by `rig.py`, as `tucked` and `whole` are), not in a shared number.
- Keep parameter, expression and motion names the same for every character: an app's settings and
  prompts are written once against them.
- Check a change on more than one character before you call it fixed. One fix meant for everyone once
  painted dark stripes into hair that had nothing wrong with it.
- Docs write paths with forward slashes and no drive letter, and `../live2d/...` for this kit seen
  from a project. Character names and example pictures are made up.
- Never commit `live2d-kit.json`, `.env`, `characters/` or `out/`, and never a real machine's paths.
- Small commits, one per change, each saying what changed and why.
