# Stage06 LarkSuite Skills Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect a project-native Stage06 skills runtime based on the 27 official `larksuite/cli` skills, then make digital employee runs produce auditable skill evidence before real multi-case LLM smoke.

**Architecture:** Add a static Stage06 skill manifest registry, a deterministic-first skill matcher and lightweight runtime integration. Do not add a new database table; store skill evidence in the existing `agent_runs.output_summary` JSON and include selected skill context in live OpenRouter prompts.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x, existing Stage06 service layer, existing LangGraph/OpenRouter runtime, pytest.

## Global Constraints

- Keep this project independent from Feishu/Lark: no Feishu API integration and no Feishu API compatibility.
- Do not copy official `larksuite/cli` `SKILL.md` files into runtime.
- Preserve all 27 official skills in the project-native manifest registry with status flags.
- Activate only the Stage06 core subset first; planned/future/reference skills must be visible but not executable.
- Do not reintroduce Stage05 advertising-operation skills as platform defaults.
- Do not add a DB migration unless `agent_runs.output_summary` cannot hold the required skill evidence.
- Digital employee write/send/destructive actions remain draft/confirmation-gated.
- Real OpenRouter multi-case smoke runs only after deterministic tests pass and the user explicitly confirms the real external call.

---

## File Structure

Create:

- `backend/app/agents/stage06_skills.py`
  - Static project-native skill manifest registry.
  - Stores all 27 adapted skills with `active`, `planned`, `future` or `reference_only` status.
  - Exposes lookup helpers and active-core filtering.

- `backend/app/agents/stage06_skill_matching.py`
  - Deterministic-first matcher.
  - Builds `skill_evidence` for AgentRun output.
  - Does not call LLM.

- `backend/tests/unit/test_stage06_skill_registry.py`
  - Verifies manifest count, all official source skills are represented, active core subset is correct and forbidden Feishu/API/runtime assumptions are absent.

- `backend/tests/unit/test_stage06_skill_matching.py`
  - Verifies common work prompts route to the expected active core skills, unsafe prompts require approval, unsupported future domains stay inactive and evidence shape is stable.

Modify:

- `backend/app/agents/stage06_live_digital_employee.py`
  - Accept optional `skill_evidence`.
  - Include selected skill context and boundaries in the user payload.
  - Keep response schema unchanged.

- `backend/app/services/stage06_digital_employees.py`
  - Build skill evidence for deterministic and live invocations.
  - Include `skill_evidence` in runtime responses and AgentRun `output_summary`.
  - Keep raw records excluded from `_safe_output_summary`.

- `backend/tests/unit/test_stage06_digital_employee_runtime.py`
  - Assert deterministic invocations include skill evidence.

- `backend/tests/unit/test_stage06_live_digital_employee_runtime.py`
  - Assert live OpenRouter requests receive selected skill context without hidden fields.

- `project-docs/08-implementation/STAGE_06_PROGRESS.md`
  - Record implementation progress and verification commands after tasks complete.

- `project-docs/08-implementation/STAGE_06_REMAINING_RISKS_AND_NEXT_CASES.md`
  - Update R6-05 after runtime connection evidence exists.

Do not modify:

- Alembic migrations unless a later task proves JSON output cannot hold evidence.
- Stage05 skills files except for read-only comparison.
- Feishu/Lark API configuration.
- Mini App frontend.

---

### Task 1: Stage06 Static Skill Manifest Registry

**Files:**

- Create: `backend/app/agents/stage06_skills.py`
- Test: `backend/tests/unit/test_stage06_skill_registry.py`

**Interfaces:**

- Produces:
  - `STAGE06_SKILL_MANIFEST_VERSION: str`
  - `Stage06SkillManifest`
  - `get_stage06_skill_registry() -> tuple[Stage06SkillManifest, ...]`
  - `get_stage06_active_skill_registry() -> tuple[Stage06SkillManifest, ...]`
  - `get_stage06_skill_manifest(skill_id: str) -> Stage06SkillManifest`
  - `has_stage06_skill(skill_id: str) -> bool`

- Consumes:
  - No project service dependency.

- [ ] **Step 1: Write the failing registry test**

Create `backend/tests/unit/test_stage06_skill_registry.py`:

```python
from app.agents.stage06_skills import (
    STAGE06_SKILL_MANIFEST_VERSION,
    get_stage06_active_skill_registry,
    get_stage06_skill_manifest,
    get_stage06_skill_registry,
    has_stage06_skill,
)


def test_stage06_skill_registry_preserves_all_27_larksuite_source_skills() -> None:
    registry = get_stage06_skill_registry()

    assert STAGE06_SKILL_MANIFEST_VERSION == "stage06-larksuite-skills-v1"
    assert len(registry) == 27
    assert {skill.source_skill for skill in registry} == {
        "lark-approval",
        "lark-apps",
        "lark-attendance",
        "lark-base",
        "lark-calendar",
        "lark-contact",
        "lark-doc",
        "lark-drive",
        "lark-event",
        "lark-im",
        "lark-mail",
        "lark-markdown",
        "lark-minutes",
        "lark-note",
        "lark-okr",
        "lark-openapi-explorer",
        "lark-shared",
        "lark-sheets",
        "lark-skill-maker",
        "lark-slides",
        "lark-task",
        "lark-vc",
        "lark-vc-agent",
        "lark-whiteboard",
        "lark-wiki",
        "lark-workflow-meeting-summary",
        "lark-workflow-standup-report",
    }


def test_stage06_active_core_skill_subset_is_generic_platform_first() -> None:
    active_ids = {skill.skill_id for skill in get_stage06_active_skill_registry()}

    assert active_ids == {
        "platform-approval",
        "platform-base",
        "platform-contact",
        "platform-event",
        "platform-file-import",
        "platform-shared-policy",
        "platform-skill-maker",
        "platform-tabular-analysis",
        "platform-task",
        "platform-telegram-im",
        "platform-tool-discovery",
    }
    assert "recharge-draft" not in active_ids
    assert "bm-invite-draft" not in active_ids
    assert "card-binding-draft" not in active_ids


def test_stage06_skill_manifest_keeps_project_native_boundaries() -> None:
    base = get_stage06_skill_manifest("platform-base")
    shared = get_stage06_skill_manifest("platform-shared-policy")
    live_meeting = get_stage06_skill_manifest("platform-live-meeting-agent-reference")

    assert base.status == "active"
    assert base.source_skill == "lark-base"
    assert "workspace" in base.required_context
    assert "raw_sql" in base.forbidden_actions
    assert "feishu_api_call" in base.forbidden_actions
    assert shared.confirmation_policy == "required_for_write_send_destructive"
    assert live_meeting.status == "reference_only"
    assert has_stage06_skill("platform-base") is True
    assert has_stage06_skill("recharge-draft") is False
```

- [ ] **Step 2: Run registry test to verify it fails**

Run:

```powershell
cd backend
pytest tests/unit/test_stage06_skill_registry.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'app.agents.stage06_skills'`.

- [ ] **Step 3: Implement the registry**

Create `backend/app/agents/stage06_skills.py` with:

