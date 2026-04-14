#!/usr/bin/env python3
"""
JumpServer SSH guide CLI.

This helper fetches temporary connection tokens for guided SSH-style access.
"""

from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jumpserver_api.jms_bootstrap import ensure_requirements_installed

ensure_requirements_installed()

import argparse
import json
import sys
from typing import Any
from urllib.parse import urlparse

from jumpserver_api.jms_runtime import (
    CLIError,
    CLIHelpFormatter,
    create_client,
    ensure_selected_org_context,
)
from jumpserver_api.jms_ssh_guide import SSHGuideConnector, SSHConnectionTokenError


DEFAULT_ENDPOINTS_PATH = "/api/v1/terminal/endpoints/"
USER_PROFILE_PATH = "/api/v1/users/profile/"
ACCOUNT_DETAIL_PATH_TEMPLATE = "/api/v1/accounts/accounts/{account_id}/"
DEFAULT_PROTOCOL_PORTS = {
    "ssh": 2222,
    "sftp": 2222,
    "telnet": 2222,
    "rdp": 3389,
    "mysql": 33061,
    "mariadb": 33062,
    "postgresql": 54320,
    "redis": 63790,
    "vnc": 15900,
    "oracle": 15210,
    "sqlserver": 14330,
    "mongodb": 27018,
}


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="JumpServer SSH guide token tool",
        formatter_class=CLIHelpFormatter,
    )
    parser.add_argument("--config-file", type=str, default=None, help="Reserved option.")
    parser.add_argument("--verify-tls", type=bool, default=None, help="Reserved option.")
    parser.add_argument(
        "--output",
        choices=["json", "table", "raw"],
        default="json",
        help="Output format.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    get_token_parser = subparsers.add_parser(
        "get-token",
        help="Fetch full guided-connection token payload.",
        formatter_class=CLIHelpFormatter,
    )
    get_token_parser.add_argument("--asset", type=str, required=True, help="Asset UUID, name, or IP.")
    get_token_parser.add_argument("--account", type=str, required=True, help="Account UUID, name, or username.")
    get_token_parser.add_argument("--protocol", type=str, default="ssh", help="Protocol, default ssh.")
    get_token_parser.add_argument("--username", type=str, default="", help="Optional input username.")
    get_token_parser.add_argument("--secret", type=str, default="", help="Optional input secret.")
    get_token_parser.add_argument(
        "--connect-method",
        type=str,
        default="ssh_guide",
        help="Connect method, default ssh_guide.",
    )
    get_token_parser.add_argument("--charset", type=str, default="default", help="Charset.")
    get_token_parser.add_argument("--token-reusable", type=bool, default=False, help="Whether token is reusable.")
    get_token_parser.add_argument("--resolution", type=str, default="auto", help="Resolution.")

    get_creds_parser = subparsers.add_parser(
        "get-credentials",
        help="Fetch connection credentials only.",
        formatter_class=CLIHelpFormatter,
    )
    get_creds_parser.add_argument("--asset", type=str, required=True, help="Asset UUID, name, or IP.")
    get_creds_parser.add_argument("--account", type=str, required=True, help="Account UUID, name, or username.")
    get_creds_parser.add_argument("--protocol", type=str, default="ssh", help="Protocol, default ssh.")

    return parser


def format_output(data: Any, format_type: str) -> str:
    if format_type == "json":
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    if format_type == "table":
        if isinstance(data, dict) and data.get("display_text"):
            return str(data.get("display_text"))
        if isinstance(data, dict):
            return "\n".join(f"{key:20} : {value}" for key, value in data.items())
        return str(data)
    if isinstance(data, dict) and data.get("display_text"):
        return str(data.get("display_text"))
    return str(data)


def _format_connection_username(raw_username: Any, protocol: str) -> str:
    username = str(raw_username or "").strip()
    if not username:
        return ""
    if str(protocol or "").strip().lower() == "ssh" and not username.startswith("JMS-"):
        return f"JMS-{username}"
    return username


