# Evals

Comparisons of the models behind our tools against other open models, run locally on the same hardware and settings.
Each eval is its own uv project with its own `.venv`, like a tool, but has no API, MCP server or skill: it is run
by a person (or an agent) from the command line.

| Eval | Compares | How it is scored |
|---|---|---|
| [image-gen](image-gen/README.md) | Z-Image-Turbo vs Boogu Image Turbo, the two models `image-gen/os/imagegen` serves | Blind side-by-side review, plus speed and peak memory |

Rules (same as tools): uv only, weights in a gitignored `models/`, results in a gitignored `outputs/`, settings in
the root `.env` prefixed with the eval name, no machine-specific paths. An eval reuses the pinned upstream of the
tool it measures instead of adding a second submodule. Record every extra model's license in
`docs/legal/LICENSE-NOTES.md`.