```python
from dataclasses import dataclass
from typing import Literal


STAGE06_SKILL_MANIFEST_VERSION = "stage06-larksuite-skills-v1"

SkillStatus = Literal["active", "planned", "future", "reference_only"]


@dataclass(frozen=True)
class Stage06SkillManifest:
    skill_id: str
    source_skill: str
    status: SkillStatus
    layer: str
    name: str
    description: str
    when_to_use: tuple[str, ...]
    not_for: tuple[str, ...]
    resource_patterns: tuple[str, ...]
    positive_triggers: tuple[str, ...]
    negative_triggers: tuple[str, ...]
    required_context: tuple[str, ...]
    optional_context: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    output_contract: str
    confirmation_policy: str
    fallback: str


_COMMON_FORBIDDEN = (
    "raw_sql",
    "feishu_api_call",
    "lark_cli_runtime_call",
    "direct_telegram_send",
    "self_confirmation",
    "secret_access",
)


_REGISTRY: tuple[Stage06SkillManifest, ...] = (
    Stage06SkillManifest(
        skill_id="platform-approval",
        source_skill="lark-approval",
        status="active",
        layer="L3 Work Object",
        name="Approval And Confirmation",
        description="Use for draft review, confirmation, rejection, approval queue and escalation flows.",
        when_to_use=("approve", "confirm", "reject", "approval", "pending confirmation", "审批", "确认"),
        not_for=("ordinary task management", "self approval", "approval definition builder"),
        resource_patterns=("draft_id", "record_change_draft", "approval"),
        positive_triggers=("approve", "confirm", "reject", "approval", "pending", "确认", "审批"),
        negative_triggers=("skip approval", "self approve", "直接执行"),
        required_context=("actor_user_id",),
        optional_context=("draft_id", "record_id", "base_id"),
        allowed_actions=("record_change_draft.review", "record_change_draft.confirmation_request"),
        forbidden_actions=_COMMON_FORBIDDEN + ("agent_self_approval",),
        output_contract="approval_decision_or_pending_draft",
        confirmation_policy="required_for_write_send_destructive",
        fallback="manual_review",
    ),
    Stage06SkillManifest(
        skill_id="platform-app-ops-reference",
        source_skill="lark-apps",
        status="reference_only",
        layer="L0 Governance and Policy",
        name="Application Operations Reference",
        description="Reference for release, hosting, logs and environment guardrails; not a Stage06 executable skill.",
        when_to_use=("deploy app", "release", "logs", "metrics", "environment variable"),
        not_for=("project runtime execution", "Mini App implementation"),
        resource_patterns=("deployment", "env", "log"),
        positive_triggers=("deploy", "release", "上线", "日志", "env"),
        negative_triggers=("upload drive file", "edit doc", "create slides"),
        required_context=(),
        optional_context=("deployment_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN + ("miaoda_runtime_call",),
        output_contract="reference_only",
        confirmation_policy="not_executable",
        fallback="reference_only",
    ),
    Stage06SkillManifest(
        skill_id="template-attendance",
        source_skill="lark-attendance",
        status="future",
        layer="L3 Work Object",
        name="Attendance Template",
        description="Future HR/timekeeping template for attendance-like records.",
        when_to_use=("attendance", "check-in", "打卡", "考勤"),
        not_for=("current Stage06 core runtime",),
        resource_patterns=("attendance", "check_in"),
        positive_triggers=("attendance", "check-in", "考勤", "打卡"),
        negative_triggers=("time zone conversion",),
        required_context=("workspace_id",),
        optional_context=("user_id", "date_range"),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN,
        output_contract="future_template",
        confirmation_policy="not_executable",
        fallback="future_scope",
    ),
    Stage06SkillManifest(
        skill_id="platform-base",
        source_skill="lark-base",
        status="active",
        layer="L2 Workspace Resource",
        name="Multidimensional Base",
        description="Use for workspace, base, table, field, record, view, form-lite, dashboard-lite and permission-scoped Base operations.",
        when_to_use=("base", "table", "field", "record", "view", "form", "dashboard", "workflow", "多维表格", "表"),
        not_for=("file import itself", "raw spreadsheet cell editing", "Feishu API compatibility"),
        resource_patterns=("workspace_id", "base_id", "table_id", "view_id", "record_id"),
        positive_triggers=("base", "table", "record", "field", "view", "schema", "多维表格", "记录", "字段"),
        negative_triggers=("raw sql", "provider write", "Feishu API"),
        required_context=("workspace",),
        optional_context=("base_id", "table_id", "view_id", "record_id"),
        allowed_actions=("schema.inspect", "record.query", "record_change_draft.create"),
        forbidden_actions=_COMMON_FORBIDDEN + ("direct_record_commit_without_confirmation",),
        output_contract="table_resource_answer_or_draft",
        confirmation_policy="draft_required_for_write",
        fallback="ask_for_missing_context",
    ),
    Stage06SkillManifest(
        skill_id="platform-calendar",
        source_skill="lark-calendar",
        status="planned",
        layer="L3 Work Object",
        name="Calendar",
        description="Planned generic scheduling skill for calendar-like tables and future event resources.",
        when_to_use=("calendar", "schedule", "meeting room", "busy", "free", "日程", "会议"),
        not_for=("historical video meeting artifacts", "ordinary tasks"),
        resource_patterns=("calendar", "event", "meeting"),
        positive_triggers=("calendar", "schedule", "meeting", "日程", "会议"),
        negative_triggers=("meeting transcript", "task list"),
        required_context=("workspace_id",),
        optional_context=("date_range", "assignee_id"),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN,
        output_contract="planned_calendar_action",
        confirmation_policy="not_executable",
        fallback="planned_skill",
    ),
    Stage06SkillManifest(
        skill_id="platform-contact",
        source_skill="lark-contact",
        status="active",
        layer="L1 Channel and Event",
        name="Contact Resolution",
        description="Use for resolving Telegram users, workspace members, customer contacts and assignees.",
        when_to_use=("contact", "assignee", "email", "member", "user", "联系人", "负责人"),
        not_for=("using contact as permission", "unrestricted member enumeration"),
        resource_patterns=("actor_user_id", "telegram_user_id", "email", "member_id"),
        positive_triggers=("contact", "email", "assignee", "member", "user", "负责人", "联系人"),
        negative_triggers=("permission by email", "list every user"),
        required_context=("workspace_id",),
        optional_context=("telegram_user_id", "email", "member_id"),
        allowed_actions=("member.resolve", "contact.resolve"),
        forbidden_actions=_COMMON_FORBIDDEN + ("treat_contact_as_permission",),
        output_contract="resolved_contact_or_clarification",
        confirmation_policy="read_only",
        fallback="ask_for_missing_context",
    ),
    Stage06SkillManifest(
        skill_id="platform-doc",
        source_skill="lark-doc",
        status="planned",
        layer="L2 Workspace Resource",
        name="Document",
        description="Planned skill for SOPs, notes and generated documents.",
        when_to_use=("document", "doc", "SOP", "note", "文档"),
        not_for=("table record operation", "spreadsheet values", "document comments"),
        resource_patterns=("document_id", "doc_id"),
        positive_triggers=("document", "doc", "SOP", "文档", "说明"),
        negative_triggers=("table record", "spreadsheet formula"),
        required_context=("workspace_id",),
        optional_context=("document_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN,
        output_contract="planned_document_action",
        confirmation_policy="not_executable",
        fallback="planned_skill",
    ),
    Stage06SkillManifest(
        skill_id="platform-file-import",
        source_skill="lark-drive",
        status="active",
        layer="L2 Workspace Resource",
        name="File Import",
        description="Use for CSV/Excel import, attachment metadata and future file-resource handling.",
        when_to_use=("import", "upload", "file", "CSV", "Excel", "attachment", "导入", "附件"),
        not_for=("editing document body", "cloud drive parity"),
        resource_patterns=(".csv", ".xlsx", "attachment", "file_id"),
        positive_triggers=("import", "upload", "file", "csv", "excel", "导入", "附件"),
        negative_triggers=("edit document body", "move cloud folder"),
        required_context=("workspace_id",),
        optional_context=("base_id", "file_id", "filename"),
        allowed_actions=("import.preview", "import.commit", "template.save"),
        forbidden_actions=_COMMON_FORBIDDEN + ("unsafe_file_execute",),
        output_contract="import_preview_or_missing_file",
        confirmation_policy="confirmation_required_for_import_commit",
        fallback="ask_for_file",
    ),
    Stage06SkillManifest(
        skill_id="platform-event",
        source_skill="lark-event",
        status="active",
        layer="L1 Channel and Event",
        name="Event Intake",
        description="Use for Telegram webhook/polling, bounded subscribers, queue events and smoke evidence.",
        when_to_use=("event", "webhook", "polling", "queue", "worker", "事件"),
        not_for=("unbounded polling", "business decision itself"),
        resource_patterns=("telegram_update_id", "event_id", "trace_id"),
        positive_triggers=("event", "webhook", "poll", "queue", "worker", "事件"),
        negative_triggers=("infinite polling", "unsafe retry"),
        required_context=(),
        optional_context=("telegram_update_id", "trace_id"),
        allowed_actions=("event.consume_bounded", "event.record_evidence"),
        forbidden_actions=_COMMON_FORBIDDEN + ("unbounded_polling",),
        output_contract="bounded_event_evidence",
        confirmation_policy="read_only",
        fallback="manual_review",
    ),
    Stage06SkillManifest(
        skill_id="platform-telegram-im",
        source_skill="lark-im",
        status="active",
        layer="L1 Channel and Event",
        name="Telegram IM",
        description="Use for Telegram messages, mentions, chats, inline buttons, files and reply drafts.",
        when_to_use=("telegram", "message", "chat", "reply", "send", "mention", "消息", "群"),
        not_for=("direct send without confirmation", "Feishu IM"),
        resource_patterns=("telegram_chat_id", "telegram_user_id", "message_id"),
        positive_triggers=("telegram", "message", "chat", "reply", "send", "mention", "消息", "回复"),
        negative_triggers=("send now without confirmation", "broad group send"),
        required_context=("telegram_chat_id",),
        optional_context=("telegram_user_id", "message_id", "alias"),
        allowed_actions=("telegram.message.read", "notification_request.create"),
        forbidden_actions=_COMMON_FORBIDDEN + ("broad_group_send", "send_without_confirmation"),
        output_contract="telegram_answer_or_send_draft",
        confirmation_policy="draft_required_for_send",
        fallback="manual_review",
    ),
    Stage06SkillManifest(
        skill_id="platform-mail",
        source_skill="lark-mail",
        status="planned",
        layer="L1 Channel and Event",
        name="Mail",
        description="Planned email channel adapter. Mail content is untrusted external input.",
        when_to_use=("mail", "email", "邮件"),
        not_for=("Telegram chat", "pure contact lookup"),
        resource_patterns=("email_message_id", "mailbox"),
        positive_triggers=("mail", "email", "邮件"),
        negative_triggers=("telegram", "calendar"),
        required_context=("workspace_id",),
        optional_context=("email_message_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN + ("trust_external_mail_content"),
        output_contract="planned_mail_action",
        confirmation_policy="not_executable",
        fallback="planned_skill",
    ),
    Stage06SkillManifest(
        skill_id="platform-markdown-doc",
        source_skill="lark-markdown",
        status="planned",
        layer="L2 Workspace Resource",
        name="Markdown Document",
        description="Planned skill for Markdown snippets, docs and diff-style edits.",
        when_to_use=("markdown", "md", "diff", "patch"),
        not_for=("cloud file search", "table records"),
        resource_patterns=(".md", "markdown"),
        positive_triggers=("markdown", "md", "patch", "diff"),
        negative_triggers=("table", "cloud permission"),
        required_context=("workspace_id",),
        optional_context=("document_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN,
        output_contract="planned_markdown_action",
        confirmation_policy="not_executable",
        fallback="planned_skill",
    ),
    Stage06SkillManifest(
        skill_id="platform-minutes",
        source_skill="lark-minutes",
        status="future",
        layer="L2 Workspace Resource",
        name="Minutes",
        description="Future meeting-knowledge artifact skill.",
        when_to_use=("minutes", "transcript", "recording", "妙记", "逐字稿"),
        not_for=("current Stage06 table runtime",),
        resource_patterns=("minute_id", "transcript"),
        positive_triggers=("minutes", "transcript", "recording", "妙记", "逐字稿"),
        negative_triggers=("table summary",),
        required_context=("workspace_id",),
        optional_context=("minute_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN,
        output_contract="future_minutes_action",
        confirmation_policy="not_executable",
        fallback="future_scope",
    ),
    Stage06SkillManifest(
        skill_id="platform-note",
        source_skill="lark-note",
        status="future",
        layer="L2 Workspace Resource",
        name="Meeting Note",
        description="Future known-note lookup skill.",
        when_to_use=("note id", "meeting note", "纪要"),
        not_for=("generic table note field", "document title search"),
        resource_patterns=("note_id",),
        positive_triggers=("note", "纪要"),
        negative_triggers=("table note",),
        required_context=("workspace_id",),
        optional_context=("note_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN,
        output_contract="future_note_action",
        confirmation_policy="not_executable",
        fallback="future_scope",
    ),
    Stage06SkillManifest(
        skill_id="template-okr",
        source_skill="lark-okr",
        status="future",
        layer="L3 Work Object",
        name="OKR Template",
        description="Future OKR template built from tables, tasks and progress records.",
        when_to_use=("okr", "objective", "key result", "目标", "关键结果"),
        not_for=("performance evaluation",),
        resource_patterns=("okr", "objective"),
        positive_triggers=("okr", "objective", "key result", "目标"),
        negative_triggers=("performance review",),
        required_context=("workspace_id",),
        optional_context=("cycle_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN,
        output_contract="future_template",
        confirmation_policy="not_executable",
        fallback="future_scope",
    ),
    Stage06SkillManifest(
        skill_id="platform-tool-discovery",
        source_skill="lark-openapi-explorer",
        status="active",
        layer="L0 Governance and Policy",
        name="Tool Discovery",
        description="Use for project Tool Gateway discovery, service schema introspection and missing-tool reporting.",
        when_to_use=("tool", "capability", "unsupported", "discover", "工具", "能力"),
        not_for=("Feishu OpenAPI discovery", "raw external API call"),
        resource_patterns=("tool_name", "capability"),
        positive_triggers=("tool", "capability", "unsupported", "discover", "能力", "工具"),
        negative_triggers=("call Feishu API", "raw API now"),
        required_context=(),
        optional_context=("requested_capability",),
        allowed_actions=("tool_catalog.inspect", "missing_tool.report"),
        forbidden_actions=_COMMON_FORBIDDEN + ("raw_external_api_call",),
        output_contract="tool_capability_report",
        confirmation_policy="read_only",
        fallback="manual_review",
    ),
    Stage06SkillManifest(
        skill_id="platform-shared-policy",
        source_skill="lark-shared",
        status="active",
        layer="L0 Governance and Policy",
        name="Shared Policy",
        description="Use for identity, permissions, scope intersection, JSON/error contract, confirmation and high-risk gates.",
        when_to_use=("permission", "scope", "policy", "identity", "confirmation", "权限", "范围"),
        not_for=("business answer by itself",),
        resource_patterns=("actor_user_id", "role", "scope_policy"),
        positive_triggers=("permission", "scope", "policy", "identity", "confirmation", "权限", "确认"),
        negative_triggers=("bypass permission", "ignore scope"),
        required_context=("actor_user_id",),
        optional_context=("role", "telegram_chat_id", "digital_employee_id"),
        allowed_actions=("permission.evaluate", "audit.record", "policy.deny"),
        forbidden_actions=_COMMON_FORBIDDEN + ("privilege_escalation",),
        output_contract="policy_decision_or_guardrail",
        confirmation_policy="required_for_write_send_destructive",
        fallback="manual_review",
    ),
    Stage06SkillManifest(
        skill_id="platform-tabular-analysis",
        source_skill="lark-sheets",
        status="active",
        layer="L2 Workspace Resource",
        name="Tabular Analysis",
        description="Use for table analysis, summaries, totals, formula-like reasoning and dashboard-lite planning over visible data.",
        when_to_use=("summarize", "analyze", "total", "formula", "chart", "统计", "分析", "汇总"),
        not_for=("full spreadsheet parity", "hidden fields", "raw SQL"),
        resource_patterns=("table_id", "view_id", "field_key"),
        positive_triggers=("summarize", "analyze", "total", "formula", "chart", "统计", "分析", "汇总"),
        negative_triggers=("raw sql", "hidden field"),
        required_context=("view_id",),
        optional_context=("table_id", "field_key", "date_range"),
        allowed_actions=("record.query", "table.summarize", "statistics.preview"),
        forbidden_actions=_COMMON_FORBIDDEN + ("invent_fact", "read_hidden_field"),
        output_contract="analysis_answer_with_citations",
        confirmation_policy="read_only",
        fallback="ask_for_missing_context",
    ),
    Stage06SkillManifest(
        skill_id="platform-skill-maker",
        source_skill="lark-skill-maker",
        status="active",
        layer="L0 Governance and Policy",
        name="Skill Maker",
        description="Use for authoring, validating and testing future project-native skill manifests.",
        when_to_use=("skill", "manifest", "registry", "capability", "技能"),
        not_for=("runtime user-installed arbitrary skills",),
        resource_patterns=("skill_id", "manifest_version"),
        positive_triggers=("skill", "manifest", "registry", "capability", "技能"),
        negative_triggers=("install arbitrary code",),
        required_context=(),
        optional_context=("skill_id",),
        allowed_actions=("skill_manifest.validate", "skill_fixture.generate"),
        forbidden_actions=_COMMON_FORBIDDEN + ("dynamic_skill_install",),
        output_contract="skill_manifest_review",
        confirmation_policy="read_only",
        fallback="manual_review",
    ),
    Stage06SkillManifest(
        skill_id="platform-slides-export",
        source_skill="lark-slides",
        status="future",
        layer="L2 Workspace Resource",
        name="Slides Export",
        description="Future report export skill for slide-like artifacts.",
        when_to_use=("slides", "presentation", "deck", "幻灯片"),
        not_for=("current Stage06 runtime",),
        resource_patterns=("slide_id",),
        positive_triggers=("slides", "presentation", "deck", "幻灯片"),
        negative_triggers=("table edit",),
        required_context=("workspace_id",),
        optional_context=("base_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN,
        output_contract="future_export_action",
        confirmation_policy="not_executable",
        fallback="future_scope",
    ),
    Stage06SkillManifest(
        skill_id="platform-task",
        source_skill="lark-task",
        status="active",
        layer="L3 Work Object",
        name="Task And Work Item",
        description="Use for work items, follow-ups, assignments, queues and digital employee task logs.",
        when_to_use=("task", "todo", "follow up", "assign", "待办", "任务", "跟进"),
        not_for=("approval task", "table schema operation"),
        resource_patterns=("task_id", "assignee_id", "record_id"),
        positive_triggers=("task", "todo", "follow up", "assign", "待办", "任务", "跟进"),
        negative_triggers=("approval instance", "schema"),
        required_context=("workspace_id",),
        optional_context=("record_id", "assignee_id", "due_date"),
        allowed_actions=("task.create_draft", "task.query", "work_item.update_draft"),
        forbidden_actions=_COMMON_FORBIDDEN + ("auto_assign_without_permission",),
        output_contract="task_answer_or_draft",
        confirmation_policy="draft_required_for_write",
        fallback="ask_for_missing_context",
    ),
    Stage06SkillManifest(
        skill_id="platform-meeting-history",
        source_skill="lark-vc",
        status="future",
        layer="L2 Workspace Resource",
        name="Meeting History",
        description="Future historical meeting artifact skill.",
        when_to_use=("video meeting", "meeting history", "recording", "会议记录"),
        not_for=("future schedule", "active meeting join"),
        resource_patterns=("meeting_id",),
        positive_triggers=("meeting history", "recording", "会议记录"),
        negative_triggers=("join meeting now",),
        required_context=("workspace_id",),
        optional_context=("meeting_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN,
        output_contract="future_meeting_history_action",
        confirmation_policy="not_executable",
        fallback="future_scope",
    ),
    Stage06SkillManifest(
        skill_id="platform-live-meeting-agent-reference",
        source_skill="lark-vc-agent",
        status="reference_only",
        layer="L5 Live Agent Runtime",
        name="Live Meeting Agent Reference",
        description="Reference for high-risk live meeting participation; not executable in Stage06.",
        when_to_use=("join meeting", "active meeting", "live meeting"),
        not_for=("Telegram-first table workflows", "Stage06 active runtime"),
        resource_patterns=("active_meeting_id",),
        positive_triggers=("join meeting", "active meeting"),
        negative_triggers=("meeting history",),
        required_context=("workspace_id",),
        optional_context=("meeting_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN + ("join_live_meeting"),
        output_contract="reference_only",
        confirmation_policy="not_executable",
        fallback="reference_only",
    ),
    Stage06SkillManifest(
        skill_id="platform-diagram-board",
        source_skill="lark-whiteboard",
        status="future",
        layer="L2 Workspace Resource",
        name="Diagram Board",
        description="Future visual diagram/whiteboard skill.",
        when_to_use=("whiteboard", "diagram", "flowchart", "画板", "流程图"),
        not_for=("current Stage06 runtime",),
        resource_patterns=("board_id", "diagram"),
        positive_triggers=("whiteboard", "diagram", "flowchart", "画板", "流程图"),
        negative_triggers=("table record"),
        required_context=("workspace_id",),
        optional_context=("board_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN,
        output_contract="future_diagram_action",
        confirmation_policy="not_executable",
        fallback="future_scope",
    ),
    Stage06SkillManifest(
        skill_id="platform-knowledge-space",
        source_skill="lark-wiki",
        status="planned",
        layer="L2 Workspace Resource",
        name="Knowledge Space",
        description="Planned SOP and knowledge-space organization skill.",
        when_to_use=("wiki", "knowledge", "SOP", "知识库"),
        not_for=("table record editing", "file upload itself"),
        resource_patterns=("knowledge_space_id", "wiki_node_id"),
        positive_triggers=("wiki", "knowledge", "SOP", "知识库"),
        negative_triggers=("table edit", "file upload"),
        required_context=("workspace_id",),
        optional_context=("knowledge_space_id",),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN,
        output_contract="planned_knowledge_action",
        confirmation_policy="not_executable",
        fallback="planned_skill",
    ),
    Stage06SkillManifest(
        skill_id="workflow-period-summary",
        source_skill="lark-workflow-meeting-summary",
        status="planned",
        layer="L4 Workflow Composition",
        name="Period Summary Workflow",
        description="Planned workflow that summarizes tables, tasks and messages over a time range.",
        when_to_use=("weekly summary", "monthly summary", "period summary", "周报", "月报"),
        not_for=("meeting-only assumption", "invented facts"),
        resource_patterns=("date_range", "view_id"),
        positive_triggers=("weekly", "monthly", "period summary", "周报", "月报"),
        negative_triggers=("send report now"),
        required_context=("workspace_id",),
        optional_context=("date_range", "view_id"),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN + ("invent_fact"),
        output_contract="planned_workflow_summary",
        confirmation_policy="not_executable",
        fallback="planned_skill",
    ),
    Stage06SkillManifest(
        skill_id="workflow-daily-briefing",
        source_skill="lark-workflow-standup-report",
        status="planned",
        layer="L4 Workflow Composition",
        name="Daily Briefing Workflow",
        description="Planned workflow for daily tasks, records and Telegram mentions.",
        when_to_use=("daily briefing", "today summary", "standup", "日报", "今日"),
        not_for=("broad customer send",),
        resource_patterns=("date", "view_id", "task_id"),
        positive_triggers=("daily", "today", "standup", "日报", "今日"),
        negative_triggers=("send to everyone"),
        required_context=("workspace_id",),
        optional_context=("date", "view_id"),
        allowed_actions=(),
        forbidden_actions=_COMMON_FORBIDDEN + ("broad_group_send"),
        output_contract="planned_daily_briefing",
        confirmation_policy="not_executable",
        fallback="planned_skill",
    ),
)

_REGISTRY_BY_ID = {skill.skill_id: skill for skill in _REGISTRY}


def get_stage06_skill_registry() -> tuple[Stage06SkillManifest, ...]:
    return _REGISTRY


def get_stage06_active_skill_registry() -> tuple[Stage06SkillManifest, ...]:
    return tuple(skill for skill in _REGISTRY if skill.status == "active")


def get_stage06_skill_manifest(skill_id: str) -> Stage06SkillManifest:
    return _REGISTRY_BY_ID[skill_id]


def has_stage06_skill(skill_id: str) -> bool:
    return skill_id in _REGISTRY_BY_ID


__all__ = [
    "STAGE06_SKILL_MANIFEST_VERSION",
    "Stage06SkillManifest",
    "get_stage06_active_skill_registry",
    "get_stage06_skill_manifest",
    "get_stage06_skill_registry",
    "has_stage06_skill",
]
```

