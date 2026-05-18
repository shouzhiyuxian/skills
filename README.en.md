# JumpServer Skills

`jumpserver-skills` is a JumpServer V4.10 skill repository. The repository now uses a split layout: one backward-compatible router skill at the root, several narrower intention-driven child skills, and a shared runtime. It still covers object lookup, permission readback, audit investigation, governance inspection, access analysis, and bastion usage reporting, but the trigger boundaries are now narrower and easier to maintain.

Inside the repository, requests still reuse the same three formal entrypoints: `jms_query.py`, `jms_diagnose.py`, and `jms_report.py`. The repository stays read-only by default, only allowing local runtime writes to `.env` and the current organization context, and it does not perform JumpServer business write operations.

[中文](./README.md)

## Quick Start

1. Connect this skill to your agent or Codex environment. The repository file [agents/openai.yaml](./agents/openai.yaml) can be used directly as the integration description.
2. Initialize the configuration in natural language, for example: "Help me generate `.env`. My JumpServer URL is `https://jump.example.com`, and I log in with AK/SK."
3. Then continue with direct requests such as "Which assets can this user access in the Default organization?" or "Show me yesterday's usage."

For first-time use, the natural-language `.env` generation path is usually the fastest option.

## What This Skill Can Do

| Capability Group | Suitable Requests | Entrypoint | Notes |
|---|---|---|---|
| Object queries | queries for assets, accounts, users, user groups, orgs, platforms, nodes, labels, and domains | `jms_query.py` | Best for exact object lists or reading a single object in detail |
| Permission relationships | permission rules, ACL, RBAC, who can access an asset, details of a permission rule | `jms_query.py` | Read and explain only; no permission writes |
| Audit investigation | login, session, command, file transfer, abnormal behavior, high-risk commands, failed login investigations | `jms_query.py` | Best for logs, records, details, and event-level requests |
| Configuration and diagnostics | config checks, connectivity, org switching, object resolution, license, system settings, storage, tickets | `jms_diagnose.py` | Best for preflight, environment confirmation, and governance prerequisites |
| User effective access scope | which assets or nodes a user can access, or which accounts/protocols a user can use on an asset | `jms_diagnose.py` | Returns effective access scope first instead of defaulting to permission-rule explanations |
| Governance inspection | asset governance, account governance, access analysis, system inspection, capability-based aggregate analysis | `jms_diagnose.py` | Prefer capability aggregation instead of forcing users to stitch together scattered queries |
| Usage reports | daily reports, usage situation, usage analysis, what happened on a day, rankings or overviews for a time range | `jms_report.py` | These requests produce a complete HTML report instead of a one-line summary |
| Guided connection | SSH/RDP/VNC guided connection, database protocol (MySQL/PostgreSQL/MongoDB, etc.) guided connection, get temporary connection tokens | `jms_ssh_guide_cli.py` | Supports automatic asset name and account name resolution |

## Subskill Layout

The repository keeps the root [SKILL.md](./SKILL.md) as the compatibility router skill and adds 8 narrower child skills:

| Child skill | Focus | Primary entrypoint |
|---|---|---|
| `jumpserver-runtime-setup` | configuration, preflight, connectivity, org switching, execution-context troubleshooting | `jms_diagnose.py` |
| `jumpserver-object-query` | assets, accounts, users, orgs, platforms, nodes, labels, zones, and object detail lookup | `jms_query.py` |
| `jumpserver-effective-access` | what a user can actually access right now | `jms_diagnose.py` |
| `jumpserver-permission-analysis` | permission rules, ACL, RBAC, why access exists, who is authorized to an asset | `jms_query.py` / `jms_diagnose.py` |
| `jumpserver-audit-investigation` | login, session, command, file-transfer, job details, named-user login counts | `jms_query.py` / `jms_diagnose.py` |
| `jumpserver-usage-reporting` | day or time-range usage overviews, rankings, and HTML reports | `jms_report.py` |
| `jumpserver-governance-inspection` | capability aggregation, settings, license, tickets, storage, governance inspection | `jms_diagnose.py` |
| `jumpserver-guided-connection` | SSH/RDP/VNC guided connection, database protocol guided connection, get temporary connection tokens | `jms_ssh_guide_cli.py` |

The shared pieces stay centralized: the reusable low-level modules now live in `jumpserver-api/`, `references/` remains the rules library, and `template/` remains the HTML-report template area.

To support hosts that can register only one skill at a time, each child skill directory now also contains:

