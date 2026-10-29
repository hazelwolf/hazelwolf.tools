---
name: hazelwolf
description: >-
  Local HazelWolf AI tools, usable from any project: Z-Image text-to-image and img2img (zimage), LTX-2.5
  text/image-to-video with audio (ltx), Wan 2.2 Apache-licensed text/image-to-video (wan), VoiceStudio text to
  speech, voice cloning and transcription (voicestudio), and Localbox to drop images or videos into ComfyUI input
  (localbox). Use when the user wants to generate an image
  or a video, animate a still, speak or narrate text, clone a voice, transcribe audio, or copy media into ComfyUI,
  or asks what HazelWolf tools are available.
---

# HazelWolf tools

The tools live in the hazelwolf.tools workspace, not in the current project. Reach them with the launcher next
to this file, which finds the workspace from any directory:

```bash
HW=~/.claude/skills/hazelwolf/hw
$HW list               # tools and what they do
$HW skill zimage       # path of a tool's own SKILL.md
```

## How to use a tool

1. Read the tool's own skill (`$HW skill <tool>`) for its MCP tools, prompt tips and first-use steps.
2. Prefer its MCP server. `hw install` registers each one at user scope under the tool's name (`zimage`,
   `ltx`, `wan`, `voicestudio`, `localbox`), so its tools work in every project.
3. If MCP is not connected, use the HTTP fallback. The tool skills show commands like
   `uv run --directory image-gen/os/zimage zimage-api`. Those paths are relative to the workspace, so run them
   through the launcher instead:

   ```bash
   $HW zimage api           # = uv run --directory <workspace>/image-gen/os/zimage zimage-api
   $HW zimage prepare       # first-use model download
   $HW ltx prepare          # first-use download of the gated LTX pack (needs HF_TOKEN + accepted license)
   $HW wan prepare          # first-use download of Wan 2.2 (~18 GB)
   $HW voicestudio backend
   $HW localbox api
   ```

   Start servers and long jobs in the background.

Generated files go to the tool's `outputs/` folder inside the workspace (`$HW dir <tool>`). Copy results into the
current project when the user wants them there.

## Setup on a new machine

```bash
<workspace>/skills/hazelwolf/hw install
```

This links this skill into `~/.claude/skills/hazelwolf` and registers the MCP servers with `claude mcp add -s user`.
Restart Claude (or start a new session) to pick them up.