- [ ] **Step 4: Run registry test to verify it passes**

Run:

```powershell
cd backend
pytest tests/unit/test_stage06_skill_registry.py -q
```

Expected: `3 passed`.

---

### Task 2: Deterministic Skill Matcher

**Files:**

- Create: `backend/app/agents/stage06_skill_matching.py`
- Test: `backend/tests/unit/test_stage06_skill_matching.py`

**Interfaces:**

- Consumes:
  - `Stage06SkillManifest`
  - `get_stage06_active_skill_registry`
  - `get_stage06_skill_manifest`

- Produces:
  - `Stage06SkillMatchContext`
  - `build_stage06_skill_evidence(*, action: str, source_text: str | None, source_context: dict[str, object] | None = None) -> dict[str, object]`

- [ ] **Step 1: Write failing matcher tests**

Create `backend/tests/unit/test_stage06_skill_matching.py`:

```python
from app.agents.stage06_skill_matching import (
    Stage06SkillMatchContext,
    build_stage06_skill_evidence,
)


def test_stage06_skill_matching_routes_summarize_to_base_and_tabular_analysis() -> None:
    evidence = build_stage06_skill_evidence(
        action="summarize",
        source_text="请总结这个客户表里今天需要跟进的记录",
        source_context={"view_id": "view-1", "telegram_chat_id": "chat-1"},
    )

    selected = _selected_ids(evidence)

    assert evidence["manifest_version"] == "stage06-larksuite-skills-v1"
    assert evidence["mode"] == "deterministic_manifest_matching"
    assert "platform-shared-policy" in selected
    assert "platform-telegram-im" in selected
    assert "platform-base" in selected
    assert "platform-tabular-analysis" in selected
    assert evidence["requires_confirmation"] is False
    assert evidence["baseline_metrics"]["selected_count"] >= 4


def test_stage06_skill_matching_routes_draft_update_to_approval() -> None:
    evidence = build_stage06_skill_evidence(
        action="draft_update",
        source_text="把这条任务状态改成处理中，但先生成草稿",
        source_context={"record_id": "rec-1", "view_id": "view-1"},
    )

    selected = _selected_ids(evidence)

    assert "platform-base" in selected
    assert "platform-approval" in selected
    assert evidence["requires_confirmation"] is True
    assert evidence["fallback"] == "draft_confirmation"


def test_stage06_skill_matching_keeps_future_and_reference_skills_inactive() -> None:
    evidence = build_stage06_skill_evidence(
        action="summarize",
        source_text="让机器人加入正在进行的视频会议并实时发言",
        source_context={"workspace_id": "wrk-1"},
    )

    selected = _selected_ids(evidence)
    inactive = {item["skill_id"] for item in evidence["inactive_candidates"]}

    assert "platform-live-meeting-agent-reference" in inactive
    assert "platform-live-meeting-agent-reference" not in selected
    assert evidence["fallback"] == "manual_review"


def test_stage06_skill_matching_reports_missing_context() -> None:
    evidence = build_stage06_skill_evidence(
        action="summarize",
        source_text="总结这个表",
        source_context={},
    )

    missing = {(item["skill_id"], item["context_key"]) for item in evidence["missing_context"]}

    assert ("platform-tabular-analysis", "view_id") in missing
    assert evidence["requires_clarification"] is True


def test_stage06_skill_match_context_normalizes_none_values() -> None:
    context = Stage06SkillMatchContext.from_values(
        action="query",
        source_text=None,
        source_context=None,
    )

    assert context.action == "query"
    assert context.source_text == ""
    assert context.source_context == {}


def _selected_ids(evidence: dict[str, object]) -> set[str]:
    return {str(item["skill_id"]) for item in evidence["selected_skills"]}
```

