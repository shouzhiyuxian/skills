#!/usr/bin/env python3
"""
JumpServer Interactive Session Manager - 交互式会话管理模块

该模块实现通过 JumpServer 向导连接令牌建立实际的 SSH/DB 会话，
并支持在会话中执行命令、查询结果和保持登录态。

由于 CLI 每次调用是独立进程，会话凭证通过文件持久化到
.sessions/ 目录下。exec 命令读取凭证后重新建立连接执行操作。

支持的协议：
  - SSH: 通过 paramiko 建立 SSH 通道，执行命令
  - MySQL/MariaDB/PostgreSQL/MongoDB: 通过数据库驱动建立连接，执行 SQL

核心流程：
  1. connect: 获取向导连接令牌 → 建立实际连接 → 保存凭证到文件
  2. exec: 读取凭证 → 重新建立连接 → 执行命令/SQL → 断开连接
  3. disconnect: 删除凭证文件

使用示例：
  >>> from jms_interactive_session import InteractiveSessionManager
  >>> mgr = InteractiveSessionManager()
  >>> result = mgr.connect(asset="10.1.12.62", account="root", protocol="ssh")
  >>> session_id = result["session_id"]
  >>> result = mgr.execute(session_id, "hostname && whoami")
  >>> print(result["stdout"])
  >>> mgr.disconnect(session_id)
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from jms_api_client import JumpServerClient
from jms_runtime import create_client, create_discovery
from jms_ssh_guide import SSHGuideConnector, SSHConnectionTokenError
from jms_types import JumpServerAPIError

logger = logging.getLogger(__name__)

# 默认会话存储目录（相对于仓库根目录）
SESSIONS_DIR_NAME = ".sessions"


# ---------------------------------------------------------------------------
# Protocol helpers
# ---------------------------------------------------------------------------

class ProtocolType(str, Enum):
    SSH = "ssh"
    RDP = "rdp"
    VNC = "vnc"
    MYSQL = "mysql"
    MARIADB = "mariadb"
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"
    REDIS = "redis"

    @classmethod
    def is_db(cls, protocol: str) -> bool:
        return protocol.lower() in ("mysql", "mariadb", "postgresql", "mongodb", "redis")

    @classmethod
    def is_ssh(cls, protocol: str) -> bool:
        return protocol.lower() in ("ssh", "sftp", "telnet")


# ---------------------------------------------------------------------------
# Session data model
# ---------------------------------------------------------------------------

@dataclass
class SessionInfo:
    """单个活跃会话的信息（可序列化到文件）"""
    session_id: str
    protocol: str
    host: str
    port: int
    username: str
    token_password: str
    asset_name: str
    account_username: str
    expires_at: str
    connected_at: str = ""
    last_activity_at: str = ""
    status: str = "connected"  # connected | disconnected | expired | error
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "protocol": self.protocol,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "token_password": self.token_password,
            "asset_name": self.asset_name,
            "account_username": self.account_username,
            "expires_at": self.expires_at,
            "connected_at": self.connected_at,
            "last_activity_at": self.last_activity_at,
            "status": self.status,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionInfo":
        return cls(
            session_id=data.get("session_id", ""),
            protocol=data.get("protocol", ""),
            host=data.get("host", ""),
            port=data.get("port", 0),
            username=data.get("username", ""),
            token_password=data.get("token_password", ""),
            asset_name=data.get("asset_name", ""),
            account_username=data.get("account_username", ""),
            expires_at=data.get("expires_at", ""),
            connected_at=data.get("connected_at", ""),
            last_activity_at=data.get("last_activity_at", ""),
            status=data.get("status", "connected"),
            error_message=data.get("error_message", ""),
        )

    def to_public_dict(self) -> Dict[str, Any]:
        """不暴露密码的公开信息"""
        d = self.to_dict()
        d.pop("token_password", None)
        return d


# ---------------------------------------------------------------------------
# Session Registry (file-based persistence)
# ---------------------------------------------------------------------------

class SessionRegistry:
    """基于文件的会话注册表，支持跨进程会话持久化"""

    def __init__(self, base_dir: Optional[str] = None) -> None:
        if base_dir is None:
            # 使用仓库根目录下的 .sessions/
            base_dir = str(Path(__file__).resolve().parent.parent / SESSIONS_DIR_NAME)
        self._base_dir = base_dir
        os.makedirs(self._base_dir, exist_ok=True)

    def _session_file(self, session_id: str) -> Path:
        return Path(self._base_dir) / f"{session_id}.json"

    def register(self, session: SessionInfo) -> None:
        """保存会话信息到文件"""
        path = self._session_file(session.session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

    def get(self, session_id: str) -> Optional[SessionInfo]:
        """从文件读取会话信息"""
        path = self._session_file(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SessionInfo.from_dict(data)
        except Exception:
            return None

    def update(self, session_id: str, **kwargs: Any) -> Optional[SessionInfo]:
        """更新会话信息"""
        session = self.get(session_id)
        if not session:
            return None
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        self.register(session)
        return session

    def remove(self, session_id: str) -> Optional[SessionInfo]:
        """删除会话文件"""
        session = self.get(session_id)
        path = self._session_file(session_id)
        if path.exists():
            path.unlink()
        return session

    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有保存的会话"""
        result = []
        base = Path(self._base_dir)
        for path in base.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session = SessionInfo.from_dict(data)
                result.append(session.to_public_dict())
            except Exception:
                continue
        return result

    def get_active(self) -> List[SessionInfo]:
        """获取所有活跃会话"""
        result = []
        base = Path(self._base_dir)
        for path in base.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session = SessionInfo.from_dict(data)
                if session.status == "connected":
                    result.append(session)
            except Exception:
                continue
        return result


