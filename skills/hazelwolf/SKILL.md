---
name: hazelwolf
description: >-
  Local HazelWolf AI tools, usable from any project: text-to-image and img2img with Z-Image, plus Boogu for
  text-heavy images like posters and menus (imagegen), LTX-2.5
  text/image-to-video with audio (ltx), Wan 2.2 Apache-licensed text/image-to-video (wan), VoiceStudio text to
  speech, voice cloning and transcription (voicestudio), saved ComfyUI workflows run by name (comfyflow), and
  Localbox to drop images or videos into ComfyUI input (localbox). Use when the user wants to generate an image
  or a video, animate a still, speak or narrate text, clone a voice, transcribe audio, run a ComfyUI workflow, or
  copy media into ComfyUI, or asks what HazelWolf tools are available.
---

# HazelWolf tools

The tools live in the hazelwolf.tools workspace, not in the current project. Reach them with the launcher next
to this file, which finds the workspace from any directory:

```bash
HW=~/.claude/skills/hazelwolf/hw
$HW list               # tools and what they do
$HW skill imagegen       # path of a tool's own SKILL.md
$HW test               # check every MCP server starts, lists its tools and reports healthy
```

## How to use a tool

1. Read the tool's own skill (`$HW skill <tool>`) for its MCP tools, prompt tips and first-use steps.
2. Prefer its MCP server. `hw install` registers each one at user scope under the tool's name (`imagegen`,
   `ltx`, `wan`, `voicestudio`, `comfyflow`, `localbox`), so its tools work in every project. `comfyflow` needs
   ComfyUI running (`<workspace>/creative/os/creative-workflows/run.sh`); `voicestudio` needs its backend
   (`$HW voicestudio backend`).
3. If MCP is not connected, use the HTTP fallback. The tool skills show commands like
   `uv run --directory image-gen/os/imagegen imagegen-api`. Those paths are relative to the workspace, so run them
   through the launcher instead:

   ```bash
   $HW imagegen api           # = uv run --directory <workspace>/image-gen/os/imagegen imagegen-api
   $HW imagegen prepare       # first-use model download
   $HW ltx prepare          # first-use download of the gated LTX pack (needs HF_TOKEN + accepted license)
   $HW wan prepare          # first-use download of Wan 2.2 (~18 GB)
   $HW voicestudio backend
   $HW comfyflow api
   $HW localbox api
   ```

   Start servers and long jobs in the background.

For images, the `imagegen` tool holds two models: Z-Image (default) for people, photos, scenes and styles, and Boogu
(`model: "boogu"`) for text-heavy images such as posters, menus, labels and book covers. Its skill has the routing
table.

Generated files go to the tool's `outputs/` folder inside the workspace (`$HW dir <tool>`). Copy results into the
current project when the user wants them there.

## Setup on a new machine

```bash
<workspace>/skills/hazelwolf/hw install
```

This links this skill into `~/.claude/skills/hazelwolf`, links each tool's own skill (`/imagegen`, `/ltx`, ...) into
`~/.claude/skills/<tool>`, and registers the MCP servers with `claude mcp add -s user`, launched with
`uv run --frozen` so startup stays well under Claude Code's 30 s MCP timeout. Re-run it after adding a tool, then
start a new session and run `$HW test`.