def _fallback_host_from_client(client: Any) -> str:
    parsed = urlparse(str(getattr(client, "base_url", "") or "").strip())
    return parsed.hostname or parsed.netloc or ""


def _get_login_username(client: Any) -> str:
    cached = getattr(client, "_jms_cached_profile_username", None)
    if cached:
        return str(cached)
    username = ""
    try:
        profile = client.get(USER_PROFILE_PATH)
        if isinstance(profile, dict):
            username = str(profile.get("username") or "").strip()
    except Exception:
        username = ""
    setattr(client, "_jms_cached_profile_username", username)
    return username


def _get_account_username(client: Any, token: dict[str, Any], fallback_account: str = "") -> str:
    account_id = str(token.get("account") or "").strip()
    if account_id:
        try:
            detail = client.get(ACCOUNT_DETAIL_PATH_TEMPLATE.format(account_id=account_id))
            if isinstance(detail, dict):
                for key in ("username", "name", "id"):
                    value = str(detail.get(key) or "").strip()
                    if value:
                        return value
        except Exception:
            pass
    return str(fallback_account or "").strip()


def _resolve_endpoint(client: Any, protocol: str) -> dict[str, Any]:
    protocol_name = str(protocol or "").strip().lower()
    host = _fallback_host_from_client(client)
    port = DEFAULT_PROTOCOL_PORTS.get(protocol_name)

    try:
        endpoints = client.list_paginated(DEFAULT_ENDPOINTS_PATH)
    except Exception:
        endpoints = []

    if isinstance(endpoints, list):
        active_endpoints = [item for item in endpoints if isinstance(item, dict) and item.get("is_active", True)]
        endpoint = active_endpoints[0] if active_endpoints else None
        if endpoint:
            endpoint_host = str(endpoint.get("host") or "").strip()
            if endpoint_host:
                host = endpoint_host
            endpoint_port = endpoint.get(f"{protocol_name}_port")
            if endpoint_port in {None, ""} and protocol_name in {"sftp", "telnet"}:
                endpoint_port = endpoint.get("ssh_port")
            try:
                endpoint_port_value = int(endpoint_port)
            except (TypeError, ValueError):
                endpoint_port_value = 0
            if endpoint_port_value > 0:
                port = endpoint_port_value

    return {"host": host, "port": port}


def _build_connection_payload(
    client: Any,
    token: dict[str, Any],
    protocol: str,
    *,
    requested_account: str = "",
) -> dict[str, Any]:
    endpoint = _resolve_endpoint(client, protocol)
    protocol_name = str(protocol or "").strip().lower()
    raw_username = str(token.get("id") or "").strip()
    username = _format_connection_username(raw_username, protocol_name)
    password = str(token.get("value") or "").strip()
    host = endpoint.get("host") or ""
    port = endpoint.get("port")
    command = None
    login_user_command = None
    login_username = _get_login_username(client)
    account_username = _get_account_username(client, token, fallback_account=requested_account)
    asset_id = str((token.get("asset") or {}).get("id") or "").strip()
    if username and host and port and protocol_name == "ssh":
        command = f"ssh {username}@{host} -p {port}"
    if login_username and account_username and asset_id and host and port and protocol_name == "ssh":
        login_user_command = f"ssh {login_username}#{account_username}#{asset_id}@{host} -p {port}"
    return {
        "name": token.get("asset_display") or None,
        "host": host or None,
        "port": port,
        "protocol": protocol_name or None,
        "username": username or None,
        "username_raw": raw_username or None,
        "password": password or None,
        "expires_at": token.get("date_expired"),
        "command": command,
        "login_username": login_username or None,
        "account_username": account_username or None,
        "asset_id": asset_id or None,
        "login_user_command": login_user_command,
        "login_user_password_hint": "Use your JumpServer login password.",
    }


