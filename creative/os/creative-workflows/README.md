# creative-workflows

ComfyUI, pinned as a submodule. Models, workflows, inputs, and outputs stay in this folder so the upstream checkout is not modified.

- Upstream: https://github.com/Comfy-Org/ComfyUI
- Pin: `e9027f2b30f37bb3052714eb08fcf479542f4fc0` (`upstream/`)
- Code license: GPL-3.0 (`upstream/LICENSE`)
- Weights: not in git. Each checkpoint keeps its own license.

## Layout

```
creative/os/creative-workflows/
├── upstream/    # ComfyUI submodule
├── models/      # weights (gitignored)
├── workflows/   # workflow JSON kept in git
├── docs/        # notes for those workflows and for this machine's hardware
├── input/       # uploads, including localbox (gitignored)
├── output/      # generated files (gitignored)
├── temp/        # gitignored
├── user/        # ComfyUI user state, including the in-app workflow list (gitignored)
├── custom_nodes/
└── run.sh
```

`workflows/` is the copy to commit. ComfyUI's in-app list reads `user/default/workflows/`.

## Run

From the repo root:

```bash
creative/os/creative-workflows/run.sh
```

Listens on `127.0.0.1:8188`. `--base-directory` is this tool folder, so ComfyUI uses `models`, `input`, `output`, `temp`, `user`, and `custom_nodes` here.

On a new machine, after `git submodule update --init creative/os/creative-workflows/upstream`:

```bash
cd creative/os/creative-workflows/upstream
uv sync
```

`models/` has to be copied or downloaded separately.