# Global singleton
_global_registry = SessionRegistry()


def get_session_registry() -> SessionRegistry:
    return _global_registry


# ---------------------------------------------------------------------------
# SSH Session Handler
# ---------------------------------------------------------------------------

class SSHSessionHandler:
    """通过 paramiko 建立 SSH 交互式会话"""

    def __init__(self, host: str, port: int, username: str, password: str, timeout: int = 30) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self._client: Any = None

    def connect(self) -> Any:
        """建立 SSH 连接，返回 paramiko.SSHClient"""
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=self.timeout,
            look_for_keys=False,
            allow_agent=False,
            banner_timeout=self.timeout,
            auth_timeout=self.timeout,
        )
        self._client = client
        return client

    def execute(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """执行 SSH 命令并返回结果"""
        if not self._client:
            raise InteractiveSessionError("SSH session not connected")

        stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        stdout_text = stdout.read().decode("utf-8", errors="replace")
        stderr_text = stderr.read().decode("utf-8", errors="replace")

        return {
            "stdout": stdout_text,
            "stderr": stderr_text,
            "exit_code": exit_code,
            "command": command,
        }

    def close(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None


# ---------------------------------------------------------------------------
# Database Session Handler
# ---------------------------------------------------------------------------

class DBSessionHandler:
    """通过数据库驱动建立 DB 交互式会话"""

    def __init__(self, host: str, port: int, username: str, password: str,
                 protocol: str, timeout: int = 30) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.protocol = protocol.lower()
        self.timeout = timeout
        self._connection: Any = None

    def connect(self) -> Any:
        """建立数据库连接"""
        if self.protocol in ("mysql", "mariadb"):
            return self._connect_mysql()
        elif self.protocol == "postgresql":
            return self._connect_postgresql()
        elif self.protocol == "mongodb":
            return self._connect_mongodb()
        else:
            raise InteractiveSessionError(
                f"Unsupported database protocol: {self.protocol}",
                details=f"当前支持的数据库协议：mysql, mariadb, postgresql, mongodb"
            )

    def _connect_mysql(self) -> Any:
        try:
            import pymysql
        except ImportError:
            try:
                import mysql.connector as pymysql
            except ImportError:
                raise InteractiveSessionError(
                    "Missing MySQL driver",
                    details="请安装 pymysql 或 mysql-connector-python: pip install pymysql"
                )

        conn = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            connect_timeout=self.timeout,
            read_timeout=self.timeout,
            write_timeout=self.timeout,
            charset="utf8mb4",
        )
        self._connection = conn
        return conn

    def _connect_postgresql(self) -> Any:
        try:
            import psycopg2
        except ImportError:
            raise InteractiveSessionError(
                "Missing PostgreSQL driver",
                details="请安装 psycopg2: pip install psycopg2-binary"
            )

        conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            connect_timeout=self.timeout,
        )
        self._connection = conn
        return conn

    def _connect_mongodb(self) -> Any:
        try:
            import pymongo
        except ImportError:
            raise InteractiveSessionError(
                "Missing MongoDB driver",
                details="请安装 pymongo: pip install pymongo"
            )

        client = pymongo.MongoClient(
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            connectTimeoutMS=self.timeout * 1000,
            serverSelectionTimeoutMS=self.timeout * 1000,
        )
        client.admin.command("ping")
        self._connection = client
        return client

    def execute(self, sql: str, timeout: int = 30) -> Dict[str, Any]:
        """执行 SQL 语句并返回结果"""
        if not self._connection:
            raise InteractiveSessionError("Database session not connected")

        if self.protocol in ("mysql", "mariadb"):
            return self._execute_mysql(sql, timeout)
        elif self.protocol == "postgresql":
            return self._execute_postgresql(sql, timeout)
        elif self.protocol == "mongodb":
            return self._execute_mongodb(sql)
        else:
            raise InteractiveSessionError(f"Unsupported protocol for execution: {self.protocol}")

    def _execute_mysql(self, sql: str, timeout: int = 30) -> Dict[str, Any]:
        import pymysql
        cursor = self._connection.cursor()
        try:
            cursor.execute(sql)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                results = []
                for row in rows:
                    if isinstance(row, dict):
                        results.append(row)
                    else:
                        results.append(dict(zip(columns, row)))
                self._connection.commit()
                return {
                    "type": "query",
                    "columns": columns,
                    "rows": results,
                    "row_count": len(results),
                    "sql": sql,
                }
            else:
                self._connection.commit()
                return {
                    "type": "execute",
                    "affected_rows": cursor.rowcount,
                    "sql": sql,
                }
        except pymysql.Error as e:
            self._connection.rollback()
            raise InteractiveSessionError(f"MySQL execution error: {e}", details=str(e))
        finally:
            cursor.close()

    def _execute_postgresql(self, sql: str, timeout: int = 30) -> Dict[str, Any]:
        cursor = self._connection.cursor()
        try:
            cursor.execute(sql)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                results = [dict(zip(columns, row)) for row in rows]
                self._connection.commit()
                return {
                    "type": "query",
                    "columns": columns,
                    "rows": results,
                    "row_count": len(results),
                    "sql": sql,
                }
            else:
                self._connection.commit()
                return {
                    "type": "execute",
                    "affected_rows": cursor.rowcount,
                    "sql": sql,
                }
        except Exception as e:
            self._connection.rollback()
            raise InteractiveSessionError(f"PostgreSQL execution error: {e}", details=str(e))
        finally:
            cursor.close()

    def _execute_mongodb(self, sql: str, timeout: int = 30) -> Dict[str, Any]:
        try:
            cmd = json.loads(sql)
        except json.JSONDecodeError as e:
            raise InteractiveSessionError(
                f"Invalid MongoDB command (must be JSON): {e}",
                details='MongoDB 命令必须是有效的 JSON 格式，例如: {"find": "collection_name"}'
            )

        db = self._connection.get_database()
        result = db.command(cmd)
        return {
            "type": "mongodb_command",
            "result": result,
            "sql": sql,
        }

    def close(self) -> None:
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None


