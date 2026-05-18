#!/usr/bin/env python3
"""
SSH Guide Connection Handler - 堡垒机 SSH 向导连接模块

该模块用于处理通过 SSH 向导方式连接堡垒机的请求。
SSH 向导连接是一种简化的连接方式，通过向导获取临时连接令牌。

实现的 OpenAPI 端点：
  /api/v1/authentication/connection-token/

返回的令牌包含以下关键字段：
  - 'id': 用作连接的用户名
  - 'value': 用作连接的密码（临时令牌）
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, Optional

from jms_api_client import JumpServerClient
from jms_discovery import JumpServerDiscovery
from jms_runtime import create_discovery, is_uuid_like
from jms_types import JumpServerAPIError, JumpServerConfig

if TYPE_CHECKING:
    pass


class SSHConnectionTokenError(JumpServerAPIError):
    """SSH 连接令牌错误"""

    pass


class SSHGuideConnector:
    """
    堡垒机 SSH 向导连接器

    该类处理向向导连接 API 端点提交请求，并返回连接所需的令牌信息。
    
    典型的连接流程：
    1. 获取资产、账号、协议信息
    2. 调用 get_connection_token() 获取令牌
    3. 使用返回的 id 和 value 作为连接凭证
    
    Attributes:
        client (JumpServerClient): JumpServer API 客户端
        discovery (JumpServerDiscovery): JumpServer 发现引擎，用于解析资产和账号
    """

    CONNECTION_TOKEN_PATH = "/api/v1/authentication/connection-token/"

    def __init__(self, client: JumpServerClient, discovery: Optional[JumpServerDiscovery] = None):
        """
        初始化 SSH 向导连接器

        Args:
            client: JumpServer API 客户端实例
            discovery: JumpServer 发现引擎（可选，默认自动创建）
        """
        self.client = client
        self.discovery = discovery or create_discovery()

    def resolve_asset_id(self, asset_identifier: str) -> str:
        """
        通过资产名称或地址解析资产 UUID

        支持以下输入格式：
        - UUID: "2fcc289b-f985-4e51-bde9-65d63bf47cca"
        - 资产名称: "server-prod-01"
        - 资产地址: "192.168.1.100"
        - 混合格式: "server-prod-01(192.168.1.100)"

        Args:
            asset_identifier (str): 资产标识（UUID、名称或地址）

        Returns:
            str: 资产 UUID

        Raises:
            SSHConnectionTokenError: 当无法解析或找到多个匹配时抛出
        """
        asset_identifier = str(asset_identifier or "").strip()
        
        # 如果是 UUID 格式，直接返回
        if is_uuid_like(asset_identifier):
            assets = self.discovery.list_assets()
            for item in assets:
                if str(item.get("id")) == asset_identifier:
                    return asset_identifier
            raise SSHConnectionTokenError(
                f"Asset UUID not found: {asset_identifier}",
                details=f"指定的资产 UUID '{asset_identifier}' 在当前组织中不存在"
            )
        
        # 尝试通过名称或地址查询
        try:
            assets = self.discovery.list_assets()
            matches = []
            
            for asset in assets:
                asset_name = str(asset.get("name") or "").lower()
                asset_addr = str(asset.get("address") or "").lower()
                search_val = asset_identifier.lower()
                
                if search_val == asset_name or search_val == asset_addr:
                    matches.append(asset)
                elif search_val in asset_name or search_val in asset_addr:
                    matches.append(asset)
            
            if not matches:
                raise SSHConnectionTokenError(
                    f"No matching asset found: {asset_identifier}",
                    details=f"无法找到名称或地址包含'{asset_identifier}'的资产。请检查资产名称或使用精确的 UUID。"
                )
            
            if len(matches) > 1:
                suggestions = [f"- {a.get('name')}({a.get('address')})" for a in matches[:5]]
                raise SSHConnectionTokenError(
                    f"Ambiguous asset identifier: {asset_identifier}",
                    details=f"找到多个匹配的资产，请使用更精确的名称或 UUID:\n" + "\n".join(suggestions)
                )
            
            return matches[0]["id"]
        
        except SSHConnectionTokenError:
            raise
        except Exception as exc:
            raise SSHConnectionTokenError(
                f"Failed to resolve asset identifier: {str(exc)}",
                details=str(exc)
            ) from exc

    def resolve_account_id(self, account_identifier: str, asset_id: Optional[str] = None) -> str:
        """
        通过账号名称、用户名或 UUID 解析账号 UUID

        支持以下输入格式：
        - UUID: "fb13bca0-6136-4d83-9bc0-6de7087d99fd"
        - 账号名称: "root_account"
        - 用户名: "root"
        - 混合格式: "root_account(root)"

        Args:
            account_identifier (str): 账号标识（UUID、名称或用户名）
            asset_id (str, optional): 资产 UUID，如果提供则限制在该资产下查询

        Returns:
            str: 账号 UUID

        Raises:
            SSHConnectionTokenError: 当无法解析或找到多个匹配时抛出
        """
        account_identifier = str(account_identifier or "").strip()
        
        # 如果是 UUID 格式，直接返回
        if is_uuid_like(account_identifier):
            accounts = self.discovery.list_accounts()
            for item in accounts:
                if str(item.get("id")) == account_identifier:
                    # 如果提供了 asset_id，验证账号是否属于该资产
                    if asset_id:
                        item_asset_id = str(item.get("asset", {}).get("id") or "")
                        if item_asset_id != asset_id:
                            raise SSHConnectionTokenError(
                                f"Account UUID does not belong to the specified asset: {account_identifier}",
                                details=f"账号 UUID '{account_identifier}' 不属于指定的资产"
                            )
                    return account_identifier
            
            raise SSHConnectionTokenError(
                f"Account UUID not found: {account_identifier}",
                details=f"指定的账号 UUID '{account_identifier}' 在当前组织中不存在"
            )
        
        # 尝试通过名称或用户名查询
        try:
            accounts = self.discovery.list_accounts()
            matches = []
            
            for account in accounts:
                # 如果指定了 asset_id，先过滤
                if asset_id:
                    account_asset_id = str(account.get("asset", {}).get("id") or "")
                    if account_asset_id != asset_id:
                        continue
                
                account_name = str(account.get("name") or "").lower()
                username = str(account.get("username") or "").lower()
                search_val = account_identifier.lower()
                
                if search_val == account_name or search_val == username:
                    matches.append(account)
                elif search_val in account_name or search_val in username:
                    matches.append(account)
            
            if not matches:
                location = f"指定的资产下" if asset_id else "当前组织中"
                raise SSHConnectionTokenError(
                    f"No matching account found: {account_identifier}",
                    details=f"无法在{location}找到名称或用户名包含'{account_identifier}'的账号。"
                )
            
            if len(matches) > 1:
                suggestions = [f"- {a.get('name')}({a.get('username')})" for a in matches[:5]]
                raise SSHConnectionTokenError(
                    f"Ambiguous account identifier: {account_identifier}",
                    details=f"找到多个匹配的账号，请使用更精确的名称或 UUID:\n" + "\n".join(suggestions)
                )
            
            return matches[0]["id"]
        
        except SSHConnectionTokenError:
            raise
        except Exception as exc:
            raise SSHConnectionTokenError(
                f"Failed to resolve account identifier: {str(exc)}",
                details=str(exc)
            ) from exc

    def get_connection_token(
        self,
        asset: str,
        account: str,
        protocol: str = "ssh",
        input_username: str = "",
        input_secret: str = "",
        connect_method: str = "ssh_guide",
        connect_options: Optional[Dict[str, Any]] = None,
        auto_resolve: bool = True,
    ) -> Dict[str, Any]:
        """
        获取向导连接令牌

        该方法向 JumpServer 的连接令牌端点提交请求，获取用于连接的临时令牌。
        返回的令牌包含 'id'（用户名）和 'value'（密码/令牌）两个关键字段。

        Args:
            asset (str): 资产标识，可以是：
                - UUID: "2fcc289b-f985-4e51-bde9-65d63bf47cca"
                - 资产名称: "server-prod-01"
                - 资产地址: "192.168.1.100"
            account (str): 账号标识，可以是：
                - UUID: "fb13bca0-6136-4d83-9bc0-6de7087d99fd"
                - 账号名称: "root_account"
                - 用户名: "root"
            protocol (str): 协议类型，默认为 "ssh"。
                           支持的协议：ssh, rdp, telnet, vnc, mysql, mariadb, mongodb, postgresql
            input_username (str): 输入的用户名（可选），如果不提供则使用账号的默认用户名
            input_secret (str): 输入的密码/密钥（可选），如果不提供则使用账号的默认密码
            connect_method (str): 连接方法，默认为 "ssh_guide"。其他值包括：
                                 "ssh", "rdp", "vnc", "db", "web_cli", "web_sftp"
            connect_options (Dict[str, Any]): 连接选项字典。常用选项包括：
                - charset: 字符集，默认 "default"
                - disableautohash: 禁用自动 hash，默认 False
                - token_reusable: 令牌是否可重用，默认 False
                - resolution: 分辨率设置，默认 "auto"
                - backspaceAsCtrlH: Backspace 键是否作为 Ctrl+H 发送，默认 False
                - appletConnectMethod: Applet 连接方法，默认 "web"
                - virtualappConnectMethod: 虚拟应用连接方法，默认 "web"
                - reusable: 是否可重用，默认 False
                - rdp_connection_speed: RDP 连接速度，默认 "auto"

        Returns:
            Dict[str, Any]: 连接令牌响应，包含以下关键字段：
                - 'id': 连接用户名
                - 'value': 连接密码/令牌
                - 其他字段由服务器返回

        Raises:
            SSHConnectionTokenError: 当获取令牌失败时抛出，包含详细的错误信息

        Example:
            >>> connector = SSHGuideConnector(client)
            >>> token = connector.get_connection_token(
            ...     asset="2fcc289b-f985-4e51-bde9-65d63bf47cca",
            ...     account="fb13bca0-6136-4d83-9bc0-6de7087d99fd",
            ...     protocol="ssh"
            ... )
            >>> print(f"Username: {token['id']}")
            >>> print(f"Password: {token['value']}")
        """
        # 自动解析资产和账号（如果需要）
        resolved_asset = asset
        resolved_account = account
        
        if auto_resolve:
            resolved_asset = self.resolve_asset_id(asset)
            resolved_account = self.resolve_account_id(account, asset_id=resolved_asset)
        
        # 初始化连接选项
        if connect_options is None:
            connect_options = {}

        # 设置默认连接选项
        default_options = {
            "charset": "default",
            "disableautohash": False,
            "token_reusable": False,
            "resolution": "auto",
            "backspaceAsCtrlH": False,
            "appletConnectMethod": "web",
            "virtualappConnectMethod": "web",
            "reusable": False,
            "rdp_connection_speed": "auto",
        }
        
        # 合并用户提供的选项（用户选项优先）
        default_options.update(connect_options)

        # 构建请求负载
        payload = {
            "asset": resolved_asset,
            "account": resolved_account,
            "protocol": protocol,
            "input_username": input_username,
            "input_secret": input_secret,
            "connect_method": connect_method,
            "connect_options": default_options,
        }

        try:
            # 发送 POST 请求到连接令牌端点
            response = self.client.post(
                self.CONNECTION_TOKEN_PATH,
                json_body=payload,
            )

            # 验证响应
            if not isinstance(response, dict):
                raise SSHConnectionTokenError(
                    f"Invalid connection token response: expected dict, got {type(response).__name__}",
                    details=response,
                )

            # 检查是否包含必要字段
            if "id" not in response or "value" not in response:
                raise SSHConnectionTokenError(
                    "Connection token response missing required fields: 'id' or 'value'",
                    details=response,
                )

            return response

        except SSHConnectionTokenError:
            raise
        except Exception as exc:
            raise SSHConnectionTokenError(
                f"Failed to get connection token: {str(exc)}",
                details=str(exc),
            ) from exc

    def get_connection_credentials(
        self,
        asset: str,
        account: str,
        protocol: str = "ssh",
        input_username: str = "",
        input_secret: str = "",
        auto_resolve: bool = True,
        **kwargs,
    ) -> tuple[str, str]:
        """
        便利方法：获取连接凭证（用户名和密码）

        该方法是 get_connection_token() 的包装，直接返回连接所需的凭证对。

        Args:
            asset (str): 资产标识（UUID、名称或地址）
            account (str): 账号标识（UUID、名称或用户名）
            protocol (str): 协议类型，默认为 "ssh"
            input_username (str): 输入的用户名
            input_secret (str): 输入的密码/密钥
            auto_resolve (bool): 是否自动解析资产和账号（默认 True）
            **kwargs: 其他传递给 get_connection_token() 的参数

        Returns:
            tuple[str, str]: (用户名, 密码) 元组

        Example:
            >>> username, password = connector.get_connection_credentials(
            ...     asset="server-prod-01",
            ...     account="root"
            ... )
            >>> print(f"ssh {username}@host -p {password}")
        """
        token = self.get_connection_token(
            asset=asset,
            account=account,
            protocol=protocol,
            input_username=input_username,
            input_secret=input_secret,
            auto_resolve=auto_resolve,
            **kwargs,
        )
        return token["id"], token["value"]


def create_ssh_guide_connector(config: JumpServerConfig) -> SSHGuideConnector:
    """
    工厂函数：创建 SSH 向导连接器

    Args:
        config (JumpServerConfig): JumpServer 配置对象

    Returns:
        SSHGuideConnector: SSH 向导连接器实例

    Example:
        >>> config = JumpServerConfig(base_url="http://localhost:8080", ...)
        >>> connector = create_ssh_guide_connector(config)
    """
    client = JumpServerClient(config, timeout=30)
    return SSHGuideConnector(client)


if __name__ == "__main__":
    import sys

    print(
        "This module is designed to be imported and used as part of the JumpServer skills.",
        file=sys.stderr,
    )
    print(
        "Use: from jms_ssh_guide import SSHGuideConnector",
        file=sys.stderr,
    )
    sys.exit(1)
