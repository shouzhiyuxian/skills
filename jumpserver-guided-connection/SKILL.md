---
name: jumpserver-guided-connection
description: Use when users ask to connect to an asset via guided SSH, RDP, VNC, or database protocols (MySQL, PostgreSQL, MongoDB, etc.), get temporary connection tokens, retrieve connection credentials, or perform guided connections to JumpServer assets.
---

# JumpServer Guided Connection

## Overview

这个子 skill 负责通过 JumpServer 向导方式获取临时连接令牌，并支持 SSH、RDP、VNC 以及数据库协议（MySQL、PostgreSQL、MongoDB 等）的向导连接。

## Use When

- 用户要获取 SSH 向导连接令牌
- 用户要连接到某个资产（SSH、RDP、VNC）
- 用户要连接到数据库资产（MySQL、PostgreSQL、MongoDB、MariaDB、Redis 等）
- 用户要获取连接用户名和密码
- 用户要生成临时连接令牌
- 问题涉及连接令牌、导向连接、connection-token

不要用在纯对象查询、权限解释、审计调查或使用报告上。

## Primary Entrypoints

- `python3 jumpserver-guided-connection/scripts/jms_ssh_guide_cli.py get-credentials --asset <asset> --account <account>`
- `python3 jumpserver-guided-connection/scripts/jms_ssh_guide_cli.py get-token --asset <asset> --account <account> --protocol <protocol>`

## Quick Examples

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

## Supported Protocols

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

## Read These References

- [../references/ssh-guide-connection.md](../references/ssh-guide-connection.md)
- [../references/runtime.md](../references/runtime.md)
- [../references/safety-rules.md](../references/safety-rules.md)

## Guardrails

- 只用于获取连接令牌和凭证，不执行实际的远程连接
- 资产和账号标识支持名称、IP 地址或 UUID 自动解析
- 若匹配到多个资产或账号，先阻塞并返回候选列表，不自动选择
- 令牌有效期由服务器控制，客户端不应长时间缓存
- 不记录或回显返回的密码/令牌到日志
