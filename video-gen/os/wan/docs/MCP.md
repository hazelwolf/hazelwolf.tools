# MCP server

```bash
uv run --directory <tool dir> wan-mcp                               # stdio (default)
uv run --directory <tool dir> wan-mcp --transport streamable-http   # http://127.0.0.1:8151/mcp
```

A clip takes about 12 minutes (832x480, 5 s, 25 steps on an M5 Max), so generation runs as **background jobs**
inside the MCP process. `generate_video` queues a job and returns at once; `get_video_job` reports progress and,
when done, the MP4 path. One worker runs jobs in order. Jobs live in memory and are lost when the server process
exits (for example when the agent session ends); finished MP4s stay in `outputs/`.

Each job loads the model (2–4 s) and frees it afterwards, so an idle server holds no GPU memory. Frames are capped
at 1024x576 (area): the Wan 2.2 VAE decodes untiled and the native 1280x704 needs ~50 GB on this 48 GB Mac.

**First use:** if `check_health` returns `weights_ready: false`, run `uv run --directory <tool dir> wan-prepare` in
the background (~18 GB, not gated) and wait for `weights_ready: true`. Otherwise the first job downloads it first.

## Tools

| Tool | Params | Returns |
|---|---|---|
| `check_health` | – | `{weights_ready, active_jobs, default_steps, max_size, output_dir, ...}` |
| `generate_video` | `prompt`, `width=832`, `height=480`, `duration_s=5`, `steps?` (25), `seed?`, `image_path?`, `negative_prompt?`, `output_name?` | `{job_id, status: "queued", queue_position, ...}` |
| `get_video_job` | `job_id`, `wait_s=45` (max 300) | `{job_id, status, phase, step, total_steps, result?, error?, ...}` |
| `list_video_jobs` | – | all jobs, newest first |

`result` on a finished job: `{path, name, seed, width, height, fps, frames, duration_s, steps, audio: false,
generation_time_s, load_time_s, peak_memory_gb}`.

Example flow:

```json
{"tool": "generate_video", "arguments": {"prompt": "A paper boat drifts down a rain-filled gutter, low tracking shot", "duration_s": 4}}
{"tool": "get_video_job", "arguments": {"job_id": "a1b2c3d4e5f6"}}
```

Input errors (bad size, empty prompt, missing image) are raised by `generate_video` before anything is queued. A
job that fails while running ends with `status: "failed"` and an `error` message.

## Environment

Read from `tools/.env`: `WAN_HF_REPO`, `WAN_MODEL_PATH`, `WAN_STEPS`, `WAN_OUTPUT_DIR`, `WAN_MAX_JOBS`,
`WAN_MCP_PORT`. See the README.

## Testing

```bash
npx @modelcontextprotocol/inspector uv run --directory <tool dir> wan-mcp
```