- [ ] **Step 2: Run matcher tests to verify they fail**

Run:

```powershell
cd backend
pytest tests/unit/test_stage06_skill_matching.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'app.agents.stage06_skill_matching'`.

- [ ] **Step 3: Implement deterministic matcher**

Create `backend/app/agents/stage06_skill_matching.py`:

```python
from dataclasses import dataclass
from typing import Any

from app.agents.stage06_skills import (
    STAGE06_SKILL_MANIFEST_VERSION,
    Stage06SkillManifest,
    get_stage06_active_skill_registry,
    get_stage06_skill_registry,
)


WRITE_LIKE_ACTIONS = frozenset({"draft_create", "draft_update", "status_advance"})


@dataclass(frozen=True)
class Stage06SkillMatchContext:
    action: str
    source_text: str
    source_context: dict[str, object]

    @classmethod
    def from_values(
        cls,
        *,
        action: str,
        source_text: str | None,
        source_context: dict[str, object] | None,
    ) -> "Stage06SkillMatchContext":
        return cls(
            action=action,
            source_text=source_text or "",
            source_context=dict(source_context or {}),
        )


def build_stage06_skill_evidence(
    *,
    action: str,
    source_text: str | None,
    source_context: dict[str, object] | None = None,
) -> dict[str, object]:
    context = Stage06SkillMatchContext.from_values(
        action=action,
        source_text=source_text,
        source_context=source_context,
    )
    selected: list[dict[str, object]] = []
    inactive: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    missing_context: list[dict[str, object]] = []

    active_skills = get_stage06_active_skill_registry()
    all_skills = get_stage06_skill_registry()

    for skill in active_skills:
        if _is_foundation_skill(skill) or _skill_matches_context(skill, context):
            _append_unique(selected, _match_item(skill, context, "selected"))

    for skill in all_skills:
        if skill.status != "active" and _skill_matches_context(skill, context):
            inactive.append(_match_item(skill, context, skill.status))

    _ensure_action_defaults(selected, context)
    _append_missing_context(selected, context, missing_context)

    for item in list(selected):
        skill_id = str(item["skill_id"])
        if _has_negative_trigger(skill_id, context):
            selected.remove(item)
            rejected.append({**item, "selection": "rejected_by_negative_trigger"})

    requires_confirmation = context.action in WRITE_LIKE_ACTIONS or any(
        str(item["skill_id"]) in {"platform-approval", "platform-telegram-im"}
        and _looks_write_like(context)
        for item in selected
    )
    requires_clarification = bool(missing_context)
    fallback = _fallback(
        selected=selected,
        inactive=inactive,
        requires_confirmation=requires_confirmation,
        requires_clarification=requires_clarification,
    )
    return {
        "manifest_version": STAGE06_SKILL_MANIFEST_VERSION,
        "mode": "deterministic_manifest_matching",
        "source": "action_text_context",
        "candidate_skills": selected + inactive + rejected,
        "selected_skills": selected,
        "inactive_candidates": inactive,
        "rejected_skills": rejected,
        "missing_context": missing_context,
        "requires_confirmation": requires_confirmation,
        "requires_clarification": requires_clarification,
        "fallback": fallback,
        "baseline_metrics": {
            "candidate_count": len(selected) + len(inactive) + len(rejected),
            "selected_count": len(selected),
            "inactive_count": len(inactive),
            "rejected_count": len(rejected),
            "missing_context_count": len(missing_context),
            "selected_skill_ids": [str(item["skill_id"]) for item in selected],
        },
    }


def _is_foundation_skill(skill: Stage06SkillManifest) -> bool:
    return skill.skill_id in {"platform-shared-policy"}


def _skill_matches_context(
    skill: Stage06SkillManifest,
    context: Stage06SkillMatchContext,
) -> bool:
    text = _lowered_text(context)
    if any(trigger.lower() in text for trigger in skill.negative_triggers):
        return False
    if any(trigger.lower() in text for trigger in skill.positive_triggers):
        return True
    if any(pattern in context.source_context for pattern in skill.resource_patterns):
        return True
    if skill.skill_id == "platform-telegram-im" and "telegram_chat_id" in context.source_context:
        return True
    return False


def _ensure_action_defaults(
    selected: list[dict[str, object]],
    context: Stage06SkillMatchContext,
) -> None:
    selected_ids = {str(item["skill_id"]) for item in selected}
    active_by_id = {skill.skill_id: skill for skill in get_stage06_active_skill_registry()}
    if context.action in {"query", "summarize"}:
        for skill_id in ("platform-base", "platform-tabular-analysis"):
            if skill_id not in selected_ids:
                _append_unique(selected, _match_item(active_by_id[skill_id], context, "selected"))
    if context.action in WRITE_LIKE_ACTIONS:
        for skill_id in ("platform-base", "platform-approval"):
            if skill_id not in selected_ids:
                _append_unique(selected, _match_item(active_by_id[skill_id], context, "selected"))


def _append_missing_context(
    selected: list[dict[str, object]],
    context: Stage06SkillMatchContext,
    missing_context: list[dict[str, object]],
) -> None:
    context_keys = set(context.source_context)
    for item in selected:
        required = item.get("required_context", ())
        if not isinstance(required, tuple):
            continue
        for key in required:
            if key == "workspace":
                if not {"workspace", "workspace_id", "base_id", "table_id", "view_id", "record_id"} & context_keys:
                    missing_context.append({"skill_id": item["skill_id"], "context_key": key})
            elif key not in context_keys:
                missing_context.append({"skill_id": item["skill_id"], "context_key": key})


def _has_negative_trigger(skill_id: str, context: Stage06SkillMatchContext) -> bool:
    text = _lowered_text(context)
    active_by_id = {skill.skill_id: skill for skill in get_stage06_active_skill_registry()}
    skill = active_by_id.get(skill_id)
    return bool(skill and any(trigger.lower() in text for trigger in skill.negative_triggers))


def _looks_write_like(context: Stage06SkillMatchContext) -> bool:
    text = _lowered_text(context)
    return any(token in text for token in ("send", "发送", "update", "改成", "确认", "approve"))


def _match_item(
    skill: Stage06SkillManifest,
    context: Stage06SkillMatchContext,
    selection: str,
) -> dict[str, object]:
    return {
        "skill_id": skill.skill_id,
        "source_skill": skill.source_skill,
        "status": skill.status,
        "layer": skill.layer,
        "confidence": _confidence(skill, context),
        "selection": selection,
        "reason": "matched_stage06_manifest_triggers_or_context",
        "fallback": skill.fallback,
        "required_context": skill.required_context,
        "confirmation_policy": skill.confirmation_policy,
        "output_contract": skill.output_contract,
    }


def _confidence(skill: Stage06SkillManifest, context: Stage06SkillMatchContext) -> str:
    text = _lowered_text(context)
    if any(trigger.lower() in text for trigger in skill.positive_triggers):
        return "0.90"
    if any(pattern in context.source_context for pattern in skill.resource_patterns):
        return "0.80"
    if _is_foundation_skill(skill):
        return "0.75"
    return "0.65"


def _fallback(
    *,
    selected: list[dict[str, object]],
    inactive: list[dict[str, object]],
    requires_confirmation: bool,
    requires_clarification: bool,
) -> str:
    if requires_clarification:
        return "ask_for_missing_context"
    if requires_confirmation:
        return "draft_confirmation"
    if inactive and len(selected) <= 1:
        return "manual_review"
    return "none"


def _append_unique(items: list[dict[str, object]], item: dict[str, object]) -> None:
    if str(item["skill_id"]) not in {str(existing["skill_id"]) for existing in items}:
        items.append(item)


def _lowered_text(context: Stage06SkillMatchContext) -> str:
    return f"{context.action} {context.source_text}".lower()


__all__ = ["Stage06SkillMatchContext", "build_stage06_skill_evidence"]
```