# ---------------------------------------------------------------------------
# Interactive Session Manager
# ---------------------------------------------------------------------------

class InteractiveSessionError(JumpServerAPIError):
    """交互式会话错误"""
    pass


class InteractiveSessionManager:
    """
    JumpServer 交互式会话管理器

    该类封装了从获取向导连接令牌到建立实际会话的完整流程，
    并提供命令执行、会话管理等功能。

    会话凭证通过文件持久化，支持跨进程复用。

    典型用法：
    1. connect() - 获取令牌并建立会话（凭证保存到文件）
    2. execute() - 在会话中执行命令/SQL（从文件读取凭证，重新连接后执行）
    3. disconnect() - 断开会话（删除凭证文件）
    """

    JMS_USERNAME_PREFIX = "JMS-"

    def __init__(self, client: Optional[JumpServerClient] = None) -> None:
        self._client = client
        self._connector: Optional[SSHGuideConnector] = None
        self._registry = get_session_registry()

    def _ensure_connector(self) -> SSHGuideConnector:
        if self._connector is None:
            if self._client is None:
                self._client = create_client()
            self._connector = SSHGuideConnector(self._client)
        return self._connector

    def _build_handler(self, session: SessionInfo, timeout: int = 30):
        """根据会话信息构建对应的 handler（不连接）"""
        if ProtocolType.is_ssh(session.protocol):
            return SSHSessionHandler(
                host=session.host,
                port=session.port,
                username=session.username,
                password=session.token_password,
                timeout=timeout,
            )
        elif ProtocolType.is_db(session.protocol):
            return DBSessionHandler(
                host=session.host,
                port=session.port,
                username=session.username,
                password=session.token_password,
                protocol=session.protocol,
                timeout=timeout,
            )
        else:
            raise InteractiveSessionError(
                f"Unsupported protocol: {session.protocol}",
                details=f"当前支持交互式会话的协议：ssh, mysql, mariadb, postgresql, mongodb"
            )

    def connect(
        self,
        asset: str,
        account: str,
        protocol: str = "ssh",
        input_username: str = "",
        input_secret: str = "",
        connect_options: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """
        建立交互式会话

        流程：
        1. 获取向导连接令牌
        2. 使用令牌建立实际连接（验证可用性）
        3. 保存凭证到文件
        4. 返回会话信息

        Args:
            asset: 资产标识（UUID、名称或地址）
            account: 账号标识（UUID、名称或用户名）
            protocol: 协议类型（ssh, mysql, postgresql 等）
            input_username: 可选的输入用户名
            input_secret: 可选的输入密码
            connect_options: 连接选项
            timeout: 连接超时（秒）

        Returns:
            Dict[str, Any]: 连接结果，包含 session_id 和会话信息

        Raises:
            InteractiveSessionError: 连接失败时抛出
        """
        connector = self._ensure_connector()

        # 1. 获取向导连接令牌
        try:
            token = connector.get_connection_token(
                asset=asset,
                account=account,
                protocol=protocol,
                input_username=input_username,
                input_secret=input_secret,
                connect_options=connect_options,
            )
        except SSHConnectionTokenError as exc:
            raise InteractiveSessionError(
                f"Failed to get connection token: {exc}",
                details=str(exc),
            ) from exc

        token_id = str(token.get("id") or "").strip()
        token_value = str(token.get("value") or "").strip()

        if not token_id or not token_value:
            raise InteractiveSessionError(
                "Connection token missing id or value",
                details=f"Token response: {json.dumps(token, default=str)[:200]}"
            )

        # 2. 构建 SSH 用户名
        if ProtocolType.is_ssh(protocol) and not token_id.startswith(self.JMS_USERNAME_PREFIX):
            username = f"{self.JMS_USERNAME_PREFIX}{token_id}"
        else:
            username = token_id

        # 3. 获取 endpoint 信息
        endpoint_info = self._resolve_endpoint(protocol)
        host = endpoint_info.get("host", "")
        port = endpoint_info.get("port", 0)

        if not host:
            raise InteractiveSessionError(
                "Cannot resolve connection endpoint host",
                details="无法解析堡垒机连接端点的主机地址"
            )
        if not port:
            raise InteractiveSessionError(
                "Cannot resolve connection endpoint port",
                details=f"无法解析协议 {protocol} 对应的端口"
            )

        # 4. 获取资产和账号名称
        asset_display = str(token.get("asset_display") or asset)
        account_username = str(
            token.get("account", {}).get("username", "")
            if isinstance(token.get("account"), dict) else account
        )
        expires_at = str(token.get("date_expired") or "")

        # 5. 生成 session_id
        import uuid
        session_id = str(uuid.uuid4())[:8]

        now = time.strftime("%Y/%m/%d %H:%M:%S")

        # 6. 注意：不在此处验证连接可用性
        # JumpServer SSH 向导 Token 可能为一次性使用，验证连接会消耗 Token，
        # 导致后续 execute() 时认证失败。改为在 execute() 时才建立连接。
        # DB 协议的 Token 可以重复使用，但为保持一致性，也不在此处验证。

        # 7. 创建并保存 SessionInfo
        session = SessionInfo(
            session_id=session_id,
            protocol=protocol,
            host=host,
            port=port,
            username=username,
            token_password=token_value,
            asset_name=asset_display,
            account_username=account_username,
            expires_at=expires_at,
            connected_at=now,
            last_activity_at=now,
            status="connected",
        )
        self._registry.register(session)

        return {
            "status": "connected",
            "session_id": session_id,
            "protocol": protocol,
            "host": host,
            "port": port,
            "username": username,
            "asset_name": asset_display,
            "account_username": account_username,
            "expires_at": expires_at,
            "connected_at": now,
        }

    def _build_handler_for_connect(
        self, host: str, port: int, username: str,
        token_value: str, protocol: str, timeout: int,
    ):
        """根据协议构建连接 handler"""
        if ProtocolType.is_ssh(protocol):
            return SSHSessionHandler(
                host=host, port=port, username=username,
                password=token_value, timeout=timeout,
            )
        elif ProtocolType.is_db(protocol):
            return DBSessionHandler(
                host=host, port=port, username=username,
                password=token_value, protocol=protocol, timeout=timeout,
            )
        else:
            raise InteractiveSessionError(
                f"Unsupported protocol for interactive session: {protocol}",
                details=f"当前支持交互式会话的协议：ssh, mysql, mariadb, postgresql, mongodb"
            )

    def execute(self, session_id: str, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        在指定会话中执行命令

        从文件读取凭证，重新建立连接，执行后关闭连接。

        Args:
            session_id: 会话 ID
            command: 要执行的命令（SSH 为 shell 命令，DB 为 SQL）
            timeout: 执行超时（秒）

        Returns:
            Dict[str, Any]: 执行结果

        Raises:
            InteractiveSessionError: 执行失败时抛出
        """
        session = self._registry.get(session_id)
        if not session:
            raise InteractiveSessionError(
                f"Session not found: {session_id}",
                details="指定的会话不存在，可能已断开或未创建。请先使用 connect 命令建立会话。"
            )

        if session.status not in ("connected",):
            raise InteractiveSessionError(
                f"Session is not connected (status: {session.status})",
                details=f"会话状态为 {session.status}，无法执行命令"
            )

        # 检查令牌是否过期
        if session.expires_at:
            try:
                expires = time.strptime(session.expires_at, "%Y/%m/%d %H:%M:%S %z")
                if time.time() > time.mktime(expires):
                    self._registry.update(session_id, status="expired",
                                           error_message="Token expired")
                    raise InteractiveSessionError(
                        f"Session token expired at {session.expires_at}",
                        details="会话令牌已过期，请重新建立连接"
                    )
            except (ValueError, OverflowError):
                pass  # 无法解析过期时间，继续执行

        # 构建 handler 并连接
        handler = self._build_handler(session, timeout)
        try:
            handler.connect()
            result = handler.execute(command, timeout=timeout)
            result["session_id"] = session_id
            result["protocol"] = session.protocol

            # 更新最后活动时间
            self._registry.update(session_id, last_activity_at=time.strftime("%Y/%m/%d %H:%M:%S"))
            return result
        except InteractiveSessionError:
            raise
        except Exception as exc:
            self._registry.update(session_id, status="error", error_message=str(exc))
            raise InteractiveSessionError(
                f"Command execution failed: {exc}",
                details=str(exc),
            ) from exc
        finally:
            handler.close()

    def disconnect(self, session_id: str) -> Dict[str, Any]:
        """
        断开会话

        Args:
            session_id: 会话 ID

        Returns:
            Dict[str, Any]: 断开结果
        """
        session = self._registry.get(session_id)
        if not session:
            return {
                "status": "not_found",
                "session_id": session_id,
                "message": f"Session {session_id} not found",
            }

        result = {
            "status": "disconnected",
            "session_id": session_id,
            "protocol": session.protocol,
            "host": session.host,
            "port": session.port,
            "last_activity_at": session.last_activity_at,
        }

        self._registry.remove(session_id)
        return result

    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有活跃会话"""
        return self._registry.list_sessions()

    def session_status(self, session_id: str) -> Dict[str, Any]:
        """获取会话状态"""
        session = self._registry.get(session_id)
        if not session:
            return {
                "status": "not_found",
                "session_id": session_id,
            }
        return session.to_public_dict()

    def _resolve_endpoint(self, protocol: str) -> Dict[str, Any]:
        """解析堡垒机 endpoint 信息"""
        from jms_ssh_guide_cli import _resolve_endpoint

        if self._client is None:
            self._client = create_client()

        return _resolve_endpoint(self._client, protocol)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_session_manager(client: Optional[JumpServerClient] = None) -> InteractiveSessionManager:
    """创建交互式会话管理器"""
    return InteractiveSessionManager(client=client)


if __name__ == "__main__":
    import sys
    print(
        "This module is designed to be imported and used as part of the JumpServer skills.",
        file=sys.stderr,
    )
    print(
        "Use: from jms_interactive_session import InteractiveSessionManager",
        file=sys.stderr,
    )
    sys.exit(1)