- `agents/openai.yaml`: an integration descriptor for that child skill
- `scripts/*.py`: the local entrypoint scripts for each child skill; they load `jumpserver-api/` directly instead of treating `jumpserver-runtime-setup` as the host for all Python code

That means a `jumpserver-*` child directory can now be used directly as the skill root when needed.

## How To Use This Skill

1. Prepare the environment file. Create `.env` in the repository root. There are two ways to do it:

Manual method:

```bash
cp .env.example .env
```

Conversation method:

If local configuration is incomplete, the runtime can also generate `.env` directly through natural-language conversation. It collects `JMS_API_URL`, authentication mode, organization, timeout, and TLS settings in a fixed order, then writes the local `.env` after showing a masked summary. For example:

- "Help me generate `.env`. My JumpServer URL is `https://jump.example.com`, and I log in with AK/SK."
- "Help me initialize JumpServer config. I log in with username and password, and I do not want certificate verification."

2. Connect this skill to your agent or Codex environment. The repository file [agents/openai.yaml](./agents/openai.yaml) describes the router skill.

3. If your runtime supports multi-skill discovery, prefer triggering the narrower child skill directly. If the host can register only one skill at a time, you can also register a `jumpserver-*` child directory directly and use its own `agents/openai.yaml`.

4. Describe requests directly in natural language instead of manually assembling script commands. For example: "Which assets can this user access in the Default organization?", "Show me yesterday's usage", or "Show the details of this permission rule."

5. Add context based on the returned result. If the result shows `candidate_orgs`, `switchable_orgs`, candidate objects, or a missing time range, follow the prompt and provide the organization, object name, platform, or time window. When organization selection is mandatory, the response also includes `reason_code`, `user_message`, `action_hint`, `suggested_commands`, and `candidate_org_count` so the next step is explicit.

You do not need to remember specific execution commands. This skill performs preflight first, then routes to the formal entrypoint automatically, and prompts for organization, object, or time-range details only when needed.

## Manual CLI Path

If you want to run the formal entrypoints manually, use parameters in this order:

1. Prefer explicit arguments such as `--org-name`, `--name`, `--days`, and `--user`
2. Use repeated `--filter key=value` only for a few advanced fields
3. Keep `--filters '{"key":"value"}'` only for backward compatibility

Recommended style:

```bash
python3 jumpserver-runtime-setup/scripts/jms_diagnose.py select-org --org-name Default
python3 jumpserver-effective-access/scripts/jms_diagnose.py user-assets --org-name Default --username example.user
python3 jumpserver-object-query/scripts/jms_query.py object-list --resource organization --name Default
python3 jumpserver-audit-investigation/scripts/jms_query.py audit-analyze --capability session-record-query --days 7 --user example.user
python3 jumpserver-governance-inspection/scripts/jms_diagnose.py inspect --capability hot-assets-ranking --days 30 --top 10
python3 jumpserver-governance-inspection/scripts/jms_diagnose.py reports --report-type account-statistic --days 30
```

Compatibility style:

```bash
python3 jumpserver-object-query/scripts/jms_query.py object-list --resource organization --filters '{"name":"Default"}'
python3 jumpserver-audit-investigation/scripts/jms_query.py audit-analyze --capability session-record-query --filter user=example.user --filter days=7
```

List and analysis commands now auto-paginate and return the full result set for the requested range, so `--limit/--offset` are no longer supported.

## Environment Variables

The repository root provides [`.env.example`](./.env.example) as a template. In actual use, prepare the `.env` file in the repository root. You can copy the template and edit it, or create it manually by following the template.

If you do not want to edit it manually, you can also generate `.env` through natural-language conversation. When missing or incomplete configuration is detected, the skill collects the required fields in order and writes the configuration to the local `.env` through the formal entrypoint.

If you want to provide everything up front, these are usually enough:

- `JMS_API_URL`
- one complete credential pair: `JMS_ACCESS_KEY_ID/JMS_ACCESS_KEY_SECRET` or `JMS_USERNAME/JMS_PASSWORD`
- `JMS_ORG_ID`, which can be left empty if you are not sure yet
- `JMS_TIMEOUT`, which falls back to the default if omitted
- `JMS_VERIFY_TLS`, which defaults to `false` if omitted