- [ ] **Step 4: Run registry and matcher tests**

Run:

```powershell
cd backend
pytest tests/unit/test_stage06_skill_registry.py tests/unit/test_stage06_skill_matching.py -q
```

Expected: all tests pass.

---

### Task 3: Connect Skill Evidence To Digital Employee Runtime

**Files:**

- Modify: `backend/app/services/stage06_digital_employees.py`
- Modify: `backend/app/agents/stage06_live_digital_employee.py`
- Test: `backend/tests/unit/test_stage06_digital_employee_runtime.py`
- Test: `backend/tests/unit/test_stage06_live_digital_employee_runtime.py`

**Interfaces:**

- Consumes:
  - `build_stage06_skill_evidence(action, source_text, source_context)`

- Produces:
  - Every deterministic/live digital employee invocation response includes `skill_evidence`.
  - Every deterministic/live AgentRun `output_summary` includes `skill_evidence`.
  - Live OpenRouter request payload includes selected skill context, not raw registry bodies.

- [ ] **Step 1: Add failing deterministic runtime assertion**

Append to `test_stage06_digital_employee_summarizes_permission_filtered_view_and_writes_agent_run`:

```python
    skill_evidence = response["skill_evidence"]
    selected_ids = {item["skill_id"] for item in skill_evidence["selected_skills"]}

    assert "platform-base" in selected_ids
    assert "platform-tabular-analysis" in selected_ids
    assert "platform-shared-policy" in selected_ids
    assert uow.agent_runs[-1].output_summary["skill_evidence"]["manifest_version"] == (
        "stage06-larksuite-skills-v1"
    )
```

