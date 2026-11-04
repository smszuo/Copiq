"""copiq -- architecture.md section 8.2, 23. stdlib only (argparse, json,
http.client): startup time is this command's actual latency, so no
framework is worth the ~30-100ms it would add. See section 8.2 for the
measurements behind that call.
"""
from __future__ import annotations

import argparse
import sys

from copiq_cli.config import ConfigError, load_config
from copiq_cli.format import print_item, print_list
from copiq_cli.http import ApiError, request


def _client_id() -> str:
    import socket

    return socket.gethostname()


class NoItemsError(RuntimeError):
    pass


def _resolve_id(cfg, id_arg: int | None) -> int:
    """`id` is optional on every item-scoped command (get/delete/translate/
    explain/simplify/diagram): omit it and the command acts on the most
    recently captured clipboard item, matching the actual workflow --
    copy something, then immediately act on it, without a `list` round
    trip just to read off an id. One extra GET when omitted; the id
    itself is never cached client-side, since the daemon could add a new
    item between commands."""
    if id_arg is not None:
        return id_arg
    data = request(cfg["server"], cfg["apiKey"], "GET", "/api/clipboard", params={"limit": 1})
    items = data["items"]
    if not items:
        raise NoItemsError("no clipboard items yet")
    return items[0]["id"]


def cmd_list(args, cfg) -> int:
    data = request(
        cfg["server"], cfg["apiKey"], "GET", "/api/clipboard",
        params={"limit": args.limit, "search": args.search, "before": args.before},
    )
    print_list(data["items"])
    if data.get("hasMore"):
        print(f"\n... more available. Use --before {data['nextCursor']} to continue.")
    return 0


def cmd_get(args, cfg) -> int:
    item_id = _resolve_id(cfg, args.id)
    data = request(cfg["server"], cfg["apiKey"], "GET", f"/api/clipboard/{item_id}")
    print_item(data)
    return 0


def cmd_delete(args, cfg) -> int:
    item_id = _resolve_id(cfg, args.id)
    request(cfg["server"], cfg["apiKey"], "DELETE", f"/api/clipboard/{item_id}")
    print(f"deleted {item_id}")
    return 0


# AI actions run a subprocess server-side (section 17.1) and can occasionally
# run past the default HTTP timeout even when the server would have finished
# well within its own ai.timeout_seconds (120s default) -- give the client a
# longer budget for actions specifically, not for the fast read endpoints.
_ACTION_TIMEOUT_SECONDS = 150


def _run_action(action: str):
    def _cmd(args, cfg) -> int:
        item_id = _resolve_id(cfg, args.id)
        params = {}
        if getattr(args, "lang", None):
            params["targetLanguage"] = args.lang
        if getattr(args, "type", None):
            params["diagramType"] = args.type
        body = {"action": action, "parameters": params or None, "acknowledgeSecret": args.ack}
        data = request(
            cfg["server"], cfg["apiKey"], "POST", f"/api/clipboard/{item_id}/actions",
            json_body=body, timeout=_ACTION_TIMEOUT_SECONDS,
        )
        print(data["result"])
        return 0

    return _cmd


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="copiq", description="Copiq CLI")
    sub = p.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list recent clipboard items")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("--search", default=None)
    p_list.add_argument("--before", type=int, default=None)
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser("search", help="search clipboard history")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=50)
    p_search.add_argument("--before", type=int, default=None)
    p_search.set_defaults(func=lambda args, cfg: cmd_list(
        argparse.Namespace(limit=args.limit, search=args.query, before=args.before), cfg
    ))

    _ID_HELP = "clipboard item id; omit for the most recently captured item"

    p_get = sub.add_parser("get", help="get one clipboard item")
    p_get.add_argument("id", type=int, nargs="?", default=None, help=_ID_HELP)
    p_get.set_defaults(func=cmd_get)

    p_delete = sub.add_parser("delete", help="delete one clipboard item")
    p_delete.add_argument("id", type=int, nargs="?", default=None, help=_ID_HELP)
    p_delete.set_defaults(func=cmd_delete)

    for action in ("translate", "explain", "simplify"):
        p_action = sub.add_parser(action, help=f"{action} a clipboard item")
        p_action.add_argument("id", type=int, nargs="?", default=None, help=_ID_HELP)
        p_action.add_argument("--lang", default=None, help="target language, e.g. zh-CN")
        p_action.add_argument("--ack", action="store_true", help="acknowledge a flagged secret (section 29)")
        p_action.set_defaults(func=_run_action(action))

    p_diagram = sub.add_parser(
        "diagram", help="generate a Mermaid diagram from a clipboard item"
    )
    p_diagram.add_argument("id", type=int, nargs="?", default=None, help=_ID_HELP)
    p_diagram.add_argument(
        "--type", default=None, choices=["flowchart", "sequence", "class", "er"],
        help="Mermaid diagram type; omit to let the model choose",
    )
    p_diagram.add_argument("--ack", action="store_true", help="acknowledge a flagged secret (section 29)")
    p_diagram.set_defaults(func=_run_action("diagram"))

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        return args.func(args, cfg)
    except NoItemsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except ApiError as e:
        detail = e.body.get("detail") if isinstance(e.body, dict) else e.body
        print(f"error ({e.status}): {detail}", file=sys.stderr)
        return 1
    except ConnectionError as e:
        print(f"error: could not reach server at {cfg['server']}: {e}", file=sys.stderr)
        return 1
    except TimeoutError:
        # The request may well have completed server-side (AI actions run a
        # subprocess and can occasionally outlast even a generous client
        # timeout) -- the client just gave up waiting for the response.
        print(
            f"error: timed out waiting for {cfg['server']}. "
            "The action may have completed on the server; re-run the command "
            "to check (a completed action is served from cache, so re-running "
            "is cheap).",
            file=sys.stderr,
        )
        return 1


def run() -> None:
    sys.exit(main())


if __name__ == "__main__":
    run()
