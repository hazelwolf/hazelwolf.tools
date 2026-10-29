# Changelog

## 0.1.0

- Run ComfyUI API-format workflows by name; parameters come from node titles (`@name`) or raw `node_id.input`.
- Local file parameters are uploaded to ComfyUI; seeds are randomized unless supplied.
- Import a workflow from ComfyUI's run history, with automatic `@` titles for common nodes.
- CLI (`comfyflow`), HTTP API (`comfyflow-api`) and MCP server (`comfyflow-mcp`).
- First workflows: `z_image_turbo` and `video_ltx2_3_id_lora`, both tested against ComfyUI 0.38.0.