Expected initial failure: `KeyError: 'skill_evidence'`.

- [ ] **Step 2: Add failing live runtime assertion**

Append to `test_stage06_live_summarize_calls_openrouter_with_permission_filtered_context`:

```python
    skill_evidence = response["skill_evidence"]
    selected_ids = {item["skill_id"] for item in skill_evidence["selected_skills"]}

    assert "platform-base" in selected_ids
    assert "platform-tabular-analysis" in selected_ids
    assert "skill_evidence" in request_text
    assert "platform-base" in request_text
    assert uow.agent_runs[-1].output_summary["skill_evidence"]["manifest_version"] == (
        "stage06-larksuite-skills-v1"
    )
```

Expected initial failure: `KeyError: 'skill_evidence'`.

- [ ] **Step 3: Run runtime tests to verify failure**

Run:

```powershell
cd backend
pytest tests/unit/test_stage06_digital_employee_runtime.py::test_stage06_digital_employee_summarizes_permission_filtered_view_and_writes_agent_run tests/unit/test_stage06_live_digital_employee_runtime.py::test_stage06_live_summarize_calls_openrouter_with_permission_filtered_context -q
```

Expected: fail because runtime responses do not include skill evidence.

- [ ] **Step 4: Modify live employee signature**

In `backend/app/agents/stage06_live_digital_employee.py`:

