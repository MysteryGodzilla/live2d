# Code from other projects, carried in this kit

## image2live2d

- **Project:** [image2live2d](https://github.com/Wzhang3912/image2live2d) by Wzhang3912
- **Licence:** Apache License 2.0. Its full text is in `image2live2d/LICENSE`.
- **Version:** commit `714e7cc` ("Add Docker startup and local GPU model setup (#97)"), package version 0.2.0
- **Taken on:** 2026-11-12

### What is here

- `image2live2d/`: 67 of the 76 Python files of its `src/image2live2d/` package. These are the
  files its build path loads when it turns a folder of layers into a Cubism bundle: the layer
  loader, the mesh builder, the structure and rig authoring, physics, motions, the synthesised
  parts, and the Live2D writers (`.moc3`, `model3.json`, `physics3.json`, `motion3.json`,
  `cdi3.json`, `.cmo3`).
- `tools/emit_cubism_bundle.py`: its command-line tool that runs that path.

Every file is a copy of the original with no changes. Nothing was edited inside them.

### What was left out

Its web app and service, Docker files, tests, templates and media, its other command-line tools,
and nine modules the build path doesn't load: `__main__.py`, `app/` (three files), `batch.py`,
`gpu.py`, `irr/example.py`, `preview.py` and `samples.py`.

### How this kit uses it

`scripts/rig.py` puts this folder first on Python's path and imports `image2live2d` from it. It
calls the pipeline to make the first rig from a character's layers. Then, at run time and without
touching these files, it replaces some of its functions with the kit's own: how the mouth opens,
how a blush's mesh is built, the limb cut, and the whole `.moc3` contents writer (`rig_to_moc3`),
which adds warp deformers, clipping masks and draw-order keys. `rig.py` says where each one is
replaced and why.

### Thanks

image2live2d is what made a Live2D model from layers possible here without Cubism Editor. The
kit's changes are built on top of it, not in place of it. If you want the original tool, with its
own web app and its own See-through step, use the link above.

To move to a newer image2live2d: copy the same files from the new commit over these, run a build,
and check the model in the viewer. `rig.py` replaces functions by name, so a renamed one shows up
as an error at the start of a build.
