#!/usr/bin/env python3
"""
JumpServer Interactive Session CLI.

Provides commands for connecting to JumpServer assets via guided connection
tokens, executing commands/SQL in interactive sessions, and managing sessions.

Usage:
  # Connect to an asset
  python3 jms_interactive_cli.py connect --asset 10.1.12.62 --account root --protocol ssh

  # Execute a command in a session
  python3 jms_interactive_cli.py exec --session <session_id> --command "hostname && whoami"

  # Execute SQL in a database session
  python3 jms_interactive_cli.py exec --session <session_id> --command "SHOW DATABASES;"

  # List active sessions
  python3 jms_interactive_cli.py list-sessions

  # Disconnect a session
  python3 jms_interactive_cli.py disconnect --session <session_id>
"""
from __future__ import annotations

import argparse
import json
import sys
from importlib import import_module
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
JUMPSERVER_API_ROOT = REPO_ROOT / "jumpserver-api"


def _ensure_path() -> None:
    # If called from a sub-skill entrypoint, jumpserver-api is already in sys.path
    for p in sys.path:
        if p.endswith("jumpserver-api") and Path(p).exists():
            return
    # Direct execution: add our own directory
    own_dir = str(Path(__file__).resolve().parent)
    if own_dir not in sys.path:
        sys.path.insert(0, own_dir)


def create_parser() -> argparse.ArgumentParser:
    from jms_runtime import CLIHelpFormatter

    parser = argparse.ArgumentParser(
        description="JumpServer interactive session manager",
        formatter_class=CLIHelpFormatter,
    )
    parser.add_argument("--config-file", type=str, default=None, help="Reserved option.")
    parser.add_argument("--verify-tls", type=bool, default=None, help="Reserved option.")
    parser.add_argument(
        "--output",
        choices=["json", "table"],
        default="json",
        help="Output format.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # connect
    connect_parser = subparsers.add_parser(
        "connect",
        help="Connect to an asset via guided connection token and establish an interactive session.",
        formatter_class=CLIHelpFormatter,
    )
    connect_parser.add_argument("--asset", type=str, required=True, help="Asset UUID, name, or IP.")
    connect_parser.add_argument("--account", type=str, required=True, help="Account UUID, name, or username.")
    connect_parser.add_argument("--protocol", type=str, default="ssh", help="Protocol (ssh, mysql, postgresql, etc.). Default: ssh.")
    connect_parser.add_argument("--timeout", type=int, default=30, help="Connection timeout in seconds. Default: 30.")

    # exec
    exec_parser = subparsers.add_parser(
        "exec",
        help="Execute a command or SQL in an active session.",
        formatter_class=CLIHelpFormatter,
    )
    exec_parser.add_argument("--session", type=str, required=True, help="Session ID.")
    exec_parser.add_argument("--command", type=str, required=True, dest="cmd", help="Command or SQL to execute.")
    exec_parser.add_argument("--timeout", type=int, default=30, help="Execution timeout in seconds. Default: 30.")

    # list-sessions
    subparsers.add_parser(
        "list-sessions",
        help="List all active interactive sessions.",
        formatter_class=CLIHelpFormatter,
    )

    # session-status
    status_parser = subparsers.add_parser(
        "session-status",
        help="Get the status of a specific session.",
        formatter_class=CLIHelpFormatter,
    )
    status_parser.add_argument("--session", type=str, required=True, help="Session ID.")

    # disconnect
    disconnect_parser = subparsers.add_parser(
        "disconnect",
        help="Disconnect an active session.",
        formatter_class=CLIHelpFormatter,
    )
    disconnect_parser.add_argument("--session", type=str, required=True, help="Session ID.")

    return parser


def format_output(data: dict, format_type: str) -> str:
    if format_type == "json":
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    if format_type == "table":
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, default=str)
                lines.append(f"{key:20} : {value}")
            return "\n".join(lines)
        return str(data)
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def cmd_connect(args: argparse.Namespace) -> None:
    from jms_runtime import CLIError, ensure_selected_org_context
    from jms_interactive_session import InteractiveSessionManager, InteractiveSessionError

    try:
        ensure_selected_org_context()
    except CLIError as exc:
        print(format_output({"status": "error", "message": str(exc)}, args.output), file=sys.stderr)
        sys.exit(1)

    mgr = InteractiveSessionManager()

    try:
        result = mgr.connect(
            asset=args.asset,
            account=args.account,
            protocol=args.protocol,
            timeout=args.timeout,
        )
        print(format_output(result, args.output))
    except InteractiveSessionError as exc:
        print(format_output({
            "status": "error",
            "message": str(exc),
            "error_code": "CONNECT_ERROR",
        }, args.output), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(format_output({
            "status": "error",
            "message": f"Unexpected error: {exc}",
            "error_code": "UNEXPECTED_ERROR",
        }, args.output), file=sys.stderr)
        sys.exit(1)


def cmd_exec(args: argparse.Namespace) -> None:
    from jms_interactive_session import InteractiveSessionManager, InteractiveSessionError

    mgr = InteractiveSessionManager()

    try:
        result = mgr.execute(
            session_id=args.session,
            command=args.cmd,
            timeout=args.timeout,
        )
        print(format_output(result, args.output))
    except InteractiveSessionError as exc:
        print(format_output({
            "status": "error",
            "message": str(exc),
            "error_code": "EXEC_ERROR",
        }, args.output), file=sys.stderr)
        sys.exit(1)


def cmd_list_sessions(args: argparse.Namespace) -> None:
    from jms_interactive_session import InteractiveSessionManager

    mgr = InteractiveSessionManager()
    sessions = mgr.list_sessions()
    print(format_output({
        "status": "success",
        "session_count": len(sessions),
        "sessions": sessions,
    }, args.output))


def cmd_session_status(args: argparse.Namespace) -> None:
    from jms_interactive_session import InteractiveSessionManager

    mgr = InteractiveSessionManager()
    result = mgr.session_status(args.session)
    print(format_output(result, args.output))


def cmd_disconnect(args: argparse.Namespace) -> None:
    from jms_interactive_session import InteractiveSessionManager

    mgr = InteractiveSessionManager()
    result = mgr.disconnect(args.session)
    print(format_output(result, args.output))


def main() -> int:
    _ensure_path()
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "connect":
        cmd_connect(args)
    elif args.command == "exec":
        cmd_exec(args)
    elif args.command == "list-sessions":
        cmd_list_sessions(args)
    elif args.command == "session-status":
        cmd_session_status(args)
    elif args.command == "disconnect":
        cmd_disconnect(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
