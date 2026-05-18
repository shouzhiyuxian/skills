# SSH 向导连接 (SSH Guide Connection) 说明文档

## 概述

SSH 向导连接是堡垒机提供的一种便捷的远程连接方式。该文档说明如何在 JumpServer skills 项目中使用 SSH 向导连接功能获取临时连接令牌。

## 功能特性

✨ **核心特性**：
- 通过资产名称、IP 地址或 UUID 自动查询和解析资产
- 通过账号名称、用户名或 UUID 自动查询和解析账号
- 获取临时连接令牌（用户名和密码）
- 支持多种连接协议（SSH、RDP、VNC、数据库等）
- 完整的错误处理和提示

## 功能说明

### 什么是 SSH 向导连接？

SSH 向导连接是堡垒机中一种简化的连接流程：
1. 用户选择要连接的资产（主机）
2. 选择要使用的账号（用户/密钥）
3. 选择连接协议（SSH、RDP、VNC 等）
4. 堡垒机返回一个临时的连接令牌
5. 使用这个令牌连接到目标资产

### 核心 API 端点

```
POST /api/v1/authentication/connection-token/
```

**功能**: 获取用于 SSH 向导连接的临时令牌。

**请求负载示例**:
```json
{
  "asset": "2fcc289b-f985-4e51-bde9-65d63bf47cca",
  "account": "fb13bca0-6136-4d83-9bc0-6de7087d99fd",
  "protocol": "ssh",
  "input_username": "root",
  "input_secret": "",
  "connect_method": "ssh_guide",
  "connect_options": {
    "charset": "default",
    "disableautohash": false,
    "token_reusable": false,
    "resolution": "auto",
    "backspaceAsCtrlH": false,
    "appletConnectMethod": "web",
    "virtualappConnectMethod": "web",
    "reusable": false,
    "rdp_connection_speed": "auto"
  }
}
```

**响应示例**:
```json
{
  "id": "username_for_connection",
  "value": "temporary_token_password"
}
```

其中：
- `id`: 用作 SSH 连接的用户名
- `value`: 用作 SSH 连接的密码（临时令牌）

## 模块结构

### 1. Core Module: `jms_ssh_guide.py`

核心模块，不能作为独立脚本运行，需要被导入使用。

#### 类和函数

##### `SSHGuideConnector` 类

主要的连接器类，处理与堡垒机的通信。

**初始化**:
```python
from jms_api_client import JumpServerClient
from jms_ssh_guide import SSHGuideConnector

client = JumpServerClient(config)
connector = SSHGuideConnector(client)
```

**核心方法**:

- **`get_connection_token(asset, account, protocol="ssh", input_username="", input_secret="", connect_method="ssh_guide", connect_options=None)`**
  
  获取向导连接令牌。
  
  参数说明：
  - `asset` (str): 资产 UUID，例如 `"2fcc289b-f985-4e51-bde9-65d63bf47cca"`
  - `account` (str): 账号 UUID，例如 `"fb13bca0-6136-4d83-9bc0-6de7087d99fd"`
  - `protocol` (str): 协议类型，默认 `"ssh"`
    - 支持的协议: `ssh`, `rdp`, `telnet`, `vnc`, `mysql`, `mariadb`, `mongodb`, `postgresql`
  - `input_username` (str): 输入的用户名（可选）
  - `input_secret` (str): 输入的密码/密钥（可选）
  - `connect_method` (str): 连接方法，默认 `"ssh_guide"`
  - `connect_options` (Dict): 连接选项字典
  
  返回值：
  - `Dict[str, Any]`: 包含 `id` 和 `value` 的连接令牌字典
  
  异常：
  - `SSHConnectionTokenError`: 当获取令牌失败时抛出

- **`get_connection_credentials(asset, account, protocol="ssh", ...)`**
  
  便利方法，直接返回连接凭证对 (用户名, 密码)。
  
  返回值：
  - `tuple[str, str]`: (用户名, 密码) 元组

### 2. CLI Tools: `jms_ssh_guide_cli.py`

命令行工具，提供易用的命令行接口。

## 使用指南

### 前置条件

1. 配置好 JumpServer API 连接信息
2. 拥有对目标资产和账号的访问权限
3. 资产和账号可以通过名称、地址、用户名或 UUID 标识

### 通过 Python 代码使用

#### 最简单的方式（推荐）- 使用资产和账号名称

```python
from jms_runtime import create_client
from jms_ssh_guide import SSHGuideConnector

# 创建客户端
client = create_client()

# 创建连接器
connector = SSHGuideConnector(client)

# 使用资产名称和账号用户名获取连接令牌
# 无需 UUID，自动自动查询和解析！
token = connector.get_connection_token(
    asset="server-prod-01",        # 资产名称（而不是 UUID）
    account="root",                # 账号用户名（而不是 UUID）
    protocol="ssh"
)

# 使用令牌连接
username = token['id']
password = token['value']
print(f"SSH连接命令: ssh {username}@target_host")
```