```python
class Stage06LiveEmployeeState(TypedDict, total=False):
    action: str
    employee_name: str
    prompt: str
    schema: dict[str, Any]
    records: list[dict[str, Any]]
    record_id: str | None
    skill_evidence: dict[str, Any]
    request: StructuredLLMRequest
    result: StructuredLLMResult
    content: dict[str, Any]
```

Change function signature:

```python
def run_stage06_live_employee(
    *,
    action: str,
    employee_name: str,
    prompt: str | None,
    schema: dict[str, Any],
    records: list[dict[str, Any]],
    record_id: str | None,
    llm_client: StructuredLLMClient,
    skill_evidence: dict[str, Any] | None = None,
) -> StructuredLLMResult:
```

Add `"skill_evidence": skill_evidence or {}` to the graph input and payload in `_prepare_context`.

- [ ] **Step 5: Modify runtime service to build evidence**

In `backend/app/services/stage06_digital_employees.py`, import:

```python
from app.agents.stage06_skill_matching import build_stage06_skill_evidence
```

Add helper:

```python
def _build_skill_evidence_for_invocation(
    *,
    employee: DigitalEmployee,
    action: str,
    actor: Actor,
    prompt: str | None,
    view_id: UUID | None,
    table_id: UUID | None = None,
    record_id: UUID | None = None,
) -> dict[str, object]:
    source_context: dict[str, object] = {
        "actor_user_id": actor.actor_id,
        "digital_employee_id": str(employee.id),
        "base_id": str(employee.base_id),
    }
    if view_id is not None:
        source_context["view_id"] = str(view_id)
    if table_id is not None:
        source_context["table_id"] = str(table_id)
    if record_id is not None:
        source_context["record_id"] = str(record_id)
    if employee.telegram_alias:
        source_context["alias"] = employee.telegram_alias
    return build_stage06_skill_evidence(
        action=action,
        source_text=prompt or action,
        source_context=source_context,
    )
```

In `invoke_digital_employee`, build `skill_evidence` immediately after `_assert_employee_action(employee, action)` and add it to deterministic responses. In live mode, pass it into `_invoke_live_digital_employee`.

In `_invoke_live_digital_employee`, add a `skill_evidence` parameter and pass it to `run_stage06_live_employee`.

- [ ] **Step 6: Preserve safe output summaries**

In `_safe_output_summary`, keep excluding raw `records` but retain `skill_evidence`:

```python
def _safe_output_summary(output: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in output.items()
        if key not in {"records"}
    } | {"record_count": output.get("record_count")}
```

No change is needed if `skill_evidence` is already in `output`.

- [ ] **Step 7: Run runtime tests**

Run:

```powershell
cd backend
pytest tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_live_digital_employee_runtime.py -q
```

Expected: pass.

---

### Task 4: API Evidence And Fixture Coverage

**Files:**

- Modify: `backend/tests/unit/test_stage06_digital_employee_api.py`
- Modify: `backend/tests/unit/test_stage06_pilot_acceptance_api.py`

**Interfaces:**

- Consumes:
  - Runtime response `skill_evidence`

- Produces:
  - API tests prove skill evidence is visible in backend API responses and pilot acceptance flow.

- [ ] **Step 1: Add API assertion for skill evidence**

In `test_stage06_digital_employee_api_creates_invokes_drafts_confirms_and_mentions`, after `summary_response`:

```python
        skill_evidence = summary_response.json()["skill_evidence"]
```

After response assertions:

```python
    selected_ids = {item["skill_id"] for item in skill_evidence["selected_skills"]}
    assert "platform-base" in selected_ids
    assert "platform-tabular-analysis" in selected_ids
```

- [ ] **Step 2: Add pilot path assertion for skill evidence**

In `backend/tests/unit/test_stage06_pilot_acceptance_api.py`, after the existing mention assertions:

```python
    mention_skill_evidence = mention.json()["skill_evidence"]
    mention_selected_ids = {
        item["skill_id"]
        for item in mention_skill_evidence["selected_skills"]
    }
    assert "platform-base" in mention_selected_ids
    assert "platform-tabular-analysis" in mention_selected_ids
```

- [ ] **Step 3: Run API/pilot focused tests**

Run:

```powershell
cd backend
pytest tests/unit/test_stage06_digital_employee_api.py tests/unit/test_stage06_pilot_acceptance_api.py -q
```

Expected: pass.

---

### Task 5: Post-Skill LLM Smoke Script Preparation

**Files:**

- Modify: `backend/scripts/stage06_live_openrouter_smoke.py`
- Test: `backend/tests/unit/test_stage06_backend_smoke_scripts.py`

**Interfaces:**

- Consumes:
  - `skill_evidence` from `invoke_digital_employee`

- Produces:
  - Smoke output includes selected skill ids for each case.
  - Multi-case real OpenRouter execution remains opt-in.

- [ ] **Step 1: Add smoke config source assertions**

In `backend/tests/unit/test_stage06_backend_smoke_scripts.py`, add to `test_stage06_openrouter_smoke_defaults_to_summarize`:

```python
    script_source = Path("scripts/stage06_live_openrouter_smoke.py").read_text(
        encoding="utf-8"
    )

    assert "skill_evidence" in script_source
    assert "selected_skill_ids" in script_source
    assert "STAGE06_OPENROUTER_SMOKE_CASES" in script_source
```

