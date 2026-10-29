"""Command line: comfyflow list | describe | run | job | cancel | import | health."""

from __future__ import annotations

import argparse
import json
import sys

from . import core
from .errors import FlowError


def _kv(items: list[str]) -> dict:
    params = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep:
            raise FlowError(f"expected key=value, got '{item}'")
        params[key] = value
    return params


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="comfyflow", description="Run ComfyUI workflows by name")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("health")
    sub.add_parser("list")
    sub.add_parser("describe").add_argument("name")
    run = sub.add_parser("run")
    run.add_argument("name")
    run.add_argument("params", nargs="*", help="key=value (exposed name or node_id.input)")
    run.add_argument("--no-wait", action="store_true")
    run.add_argument("--timeout", type=float)
    run.add_argument("--keep-seed", action="store_true", help="do not randomize seeds that were not supplied")
    sub.add_parser("job").add_argument("prompt_id")
    sub.add_parser("cancel").add_argument("prompt_id")
    imp = sub.add_parser("import", help="save the latest ComfyUI run as a workflow")
    imp.add_argument("name")
    imp.add_argument("--prompt-id")
    imp.add_argument("--description", default="")
    imp.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.cmd == "health":
            result = core.health()
        elif args.cmd == "list":
            result = core.list_workflows()
        elif args.cmd == "describe":
            result = core.describe_workflow(args.name)
        elif args.cmd == "run":
            result = core.run_workflow(args.name, _kv(args.params), not args.no_wait, args.timeout, not args.keep_seed)
        elif args.cmd == "job":
            result = core.get_job(args.prompt_id)
        elif args.cmd == "cancel":
            result = core.cancel_job(args.prompt_id)
        else:
            result = core.import_workflow(args.name, args.prompt_id, args.description, args.overwrite)
    except FlowError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