#### 便捷方法 - 直接获取凭证对

```python
from jms_runtime import create_client
from jms_ssh_guide import SSHGuideConnector

client = create_client()
connector = SSHGuideConnector(client)

# 直接获取用户名和密码
username, password = connector.get_connection_credentials(
    asset="server-prod-01",
    account="root"
)

print(f"Username: {username}")
print(f"Password: {password}")
```

#### 完整高级用法 - 指定所有选项

```python
token = connector.get_connection_token(
    asset="server-prod-01",
    account="root",
    protocol="ssh",
    input_username="",
    input_secret="",
    connect_method="ssh_guide",
    connect_options={
        "charset": "utf-8",
        "token_reusable": False,
        "resolution": "1920x1080"
    },
    auto_resolve=True  # 自动查询资产和账号
)
```

### 通过命令行使用

#### 使用资产和账号名称（最新版）

**获取完整令牌信息：**
```bash
cd /path/to/skills
python3 jumpserver-guided-connection/scripts/jms_ssh_guide_cli.py get-token \
  --asset server-prod-01 \
  --account root \
  --protocol ssh \
  --output json
```

**获取连接凭证（仅用户名和密码）：**
```bash
python3 jumpserver-guided-connection/scripts/jms_ssh_guide_cli.py get-credentials \
  --asset server-prod-01 \
  --account root
```

#### 支持的资产和账号标识方式

| 类型 | 示例 | 说明 |
|------|------|------|
| **资产** | | |
| UUID | `2fcc289b-f985-4e51-bde9-65d63bf47cca` | 完整的资产 UUID |
| 名称 | `server-prod-01` | 资产的友好名称 |
| IP 地址 | `192.168.1.100` | 资产的 IP 地址 |
| 混合格式 | `server-prod-01(192.168.1.100)` | 名称和地址的组合 |
| **账号** | | |
| UUID | `fb13bca0-6136-4d83-9bc0-6de7087d99fd` | 完整的账号 UUID |
| 用户名 | `root` | 账号的用户名 |
| 账号名称 | `root_account` | 账号的友好名称 |
| 混合格式 | `root_account(root)` | 名称和用户名的组合 |

#### 高级选项

```bash
python3 jumpserver-guided-connection/scripts/jms_ssh_guide_cli.py get-token \
  --asset server-prod-01 \
  --account root \
  --protocol ssh \
  --connect-method ssh_guide \
  --charset utf-8 \
  --token-reusable false \
  --resolution auto \
  --output json
```

输出格式选项 `--output`：
- `json` (默认): JSON 格式输出
- `table`: 表格格式输出
- `raw`: 原始格式输出

### 支持的协议与默认端口

| 协议 | 说明 | 默认端口 |
|------|------|----------|
| `ssh` | SSH 连接 | 2222 |
| `rdp` | Windows 远程桌面 | 3389 |
| `vnc` | VNC 远程控制 | 15900 |
| `mysql` | MySQL 数据库 | 33061 |
| `mariadb` | MariaDB 数据库 | 33062 |
| `postgresql` | PostgreSQL 数据库 | 54320 |
| `mongodb` | MongoDB 数据库 | 27018 |
| `redis` | Redis 数据库 | 63790 |
| `telnet` | Telnet 连接 | 2222 |
| `oracle` | Oracle 数据库 | 15210 |
| `sqlserver` | SQL Server 数据库 | 14330 |

## 自动解析功能说明 (Auto-Resolve)

默认情况下，SSH 向导连接器会自动解析资产和账号标识：

### 工作流程

1. **输入识别**: 接收用户输入的资产/账号标识
2. **UUID 检查**: 如果输入是 UUID 格式，直接使用
3. **列表查询**: 查询当前组织的所有资产和账号
4. **名称匹配**: 进行精确和模糊匹配
5. **歧义检测**: 如果匹配到多个结果，给出明确错误提示
6. **UUID 返回**: 返回唯一匹配项的 UUID

### 匹配规则

#### 资产匹配（按优先级）

1. **精确 UUID 匹配**: 输入的 UUID 完全相同
2. **精确名称匹配**: 输入与资产名称完全相同（不区分大小写）
3. **精确地址匹配**: 输入与资产 IP 地址完全相同
4. **模糊名称匹配**: 输入包含在资产名称中
5. **模糊地址匹配**: 输入包含在资产地址中

#### 账号匹配（按优先级）

1. **精确 UUID 匹配**: 输入的 UUID 完全相同
2. **精确用户名匹配**: 输入与账号用户名完全相同（不区分大小写）
3. **精确名称匹配**: 输入与账号名称完全相同（不区分大小写）
4. **模糊用户名匹配**: 输入包含在账号用户名中
5. **模糊名称匹配**: 输入包含在账号名称中

### 禁用自动解析