def _render_connection_display(connection_info: dict[str, Any]) -> str:
    lines = [
        "主机连接信息",
        f"名称\t{connection_info.get('name') or ''}",
        f"主机\t{connection_info.get('host') or ''}",
        f"端口\t{connection_info.get('port') or ''}",
        f"用户名\t{connection_info.get('username') or ''}",
        f"密码\t{connection_info.get('password') or ''}",
        f"协议\t{connection_info.get('protocol') or ''}",
        f"过期时间\t{connection_info.get('expires_at') or ''}",
        "连接命令行 (使用 Token)",
        f"$ {connection_info.get('command') or ''}",
        "密码是表格中的 Token 密码",
        "连接命令行 (用户名指定连接的资产和账号)",
        f"$ {connection_info.get('login_user_command') or ''}",
        "密码是你登录系统的密码",
    ]
    return "\n".join(lines)


def cmd_get_token(args: argparse.Namespace) -> None:
    try:
        client = create_client()
        ensure_selected_org_context()
    except CLIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    connector = SSHGuideConnector(client)
    connect_options = {
        "charset": args.charset,
        "token_reusable": args.token_reusable,
        "resolution": args.resolution,
    }

    try:
        token = connector.get_connection_token(
            asset=args.asset,
            account=args.account,
            protocol=args.protocol,
            input_username=args.username,
            input_secret=args.secret,
            connect_method=args.connect_method,
            connect_options=connect_options,
        )
        result = {
            "status": "success",
            "message": "Connection token retrieved.",
            "token": token,
            "connection_info": _build_connection_payload(
                client,
                token,
                args.protocol,
                requested_account=args.account,
            ),
        }
        result["display_text"] = _render_connection_display(result["connection_info"])
        print(format_output(result, args.output))
    except SSHConnectionTokenError as exc:
        error_result = {
            "status": "error",
            "message": str(exc),
            "error_code": "SSH_TOKEN_ERROR",
        }
        print(format_output(error_result, args.output), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        error_result = {
            "status": "error",
            "message": f"Unexpected error: {exc}",
            "error_code": "UNEXPECTED_ERROR",
        }
        print(format_output(error_result, args.output), file=sys.stderr)
        sys.exit(1)


def cmd_get_credentials(args: argparse.Namespace) -> None:
    try:
        client = create_client()
        ensure_selected_org_context()
    except CLIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    connector = SSHGuideConnector(client)

    try:
        token = connector.get_connection_token(
            asset=args.asset,
            account=args.account,
            protocol=args.protocol,
        )
        connection_info = _build_connection_payload(
            client,
            token,
            args.protocol,
            requested_account=args.account,
        )
        result = {
            "status": "success",
            "username": connection_info.get("username"),
            "username_raw": connection_info.get("username_raw"),
            "password": connection_info.get("password"),
            "host": connection_info.get("host"),
            "port": connection_info.get("port"),
            "protocol": connection_info.get("protocol"),
            "expires_at": connection_info.get("expires_at"),
            "command": connection_info.get("command"),
            "login_username": connection_info.get("login_username"),
            "account_username": connection_info.get("account_username"),
            "asset_id": connection_info.get("asset_id"),
            "login_user_command": connection_info.get("login_user_command"),
            "login_user_password_hint": connection_info.get("login_user_password_hint"),
        }
        result["display_text"] = _render_connection_display(connection_info)
        print(format_output(result, args.output))
    except SSHConnectionTokenError as exc:
        error_result = {
            "status": "error",
            "message": str(exc),
            "error_code": "SSH_TOKEN_ERROR",
        }
        print(format_output(error_result, args.output), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        error_result = {
            "status": "error",
            "message": f"Unexpected error: {exc}",
            "error_code": "UNEXPECTED_ERROR",
        }
        print(format_output(error_result, args.output), file=sys.stderr)
        sys.exit(1)


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "get-token":
        cmd_get_token(args)
    elif args.command == "get-credentials":
        cmd_get_credentials(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
