# Security notes

## Intended use: local only

The HTTP APIs and MCP servers in this repo are built for **local use by one user**. They bind to `127.0.0.1` by
default. Do not expose them to a network or the internet.

Known properties you should understand before changing that:

- **Arbitrary file reads.** Endpoints that accept `{"path": ...}` for input audio read any file the server process
  can read, and outputs are written to the tool's `outputs/` folder. This is convenient for local agents and unsafe
  for untrusted callers.
- **No authentication by default.** The AudioCraft API supports an optional bearer token
  (`AUDIOCRAFT_API_KEY` in `.env`). Set it if the port is reachable by anything other than you.
- **Model code and checkpoints.** Weights are downloaded from the model owners' repositories and loaded with
  pickle-based loaders; load only checkpoints you trust. User-supplied tensor files are loaded with
  `weights_only=True`.
- **GPU/CPU exhaustion.** Generation is expensive; there are request limits (duration, batch size) but no rate
  limiting.

## Secrets

- Keep keys only in the git-ignored `.env`; `.env.example` holds empty placeholders.
- A Gitleaks pre-commit hook blocks commits that contain secrets. If a real key is ever committed, rotate it
  immediately; removing it from history is not enough.

## Reporting a vulnerability

Open a private security advisory on the repository host, or contact the maintainers privately. Please do not file
public issues for security problems.