如果需要直接使用 UUID（跳过查询），设置 `auto_resolve=False`：

```python
# Python API
token = connector.get_connection_token(
    asset="2fcc289b-f985-4e51-bde9-65d63bf47cca",
    account="fb13bca0-6136-4d83-9bc0-6de7087d99fd",
    auto_resolve=False  # 禁用自动解析
)
```

## 连接选项 (Connect Options) 详解

`connect_options` 字典控制连接的行为，包含以下常用字段：

| 选项 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `charset` | string | `"default"` | 字符集编码 |
| `disableautohash` | boolean | `false` | 是否禁用自动 hash 验证 |
| `token_reusable` | boolean | `false` | 获取的令牌是否可重复使用 |
| `resolution` | string | `"auto"` | 分辨率（仅 RDP 使用），如 `"1920x1080"` |
| `backspaceAsCtrlH` | boolean | `false` | Backspace 键是否作为 Ctrl+H 发送（仅终端使用） |
| `appletConnectMethod` | string | `"web"` | Applet 连接方法：`"web"` 或 `"local"` |
| `virtualappConnectMethod` | string | `"web"` | 虚拟应用连接方法：`"web"` 或 `"local"` |
| `reusable` | boolean | `false` | 连续是否可重用 |
| `rdp_connection_speed` | string | `"auto"` | RDP 连接速度，枚举值：`"auto"`, `"modem"`, `"broadband"`, `"lan"` |

## 常见操作场景

### 场景 1: 获取 SSH 连接凭证

```python
from jms_runtime import create_client
from jms_ssh_guide import SSHGuideConnector

client = create_client()
connector = SSHGuideConnector(client)

username, password = connector.get_connection_credentials(
    asset="<asset-uuid>",
    account="<account-uuid>",
    protocol="ssh"
)

# 使用凭证连接
import os
os.system(f"sshpass -p '{password}' ssh {username}@target_host")
```

### 场景 2: 获取 RDP 连接凭证

```python
connector = SSHGuideConnector(client)

token = connector.get_connection_token(
    asset="<asset-uuid>",
    account="<account-uuid>",
    protocol="rdp",
    connect_options={
        "resolution": "1920x1080",
        "rdp_connection_speed": "lan"
    }
)

# 使用 RDP 连接
rdp_username = token['id']
rdp_password = token['value']
```

### 场景 3: 获取数据库连接凭证

```python
connector = SSHGuideConnector(client)

token = connector.get_connection_token(
    asset="<asset-uuid>",
    account="<account-uuid>",
    protocol="mysql",  # 或 'mariadb', 'postgresql', 'mongodb'
)

db_username = token['id']
db_password = token['value']
```

## 错误处理

```python
from jms_ssh_guide import SSHConnectionTokenError

try:
    token = connector.get_connection_token(
        asset="invalid-uuid",
        account="invalid-uuid"
    )
except SSHConnectionTokenError as e:
    print(f"获取令牌失败: {e}")
    print(f"错误详情: {e.details}")
```

## 常见错误及解决

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| 404 Not Found | API 端点不可用或 JumpServer 版本不支持 | 检查 JumpServer 版本是否 >= v4.10 |
| 401 Unauthorized | 认证失败 | 检查 API 凭证（access_key, secret_key）是否正确 |
| 403 Forbidden | 无访问权限 | 检查用户是否有该资产和账号的访问权限 |
| 400 Bad Request | 请求参数错误 | 检查 asset、account 是否有效，protocol 是否支持 |
| Connection Token Error | 令牌获取失败 | 检查响应是否包含 `id` 和 `value` 字段 |

## API 兼容性

该功能需要 JumpServer API v1 支持，具体版本要求：
- **JumpServer >= v4.10**: 完全支持所有功能
- **JumpServer < v4.10**: 不支持此 API 端点

## 性能和安全考虑

1. **令牌有效期**: 通常来说，连接令牌有一定的时间有效期，不应长时间保存
2. **重用策略**: 设置 `token_reusable=false` 获取一次性令牌（更安全）
3. **日志**: 避免在日志中记录返回的密码/令牌
4. **TLS 验证**: 生产环境建议启用 TLS 验证

```python
config = JumpServerConfig(
    base_url="https://jumpserver.example.com",
    # ...
    verify_tls=True  # 启用 TLS 验证
)
```

## 文件结构

```
jumpserver-api/
├── jms_ssh_guide.py          # 核心模块
├── jms_ssh_guide_cli.py      # CLI 工具
└── ...

jumpserver-guided-connection/
├── SKILL.md                   # 子 skill 路由规则
├── agents/
│   └── openai.yaml           # 接入描述
└── scripts/
    └── jms_ssh_guide_cli.py  # 本地入口脚本
```

## 相关文档

- [JumpServer API 文档](http://10.1.12.62/docs/api/)
- [堡垒机 SSH 连接流程](./routing-playbook.md)
- [权限管理](./permissions.md)
