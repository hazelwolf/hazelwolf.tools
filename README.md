# AI agent tools

Tools for AI agents (Claude Code, Cursor, OpenCode, Pi). Each tool exposes an HTTP API (Postman-ready), an MCP
server and a user-invocable skill. Layout, conventions and setup rules are in [INSTRUCTIONS.md](INSTRUCTIONS.md).

```
audio-gen/{os,custom,third-party}   video-gen/{os,custom,third-party}
image-gen/{os,custom,third-party}   creative/{os,custom,third-party}
```

## Clone

```bash
git clone --recurse-submodules <repo-url>
```

## Use from any project

```bash
skills/hazelwolf/hw install
```

Links the `hazelwolf` skill into `~/.claude/skills` and registers every tool's MCP server at Claude Code user scope.
`skills/hazelwolf/hw list` shows the tools; `hw <tool> api` starts a tool's HTTP API from any directory.

## Thanks

These tools stand on the work of the open-source community. Heartfelt thanks to every maintainer and contributor.
See [docs/ACKNOWLEDGEMENTS.md](docs/ACKNOWLEDGEMENTS.md) for the full acknowledgements.

## Legal

- Licensed under [Apache 2.0](LICENSE) (see [NOTICE](NOTICE)).
- Provided **as is**, without warranty: see [docs/legal/DISCLAIMER.md](docs/legal/DISCLAIMER.md).
- Third-party code and **model weights keep their own licenses** (some are non-commercial only):
  see [docs/legal/LICENSE-NOTES.md](docs/legal/LICENSE-NOTES.md).
- Services are for local use only: see [docs/legal/SECURITY.md](docs/legal/SECURITY.md).
