---
name: comfyflow
description: >-
  Run saved ComfyUI workflows by name with named parameters (text to image, talking-person video,
  and any workflow the user built in ComfyUI). Use when the user wants to generate or edit an image or
  video with ComfyUI, run one of their ComfyUI workflows, or turn a workflow they just ran in the
  ComfyUI UI into something reusable.
---

# Comfyflow

Runs workflows on the local ComfyUI (`creative/os/creative-workflows`). ComfyUI must be running: `creative/os/creative-workflows/run.sh`. Prefer the MCP tools; fall back to the CLI.

## Steps

1. `health` — confirm ComfyUI is up. If not, tell the user to start it (or run `run.sh` in the background).
2. `list_workflows` — pick a workflow. `describe_workflow` — read its parameter names, types and defaults. Never guess parameter names.
3. `run_workflow` with `name` and `params`. Only pass what the user asked to change; defaults and a fresh random seed cover the rest.
4. Report the output path(s) from `files`. Look at images with the Read tool before claiming they are good.

```json
{"name": "z_image_turbo", "params": {"prompt": "a red fox in snow", "size.width": 832, "size.height": 1216}}
```

- `file` parameters (`image`, `audio`) take a local path. Resolve it to an absolute path first.
- Image runs take about 12 s. Video takes 1-3 minutes: call with `wait: false`, then poll `get_job`.
- The GPU has 12 GB. Do not run two heavy jobs at once; `cancel_job` stops one.
- On `error`, read the message; an unknown parameter lists the valid names.

## Adding a workflow

1. The user builds and runs the workflow once in the ComfyUI UI.
2. `import_workflow` with a `name` and `description`. Common nodes become parameters automatically.
3. To expose more inputs, the user renames nodes to `@some_name` in ComfyUI, runs once, and imports again with `overwrite: true`. Run `describe_workflow` to check the result.

Workflow files live in `creative/os/creative-workflows/workflows/api/`. CLI equivalent: `uv run --directory creative/custom/comfyflow comfyflow run <name> key=value`. Details: `docs/MCP.md`, `docs/API.md`, `docs/DESIGN.md`.