| Variable | Required | Notes |
|---|---|---|
| `JMS_API_URL` | required | JumpServer API / access URL |
| `JMS_ACCESS_KEY_ID` | paired with `JMS_ACCESS_KEY_SECRET`, or use username/password instead | API Access Key ID |
| `JMS_ACCESS_KEY_SECRET` | paired with `JMS_ACCESS_KEY_ID`, or use username/password instead | API Access Key Secret |
| `JMS_USERNAME` | paired with `JMS_PASSWORD`, or use AK/SK instead | JumpServer login username |
| `JMS_PASSWORD` | paired with `JMS_USERNAME`, or use AK/SK instead | JumpServer login password |
| `JMS_ORG_ID` | optional during initialization | written before business execution through org selection or reserved-org rules |
| `JMS_TIMEOUT` | optional | request timeout in seconds |
| `JMS_VERIFY_TLS` | optional | whether to verify certificates, default `false` |

Environment variable rules:

- `JMS_API_URL` must be provided.
- At least one complete authentication pair must be provided: `JMS_ACCESS_KEY_ID/JMS_ACCESS_KEY_SECRET` or `JMS_USERNAME/JMS_PASSWORD`.
- `.env` is loaded automatically by the runtime.
- If `.env` is missing or incomplete, you can fill it through natural-language conversation, and the runtime will generate or overwrite the local `.env` after confirmation.
- Before first use, make sure the URL, authentication method, organization, timeout, and TLS settings are complete.
- If you switch the JumpServer instance, account, organization, or `.env` content, rerun full preflight.

## Typical Request Examples

- "Show me the details for the user `Demo-User`."
- "Show me which assets are under the node named `Demo-Node`."
- "Show me which assets are available on the `Linux` platform."
- "Which assets can this user access in the Default organization?"
- "Show me the details of this permission rule, and tell me which users and assets it affects."
- "Who can access this asset?"
- "Query the login audit for the last week."
- "Show me a user's session records and abnormal interruption details."
- "Help me investigate yesterday's high-risk commands and file-transfer audit."
- "Show me usage for a specific day."
- "Show me yesterday's login activity."
- "I want to know who logged in the most last week."
- "Check which assets were most active in early March."
- "Show me the detailed login logs for a specific day."
- "Export detailed command records for a specific day."

These boundaries are especially important:

- Expressions like `which assets can this user access in the Default organization`, `which nodes can this user access`, or `which accounts can this user use on this asset` belong to user effective access scope and should return scope results first.
- Expressions like `why can this user access this asset` or `details of this permission rule` belong to permission explanation or access analysis.
- Expressions like `login status for a day`, `session overview for a day`, or `who had the most activity in a time range` belong to reports or usage analysis.
- Expressions like `login logs for a day`, `command records for a day`, or `details of a specific session` belong to audit investigation.

## Usage Reports and Time-Range Rules

As long as the core request is JumpServer usage-data analysis for a specific day or time range, the workflow prioritizes the template-based report flow. This includes:

- usage reports, daily reports, weekly reports, and monthly reports
- usage situation, usage analysis, usage statistics, usage summary, and usage overview
- audit analysis and "what happened on a day"
- login, session, command, or transfer activity for a specific day
- rankings, TOP lists, "who had the most", or "which assets were most active" for a time range

These requests generate a complete HTML report by default instead of falling back to a free-text summary first. Only when the user explicitly says "do not generate a report", "just analyze it", "give me a quick summary", "only give me the conclusion", or "do not use the template" may the workflow skip the template and return a short analysis.

Time expressions are normalized into explicit time windows first:

- "yesterday" -> previous day `00:00:00 ~ 23:59:59`
- `20260310` -> `2026-03-10 00:00:00 ~ 23:59:59`
- `2026-03-10` / `2026/03/10` / `March 10` style expressions -> that day `00:00:00 ~ 23:59:59`
- "last week" -> previous natural week, Monday `00:00:00 ~ Sunday 23:59:59`
- "this month" -> the first day of the current month `00:00:00` to the current date or month end `23:59:59`

Quick reading guide:

- `a specific day` is only a placeholder concept; users can say `yesterday`, `20260310`, `2026-03-10`, `2026/03/10`, or `March 10`.
- `a time range` is also a placeholder concept; users can say `last week`, `this month`, or a concrete range such as `2026-03-10 to 2026-03-24`.
- Natural-language time expressions are normalized first, and the formal entrypoint ultimately uses `--date`, `--period`, or `--date-from/--date-to`.

Reports are always written to `reports/JumpServer-YYYY-MM-DD.html`. If the request includes command-audit fields, the report applies the predefined command-storage aggregation rules automatically, so users do not need to choose internal collection logic manually.

## Organization Selection and Blocking Rules