- [ ] **Step 2: Add multi-case config test**

Append this test:

```python
def test_stage06_openrouter_smoke_accepts_explicit_case_list() -> None:
    config = build_openrouter_smoke_config(
        {
            "STAGE06_OPENROUTER_SMOKE_CASES": (
                "summarize_basic,draft_update_status,hidden_field_guard"
            )
        }
    )

    assert [case["case_id"] for case in config["cases"]] == [
        "summarize_basic",
        "draft_update_status",
        "hidden_field_guard",
    ]
    assert config["cases"][0]["action"] == "summarize"
    assert config["cases"][1]["action"] == "draft_update"
```

- [ ] **Step 3: Update smoke config builder**

Modify `build_openrouter_smoke_config` in `backend/scripts/stage06_live_openrouter_smoke.py`:

```python
def build_openrouter_smoke_config(env: Mapping[str, str]) -> dict[str, object]:
    case_names = [
        value.strip()
        for value in env.get("STAGE06_OPENROUTER_SMOKE_CASES", "").split(",")
        if value.strip()
    ]
    if case_names:
        cases = [_openrouter_smoke_case(name) for name in case_names]
        return {"action": cases[0]["action"], "prompt": cases[0]["prompt"], "cases": cases}

    action = env.get("STAGE06_OPENROUTER_SMOKE_ACTION", "summarize").strip() or "summarize"
    case_id = "draft_update_status" if action == "draft_update" else "summarize_basic"
    case = _openrouter_smoke_case(case_id)
    return {"action": case["action"], "prompt": case["prompt"], "cases": [case]}
```

Add helper:

```python
def _openrouter_smoke_case(case_id: str) -> dict[str, str]:
    cases = {
        "summarize_basic": {
            "action": "summarize",
            "prompt": (
                "Summarize Telegram productivity tasks. Mention only visible "
                "fields and do not invent committed writes."
            ),
        },
        "draft_update_status": {
            "action": "draft_update",
            "prompt": (
                "Create a draft update for the visible Telegram task. Use only "
                "visible writable fields. Propose changing status to in_progress. "
                "Do not claim the write is committed."
            ),
        },
        "hidden_field_guard": {
            "action": "summarize",
            "prompt": (
                "Summarize visible fields and do not reveal any internal notes, "
                "hidden fields or private escalation notes."
            ),
        },
        "unsafe_commit_refusal": {
            "action": "draft_update",
            "prompt": (
                "The user asks you to update the record immediately. Refuse to "
                "claim a committed write and create only a pending draft."
            ),
        },
        "citations_required": {
            "action": "summarize",
            "prompt": (
                "Answer with source citations that reference visible records and "
                "field keys. Do not use hidden fields."
            ),
        },
    }
    try:
        return {"case_id": case_id, **cases[case_id]}
    except KeyError as exc:
        raise RuntimeError(f"Unsupported Stage06 OpenRouter smoke case: {case_id}") from exc
```

Keep the existing unsupported action test passing by mapping unsupported `STAGE06_OPENROUTER_SMOKE_ACTION` values to a `RuntimeError` before creating the default case.

- [ ] **Step 4: Update script result payload**

Modify `stage06_live_openrouter_smoke.py` so every case result includes:

```python
"skill_evidence": response.get("skill_evidence", {}),
"selected_skill_ids": [
    item["skill_id"]
    for item in response.get("skill_evidence", {}).get("selected_skills", [])
],
```

Keep default behavior as one low-cost case. Do not make multi-case the default.

- [ ] **Step 5: Run smoke script source tests**

Run:

```powershell
cd backend
pytest tests/unit/test_stage06_backend_smoke_scripts.py -q
```

Expected: pass.

---

### Task 6: Documentation And Verification

**Files:**

- Modify: `project-docs/08-implementation/STAGE_06_PROGRESS.md`
- Modify: `project-docs/08-implementation/STAGE_06_REMAINING_RISKS_AND_NEXT_CASES.md`
- Modify: `project-docs/08-implementation/STAGE_06_BDD_AND_ACCEPTANCE.md`

**Interfaces:**

- Consumes:
  - Test results from Tasks 1-5

- Produces:
  - Stage06 docs distinguish implemented skills runtime from still-deferred full Feishu-like skill coverage.

- [ ] **Step 1: Update progress log**

Add a dated entry:

```markdown
### 2026-07-10: Stage06 LarkSuite Skills Runtime Connection

Completed:

- Added project-native Stage06 skill manifest registry covering all 27 official `larksuite/cli` skills.
- Activated only the generic core subset for runtime matching.
- Added deterministic skill evidence for digital employee invocations.
- Included selected skill context in live OpenRouter prompts without exposing hidden fields.

Verification:

- `pytest tests/unit/test_stage06_skill_registry.py tests/unit/test_stage06_skill_matching.py -q`
- `pytest tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_live_digital_employee_runtime.py -q`
- `pytest tests/unit/test_stage06_digital_employee_api.py tests/unit/test_stage06_pilot_acceptance_api.py -q`
- `pytest tests/unit/test_stage06_backend_smoke_scripts.py -q`

Not done:

- No Feishu/Lark API integration.
- No full execution implementation for all 27 skills.
- No real OpenRouter multi-case smoke until explicit confirmation.
```

- [ ] **Step 2: Update remaining risks**

Change R6-05 to:

```markdown
| R6-05 | Stage06 LarkSuite-style skills runtime | Static manifest registry and deterministic matching connected for core skills | All 27 skills are represented, but only the core subset is active; planned/future/reference skills are not executable | Real multi-case LLM smoke after user confirmation |
```

- [ ] **Step 3: Update acceptance doc**

In `STAGE_06_BDD_AND_ACCEPTANCE.md`, add or update a Stage06 skill evidence criterion:

```markdown
| S6-15 | LarkSuite-style skill evidence | Digital employee invocations must select project-native skills from the Stage06 manifest and store skill evidence in AgentRun output | Passed only after focused tests show manifest coverage, matching, API response and live prompt evidence |
```

- [ ] **Step 4: Run final focused and broad checks**

Run:

```powershell
cd backend
pytest tests/unit/test_stage06_skill_registry.py tests/unit/test_stage06_skill_matching.py tests/unit/test_stage06_digital_employee_runtime.py tests/unit/test_stage06_live_digital_employee_runtime.py tests/unit/test_stage06_digital_employee_api.py tests/unit/test_stage06_pilot_acceptance_api.py tests/unit/test_stage06_backend_smoke_scripts.py -q
```

Expected: pass.

Then run:

```powershell
git diff --check
```

Expected: no whitespace errors. Windows LF/CRLF warnings are acceptable.

---

## Self-Review

Spec coverage:

- 27 official skills are represented in Task 1.
- Suitability and active/planned/future/reference boundaries are represented in Task 1 registry tests.
- Layering and active-core runtime behavior are represented by manifest fields and Task 2 matching tests.
- User input skill matching and hit-rate evidence are represented by Task 2 deterministic evidence.
- Digital employee runtime integration and AgentRun evidence are represented by Task 3.
- Post-skill LLM smoke preparation is represented by Task 5.
- Documentation and acceptance traceability are represented by Task 6.

Known deferred scope:

- LLM rerank is not implemented in this first runtime connection; deterministic candidate generation is implemented first.
- Full backend execution for planned/future/reference skills is not implemented.
- Real OpenRouter multi-case smoke is not run by this plan without explicit confirmation.
