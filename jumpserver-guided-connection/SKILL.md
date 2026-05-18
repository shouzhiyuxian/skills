---
name: jumpserver-guided-connection
description: Use when users ask to connect to an asset via guided SSH, RDP, VNC, or database protocols (MySQL, PostgreSQL, MongoDB, etc.), get temporary connection tokens, retrieve connection credentials, perform guided connections to JumpServer assets, or establish interactive sessions to execute commands/SQL on remote assets.
---

# JumpServer Guided Connection

## Overview

这个子 skill 负责通过 JumpServer 向导方式获取临时连接令牌，支持 SSH、RDP、VNC 以及数据库协议（MySQL、PostgreSQL、MongoDB 等）的向导连接，**并支持通过交互式会话直接在远程资产上执行命令和 SQL**。

## Use When

- 用户要获取 SSH 向导连接令牌
- 用户要连接到某个资产（SSH、RDP、VNC）
- 用户要连接到数据库资产（MySQL、PostgreSQL、MongoDB、MariaDB、Redis 等）
- 用户要获取连接用户名和密码
- 用户要生成临时连接令牌
- 用户要在远程资产上执行命令（如 hostname、ls、cat 等）
- 用户要在数据库上执行 SQL（如 SHOW DATABASES、SELECT 等）
- 用户希望保持登录态，持续操作远程资产
- 问题涉及连接令牌、导向连接、connection-token、交互式会话

不要用在纯对象查询、权限解释、审计调查或使用报告上。

## Primary Entrypoints

### 向导连接令牌（仅获取凭证）

- `python3 jumpserver-guided-connection/scripts/jms_ssh_guide_cli.py get-credentials --asset <asset> --account <account>`
- `python3 jumpserver-guided-connection/scripts/jms_ssh_guide_cli.py get-token --asset <asset> --account <account> --protocol <protocol>`

### 交互式会话（连接 + 执行命令/SQL）

- `python3 jumpserver-guided-connection/scripts/jms_interactive_cli.py connect --asset <asset> --account <account> --protocol <protocol>`
- `python3 jumpserver-guided-connection/scripts/jms_interactive_cli.py exec --session <session_id> --command "<command>"`
- `python3 jumpserver-guided-connection/scripts/jms_interactive_cli.py list-sessions`
- `python3 jumpserver-guided-connection/scripts/jms_interactive_cli.py disconnect --session <session_id>`

## Quick Examples

### 获取向导连接凭证

```bash
# SSH 向导连接
python3 jumpserver-guided-connection/scripts/jms_ssh_guide_cli.py get-credentials \
  --asset server-prod-01 \
  --account root

# 指定协议连接
python3 jumpserver-guided-connection/scripts/jms_ssh_guide_cli.py get-credentials \
  --asset mysql-host \
  --account dbadmin \
  --protocol mysql

# 获取完整令牌信息
python3 jumpserver-guided-connection/scripts/jms_ssh_guide_cli.py get-token \
  --asset server-prod-01 \
  --account root \
  --protocol ssh \
  --output json
```

### 交互式会话

```bash
# 1. 建立 SSH 交互式会话
python3 jumpserver-guided-connection/scripts/jms_interactive_cli.py connect \
  --asset 10.1.12.62 \
  --account root \
  --protocol ssh

# 2. 在会话中执行命令
python3 jumpserver-guided-connection/scripts/jms_interactive_cli.py exec \
  --session <session_id> \
  --command "hostname && whoami && uptime"

# 3. 建立 MySQL 交互式会话
python3 jumpserver-guided-connection/scripts/jms_interactive_cli.py connect \
  --asset 62mysql \
  --account root \
  --protocol mysql

# 4. 在数据库会话中执行 SQL
python3 jumpserver-guided-connection/scripts/jms_interactive_cli.py exec \
  --session <session_id> \
  --command "SHOW DATABASES;"

# 5. 查看所有活跃会话
python3 jumpserver-guided-connection/scripts/jms_interactive_cli.py list-sessions

# 6. 断开会话
python3 jumpserver-guided-connection/scripts/jms_interactive_cli.py disconnect \
  --session <session_id>
```

## Supported Protocols

| 协议 | 说明 | 默认端口 | 交互式会话 |
|------|------|----------|------------|
| `ssh` | SSH 连接 | 2222 | ✅ 支持 |
| `rdp` | Windows 远程桌面 | 3389 | ❌ 仅令牌 |
| `vnc` | VNC 远程控制 | 15900 | ❌ 仅令牌 |
| `mysql` | MySQL 数据库 | 33061 | ✅ 支持 |
| `mariadb` | MariaDB 数据库 | 33062 | ✅ 支持 |
| `postgresql` | PostgreSQL 数据库 | 54320 | ✅ 支持 |
| `mongodb` | MongoDB 数据库 | 27018 | ✅ 支持 |
| `redis` | Redis 数据库 | 63790 | ❌ 仅令牌 |

## Read These References

- [../references/ssh-guide-connection.md](../references/ssh-guide-connection.md)
- [../references/runtime.md](../references/runtime.md)
- [../references/safety-rules.md](../references/safety-rules.md)

## Guardrails

- 资产和账号标识支持名称、IP 地址或 UUID 自动解析
- 若匹配到多个资产或账号，先阻塞并返回候选列表，不自动选择
- 令牌有效期由服务器控制，客户端不应长时间缓存
- 不记录或回显返回的密码/令牌到日志
- 交互式会话通过向导令牌的 username/password 自动认证，无需手动输入密码
- 每次交互式连接会获取新的临时令牌，令牌过期后会话自动失效
- 交互式会话在进程生命周期内有效，进程退出后会话自动断开