- When the user explicitly specifies an organization, execute in that organization.
- For report or usage-analysis requests with no specified organization, or when the user explicitly says "all organizations" or "global organization", default to trying the global organization `00000000-0000-0000-0000-000000000000` first.
- For ordinary query requests with no specified organization, the existing organization rules apply. If the organization cannot be determined safely, the result returns `candidate_orgs` and uses `user_message` / `action_hint` to explicitly require an organization choice before continuing.
- If the current organization is already active but other organizations can still be switched to, the result continues to return `switchable_orgs`, and `org_context_hint` makes it clear which organization currently defines the query scope.
- If the current organization is A and the target object is in B, the workflow does not continue automatically across organizations.

In the following cases, the skill blocks instead of continuing by guesswork:

- configuration or authentication is incomplete
- the organization is unclear and cannot be determined automatically
- the object name is duplicated or the platform is unclear
- query results cross organizations
- the global organization required by the report request is not accessible
- the user tries to bypass the formal entrypoint or skip preflight

Organization-blocking responses also include these structured fields:

- `reason_code=organization_selection_required`
- `user_message`, which explicitly says an organization must be chosen before continuing
- `action_hint`, which provides the safe next command template
- `suggested_commands`, which provides 1-3 copyable follow-up commands
- `candidate_org_count`, which shows how many accessible organization candidates are available
- `org_selection_policy=required_before_query_when_multiple_accessible_orgs`

## Document Map

| File | Purpose |
|---|---|
| [SKILL.md](./SKILL.md) | router skill for high-level intent selection, shared guardrails, and backward compatibility |
| [agents/openai.yaml](./agents/openai.yaml) | skill integration description and default prompt entry |
| [jumpserver-runtime-setup/SKILL.md](./jumpserver-runtime-setup/SKILL.md) | runtime setup, preflight, and org-context child skill |
| [jumpserver-object-query/SKILL.md](./jumpserver-object-query/SKILL.md) | object-query child skill |
| [jumpserver-effective-access/SKILL.md](./jumpserver-effective-access/SKILL.md) | effective-access child skill |
| [jumpserver-permission-analysis/SKILL.md](./jumpserver-permission-analysis/SKILL.md) | permission-analysis child skill |
| [jumpserver-audit-investigation/SKILL.md](./jumpserver-audit-investigation/SKILL.md) | audit-investigation child skill |
| [jumpserver-usage-reporting/SKILL.md](./jumpserver-usage-reporting/SKILL.md) | usage-reporting child skill |
| [jumpserver-governance-inspection/SKILL.md](./jumpserver-governance-inspection/SKILL.md) | governance-inspection child skill |
| [jumpserver-guided-connection/SKILL.md](./jumpserver-guided-connection/SKILL.md) | guided-connection child skill for SSH/RDP/database |
| [references/single-skill-registration.md](./references/single-skill-registration.md) | how to register one child skill at a time |
| [references/routing-playbook.md](./references/routing-playbook.md) | ordinary routing, typical trigger words, blocking rules, and counterexamples |
| [references/report-template-playbook.md](./references/report-template-playbook.md) | template report workflow, organization priority, time-range handling, and report rules |
| [references/runtime.md](./references/runtime.md) | preflight flow, environment variable model, organization selection, and runtime constraints |
| [references/capabilities.md](./references/capabilities.md) | capability catalog and capability descriptions |
| [references/assets.md](./references/assets.md) | query guidance for assets, accounts, users, nodes, platforms, and related objects |
| [references/permissions.md](./references/permissions.md) | query guidance for permissions, ACL, RBAC, and authorization relationships |
| [references/audit.md](./references/audit.md) | audit guidance for login, session, command, file-transfer, and related data |
| [references/diagnose.md](./references/diagnose.md) | connectivity, object resolution, access analysis, system inspection, and governance guidance |
| [references/safety-rules.md](./references/safety-rules.md) | query boundaries, local write exceptions, and blocking rules |
| [references/troubleshooting.md](./references/troubleshooting.md) | common troubleshooting and recovery suggestions |

## Unsupported Scope

- Creating, updating, deleting, or unlocking assets, platforms, nodes, accounts, users, user groups, or organizations.
- Creating, updating, appending, removing, or deleting permissions and their relationships.
- Running business actions while skipping preflight.
- Using temporary SDK or HTTP scripts to bypass the formal entrypoints.
- Bypassing the formal `jms_report.py` entrypoint for report requests and replacing it with ad hoc inline logic.
- Continuing execution by guessing when objects are unclear, organizations are unclear, or the request crosses organizations.
