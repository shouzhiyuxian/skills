---
name: jumpserver-skills
description: Use when users ask about JumpServer V4.10 but the intent may span object lookup, effective access, permissions, audit investigation, usage reporting, configuration, org selection, or governance inspection, and a router skill should first select the right narrower JumpServer sub-skill.
---

# JumpServer Skills Router

这是兼容旧入口的总路由 skill。它不再承载全部细节规则，而是先判断意图，再把请求交给更窄的 JumpServer 子 skill。

## Shared Runtime

只使用各子 skill 下的正式 CLI 入口；`jumpserver-api/` 只是内部共享实现，不直接当业务入口调用：

- `python3 jumpserver-object-query/scripts/jms_query.py ...`
- `python3 jumpserver-runtime-setup/scripts/jms_diagnose.py ...`
- `python3 jumpserver-effective-access/scripts/jms_diagnose.py ...`
- `python3 jumpserver-permission-analysis/scripts/jms_query.py ...`
- `python3 jumpserver-permission-analysis/scripts/jms_diagnose.py ...`
- `python3 jumpserver-audit-investigation/scripts/jms_query.py ...`
- `python3 jumpserver-audit-investigation/scripts/jms_diagnose.py ...`
- `python3 jumpserver-governance-inspection/scripts/jms_diagnose.py ...`
- `python3 jumpserver-usage-reporting/scripts/jms_report.py ...`

上面的路径默认以仓库根目录为当前工作目录；如果调用方 cwd 不在根目录，先切换到根目录，或改用仓库相对路径。这属于执行上下文问题，不要表述成"仓库路径写错"。

共享运行时与边界先看：

- [references/runtime.md](references/runtime.md)
- [references/safety-rules.md](references/safety-rules.md)
- [references/troubleshooting.md](references/troubleshooting.md)

## Route To Subskills

按用户意图优先选择下面的子 skill：

- `jumpserver-runtime-setup`：配置、预检、连通性、组织切换、执行上下文与轻量排障
- `jumpserver-object-query`：资产、账号、用户、组织、平台、节点、标签、网域等对象查询
- `jumpserver-effective-access`：某用户当前能访问哪些资产、节点、账号、协议
- `jumpserver-permission-analysis`：授权规则、ACL、RBAC、为什么能访问、资产授权给了谁
- `jumpserver-audit-investigation`：登录、会话、命令、文件传输、作业、页面同款审计明细与命名用户登录次数
- `jumpserver-usage-reporting`：某天或某时间段的使用报告、排行、概览、HTML 模板报告
- `jumpserver-governance-inspection`：治理巡检、capability 聚合、系统设置、许可证、工单、存储、组件负载、改密失败报表
- `jumpserver-guided-connection`：SSH 向导连接、RDP/VNC 向导连接、数据库协议（MySQL/PostgreSQL/MongoDB 等）向导连接、获取临时连接令牌

如果一句话同时命中多类，先看 [references/routing-playbook.md](references/routing-playbook.md) 再决定优先级。

## Shared Guardrails

- 先走预检：`config-status --json`，必要时 `config-write --confirm`，然后 `ping`
- 允许本地运行时写入 `.env` 和当前组织上下文，不执行 JumpServer 业务写操作
- 不生成临时 SDK/HTTP 脚本，不绕过正式入口
- 组织不明确、对象重名、平台不明确、跨组织命中时先阻塞，不猜
- 正式入口返回的 JSON key 保持英文契约；对最终用户回显时优先使用中文标签
- 阻塞或参数错误时优先解释 `reason_code`、`user_message`、`action_hint`、`suggested_commands`

## High-Priority Routes

- 获取 SSH 向导连接令牌、连接到某资产、获取连接用户名密码、connection-token 时，优先用 `jumpserver-guided-connection`
- 命名用户在某时间窗"登录多少次 / 成功登录多少次 / 失败登录多少次"时，优先用 `jumpserver-audit-investigation`
- 某天或某时间段的使用情况、概览、排行、TOP、日报、周报时，优先用 `jumpserver-usage-reporting`
- "某某用户在某组织下有哪些资产 / 节点 / 账号 / 协议"时，优先用 `jumpserver-effective-access`
- "为什么能访问 / 权限详情 / ACL / RBAC / 授权给了谁"时，优先用 `jumpserver-permission-analysis`

## References

- [references/routing-playbook.md](references/routing-playbook.md)
- [references/runtime.md](references/runtime.md)
- [references/safety-rules.md](references/safety-rules.md)
- [references/migration-map.md](references/migration-map.md)
