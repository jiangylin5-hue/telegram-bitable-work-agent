# PostgreSQL Database Design

## Status

- Document status: database design draft
- Scope: PostgreSQL schema、关系、唯一约束、敏感字段、事务边界、pgvector
- Current Progress: 2026-07-04 完成第一版数据库设计文档，并对齐多维表格总蓝图补充账户状态事件、绑卡、收款和 Bitable metadata 表。

## 1. Database Principles

- PostgreSQL 是业务事实来源。
- pgvector 只做检索辅助，不做当前业务事实来源。
- 核心业务表使用 normalized schema，不用一张大 JSON 表承载所有业务。
- 所有真实执行必须写 execution log。
- 所有关键状态变化必须写 audit event。
- 所有外部写入请求必须有 idempotency key。
- 敏感字段必须分类、脱敏和权限控制。

## 2. Core Tables

### 2.1 users

Purpose: 系统用户。

Fields:

- `id`: uuid, primary key。
- `display_name`: text。
- `role`: text, sales / customer_service / production / finance / manager / admin。
- `status`: active / disabled。
- `created_at`。
- `updated_at`。

Unique:

- `id`。

Sensitive:

- 无高敏字段，但用户身份和角色变更必须 audit。

### 2.2 telegram_identities

Purpose: Telegram 用户身份绑定。

Fields:

- `id`: uuid。
- `telegram_user_id`: text。
- `username`: text nullable。
- `user_id`: uuid nullable。
- `customer_id`: uuid nullable。
- `contact_type`: internal_user / customer_contact / unknown。
- `status`。

Unique:

- `telegram_user_id`。

Sensitive:

- Telegram identity 属于个人身份数据，需要权限控制。

### 2.3 customers

Purpose: 客户主数据。

Fields:

- `id`: uuid。
- `name`: text。
- `normalized_name`: text nullable。
- `owner_user_id`: uuid。
- `status`: active / paused / blocked / archived。
- `risk_level`: low / medium / high / unknown。
- `telegram_primary_group_id`: uuid nullable。
- `report_delivery_policy`: jsonb nullable。
- `notes`: text nullable。
- `created_at`。
- `updated_at`。

Unique:

- 可选 `normalized_name` 唯一。

Sensitive:

- notes 可能包含敏感信息，需要字段权限。

### 2.4 customer_groups

Purpose: 客户和 Telegram 群绑定。

Fields:

- `id`: uuid。
- `customer_id`: uuid。
- `telegram_chat_id`: text。
- `group_title`: text。
- `group_type`: customer_group / internal_ops / finance / unknown。
- `status`: active / disabled。
- `last_message_at`: timestamptz nullable。

Unique:

- `telegram_chat_id`。
- `customer_id + group_type + status(active)` 可限制一个活跃客户主群。

Sensitive:

- 群关系是业务敏感信息。

### 2.5 messages

Purpose: Telegram 消息入库。

Fields:

- `id`: uuid。
- `telegram_update_id`: text。
- `telegram_chat_id`: text。
- `telegram_message_id`: text。
- `sender_identity_id`: uuid nullable。
- `customer_group_id`: uuid nullable。
- `customer_id`: uuid nullable。
- `raw_text`: text nullable。
- `raw_caption`: text nullable。
- `normalized_text`: text nullable。
- `message_type`: text。
- `intent_status`: unclassified / routed / ignored / needs_review / failed。
- `intent_type`: recharge / bm_invite / card_binding / account_request / report_query / risk_query / unknown nullable。
- `received_at`: timestamptz。
- `ingestion_status`: stored / ignored / failed。
- `trace_id`: text。

Unique:

- `telegram_update_id`。
- `telegram_chat_id + telegram_message_id`。

Sensitive:

- raw_text 可能包含客户和支付信息，需要访问控制和脱敏策略。

### 2.6 account_assets

Purpose: 广告账户资产。

Fields:

- `id`: uuid。
- `customer_id`: uuid。
- `account_inventory_id`: uuid nullable。
- `external_account_id`: text。
- `account_name`: text。
- `platform`: meta。
- `status`: active / disabled / blocked / unknown。
- `balance_amount`: numeric nullable。
- `balance_currency`: text nullable。
- `spend_today`: numeric nullable。
- `spend_yesterday`: numeric nullable。
- `spend_7d`: numeric nullable。
- `last_read_at`: timestamptz nullable。
- `risk_status`: normal / low_balance / blocked / stale_data / unknown。

Unique:

- `platform + external_account_id`。

Sensitive:

- balance、spend、risk_status 需要字段权限。

### 2.6a account_inventory

Purpose: 账户库存，多维表格里的生产账户库存台账。

Fields:

- `id`: uuid。
- `platform`: meta。
- `external_account_id`: text。
- `inventory_status`: produced / unused / reserved / allocated / activated / disabled / blocked / recycled / archived。
- `production_batch_id`: text nullable。
- `produced_by_user_id`: uuid nullable。
- `assigned_customer_id`: uuid nullable。
- `assigned_user_id`: uuid nullable。
- `assigned_at`: timestamptz nullable。
- `status_reason`: text nullable。
- `created_at`。
- `updated_at`。

Unique:

- `platform + external_account_id`。

Sensitive:

- external_account_id、assigned_customer_id、status_reason。

### 2.6b account_assignments

Purpose: 账户分配历史，记录账户给了谁、什么时候给、谁确认。

Fields:

- `id`: uuid。
- `account_inventory_id`: uuid。
- `customer_id`: uuid。
- `assigned_by_user_id`: uuid。
- `confirmed_by_user_id`: uuid nullable。
- `assignment_status`: proposed / confirmed / cancelled / released。
- `assigned_at`: timestamptz。
- `released_at`: timestamptz nullable。
- `trace_id`: text。

Unique:

- 一个 active account 同时只能有一个 confirmed assignment。

Sensitive:

- 客户归属和分配历史。

### 2.6c account_daily_metrics

Purpose: 每日账户余额和消耗快照，用于客户日报和公司日报。

Fields:

- `id`: uuid。
- `account_asset_id`: uuid。
- `customer_id`: uuid。
- `metric_date`: date。
- `balance_amount`: numeric nullable。
- `balance_currency`: text nullable。
- `spend_amount`: numeric nullable。
- `spend_currency`: text nullable。
- `freshness_at`: timestamptz。
- `source`: provider / manual / imported。
- `read_status`: fresh / stale_data / missing_permission / readback_failed。

Unique:

- `account_asset_id + metric_date + source`。

Sensitive:

- balance_amount、spend_amount。

### 2.6d account_status_events

Purpose: 账户状态事件时间线，用于记录账户从生产、分配、启用、绑卡、充值、异常到回收的状态变化。

Fields:

- `id`: uuid。
- `account_inventory_id`: uuid nullable。
- `account_asset_id`: uuid nullable。
- `customer_id`: uuid nullable。
- `event_type`: produced / reserved / assigned / activated / bound_card / recharged / blocked / disabled / recycled / note。
- `before_status`: text nullable。
- `after_status`: text nullable。
- `reason`: text nullable。
- `source_entity_type`: text nullable。
- `source_entity_id`: uuid nullable。
- `actor_type`: user / agent / system / worker。
- `actor_id`: text。
- `created_at`: timestamptz。

Unique:

- `id`。

Sensitive:

- reason、external account 相关状态、客户归属变化。

### 2.7 service_drafts

Purpose: AI 或人工生成的待确认服务草稿。

Fields:

- `id`: uuid。
- `draft_type`: recharge / bm_invite / card_binding / account_assignment / risk_followup / customer_reply / daily_report。
- `status`: draft / needs_more_info / pending_confirmation / rejected / confirmed / manual_review / blocked。
- `customer_id`: uuid nullable。
- `account_asset_id`: uuid nullable。
- `account_inventory_id`: uuid nullable。
- `source_message_id`: uuid nullable。
- `created_by_type`: user / agent。
- `created_by_id`: uuid or text。
- `payload`: jsonb。
- `missing_fields`: jsonb。
- `risk_flags`: jsonb。
- `confidence`: numeric nullable。
- `trace_id`: text。
- `idempotency_key`: text。

Unique:

- `idempotency_key` when not null。

Sensitive:

- payload 可能含金额、客户备注、邮箱，需要字段级脱敏和访问控制。

### 2.8 service_records

Purpose: 已确认服务记录。

Fields:

- `id`: uuid。
- `service_type`: recharge / bm_invite / card_binding / account_assignment / risk_followup。
- `status`: pending / executing / succeeded / failed / blocked / manual_review。
- `customer_id`: uuid。
- `account_asset_id`: uuid nullable。
- `source_draft_id`: uuid nullable。
- `confirmed_by_user_id`: uuid nullable。
- `confirmed_at`: timestamptz nullable。
- `idempotency_key`: text。
- `trace_id`: text。

Unique:

- `idempotency_key`。

Sensitive:

- 失败原因、执行摘要、客户备注需要权限控制。

### 2.9 recharge_records

Purpose: 充值业务记录。

Fields:

- `id`: uuid。
- `service_record_id`: uuid。
- `customer_id`: uuid。
- `account_asset_id`: uuid。
- `collection_record_id`: uuid nullable。
- `amount`: numeric。
- `currency`: text。
- `collection_status`: missing / pending / confirmed / rejected。
- `execution_status`: not_started / queued / executing / succeeded / failed / blocked。
- `readback_status`: not_started / pending / succeeded / failed / not_supported。
- `readback_at`: timestamptz nullable。
- `execution_ticket_id`: uuid nullable。

Unique:

- `service_record_id`。

Sensitive:

- amount、collection evidence、失败原因。

### 2.9a collection_records

Purpose: 收款证据和财务确认记录。该表用于把客户付款、线下打款、收款截图和财务到账确认从充值执行中拆开。

Fields:

- `id`: uuid。
- `customer_id`: uuid。
- `recharge_record_id`: uuid nullable。
- `amount`: numeric。
- `currency`: text。
- `collection_method`: bank / crypto / card / other。
- `evidence_attachment_ref`: text nullable。
- `collection_status`: missing / pending / confirmed / rejected / manual_review。
- `confirmed_by_user_id`: uuid nullable。
- `confirmed_at`: timestamptz nullable。
- `finance_note`: text nullable。
- `trace_id`: text。
- `created_at`。
- `updated_at`。

Unique:

- `id`。
- 可选 `recharge_record_id + collection_status(confirmed)` 防止一个充值绑定多个有效确认记录。

Sensitive:

- amount、evidence_attachment_ref、finance_note。

Business rule:

- `collection_status = confirmed` 只代表收款确认，不代表广告账户充值执行成功。

### 2.10 payment_profiles

Purpose: 脱敏支付资源。

Fields:

- `id`: uuid。
- `provider`: text。
- `tokenized_profile_id`: text。
- `masked_label`: text。
- `last4`: text nullable。
- `brand`: text nullable。
- `status`: active / inactive / blocked / reserved。
- `customer_id`: uuid nullable。
- `limit_summary`: text nullable。
- `last_checked_at`: timestamptz nullable。

Unique:

- `provider + tokenized_profile_id`。

Sensitive:

- tokenized_profile_id 是敏感引用。

Forbidden:

- raw card number。
- CVV。
- 完整卡图。

### 2.10a account_card_bindings

Purpose: 账户和 tokenized payment profile 的绑定记录，支持一卡一户策略、绑卡状态、执行日志和失败原因。

Fields:

- `id`: uuid。
- `account_asset_id`: uuid。
- `payment_profile_id`: uuid。
- `customer_id`: uuid。
- `binding_status`: planned / pending_confirmation / executing / bound / failed / unbound / blocked。
- `one_card_one_account_policy`: strict / relaxed_by_manager。
- `service_record_id`: uuid nullable。
- `execution_log_id`: uuid nullable。
- `bound_at`: timestamptz nullable。
- `unbound_at`: timestamptz nullable。
- `failure_reason`: text nullable。
- `trace_id`: text。
- `created_at`。
- `updated_at`。

Unique:

- active `payment_profile_id` 同一时间只能绑定一个 active account，除非策略明确允许 `relaxed_by_manager`。
- active `account_asset_id` 同一时间只能有一个 `binding_status = bound`。

Sensitive:

- payment_profile_id、failure_reason、binding history。

### 2.11 risk_events

Purpose: 风险事件。

Fields:

- `id`: uuid。
- `customer_id`: uuid nullable。
- `account_asset_id`: uuid nullable。
- `risk_type`: low_balance / zero_spend / stale_data / missing_permission / blocked_account / abnormal_spend / readback_failed。
- `severity`: low / medium / high。
- `source_metric_id`: uuid nullable。
- `source_metric`: jsonb。
- `freshness_at`: timestamptz nullable。
- `status`: open / acknowledged / resolved / ignored。
- `owner_user_id`: uuid nullable。

Unique:

- 可按 `account_asset_id + risk_type + status(open)` 防止重复 open 风险。

Sensitive:

- source_metric 可能含金额。

### 2.12 execution_logs

Purpose: 真实执行证据。

Fields:

- `id`: uuid。
- `service_record_id`: uuid。
- `provider`: text。
- `provider_request_id`: text nullable。
- `provider_response_id`: text nullable。
- `execution_status`: succeeded / failed / pending / blocked。
- `request_summary`: jsonb。
- `response_summary`: jsonb。
- `error_code`: text nullable。
- `error_message_redacted`: text nullable。
- `executed_at`: timestamptz。
- `trace_id`: text。

Unique:

- `provider + provider_request_id` when request id exists。
- `service_record_id + provider + executed_at` index。

Sensitive:

- request/response 只能保存脱敏摘要。

### 2.13 ops_audit_events

Purpose: 审计事件。

Fields:

- `id`: uuid。
- `trace_id`: text。
- `actor_type`: user / agent / system / worker。
- `actor_id`: text。
- `event_type`: text。
- `entity_type`: text。
- `entity_id`: uuid nullable。
- `before_state`: jsonb nullable。
- `after_state`: jsonb nullable。
- `permission_snapshot`: jsonb nullable。
- `created_at`: timestamptz。

Unique:

- `id`。

Sensitive:

- before/after 必须脱敏，不保存 raw secret。

### 2.13a execution_tickets

Purpose: 人工确认后授权 Agent 执行真实动作的一次性票据。

Fields:

- `id`: uuid。
- `approved_by_user_id`: uuid。
- `approved_at`: timestamptz。
- `expires_at`: timestamptz。
- `allowed_action`: text。
- `allowed_customer_id`: uuid nullable。
- `allowed_account_id`: uuid nullable。
- `amount_limit`: numeric nullable。
- `payment_profile_id`: uuid nullable。
- `risk_snapshot`: jsonb。
- `permission_snapshot`: jsonb。
- `idempotency_key`: text。
- `status`: issued / used / expired / revoked。
- `used_at`: timestamptz nullable。
- `trace_id`: text。

Unique:

- `idempotency_key`。

Sensitive:

- permission_snapshot、risk_snapshot。

### 2.13b customer_daily_reports

Purpose: 客户日报。

Fields:

- `id`: uuid。
- `customer_id`: uuid。
- `report_date`: date。
- `report_payload`: jsonb。
- `visibility_scope`: jsonb。
- `delivery_status`: draft / queued / sent / failed / review_required。
- `reviewed_by_user_id`: uuid nullable。
- `sent_at`: timestamptz nullable。
- `trace_id`: text。

Unique:

- `customer_id + report_date`。

Sensitive:

- report_payload 包含金额、账户状态和客户信息。

### 2.13c company_daily_reports

Purpose: 公司全局日报。

Fields:

- `id`: uuid。
- `report_date`: date。
- `report_payload`: jsonb。
- `delivery_status`: draft / queued / sent / failed / review_required。
- `sent_at`: timestamptz nullable。
- `trace_id`: text。

Unique:

- `report_date`。

Sensitive:

- 全局客户、金额、账户和异常汇总。

### 2.14 agent_runs

Purpose: Agent 调用记录。

Fields:

- `id`: uuid。
- `agent_name`: text。
- `graph_name`: text。
- `model_provider`: openrouter。
- `model_name`: text。
- `prompt_version`: text。
- `input_summary`: jsonb。
- `output_summary`: jsonb。
- `tool_calls`: jsonb。
- `status`: succeeded / failed / needs_review。
- `trace_id`: text。
- `started_at`。
- `completed_at`。

Sensitive:

- input/output 只保存脱敏摘要，完整 prompt 是否保存需后续安全评审。

### 2.15 vector_documents

Purpose: pgvector 检索文档。

Fields:

- `id`: uuid。
- `doc_type`: sop / historical_case / provider_error / reply_template / customer_note。
- `title`: text。
- `content_redacted`: text。
- `embedding`: vector。
- `source_entity_type`: text nullable。
- `source_entity_id`: uuid nullable。
- `visibility_scope`: jsonb。

Sensitive:

- content 必须脱敏。

### 2.16 table_views

Purpose: 多维表格视图定义。第一阶段可以代码固定配置，但数据库设计预留该实体。

Fields:

- `id`: uuid。
- `table_name`: text。
- `view_key`: text。
- `view_name`: text。
- `view_type`: table / kanban / dashboard / inbox / report / audit。
- `role_scope`: jsonb。
- `status`: active / disabled。
- `created_at`。
- `updated_at`。

Unique:

- `view_key`。

Sensitive:

- role_scope 可能暴露权限结构。

### 2.17 view_columns

Purpose: 多维表格视图列配置。

Fields:

- `id`: uuid。
- `view_id`: uuid。
- `field_name`: text。
- `display_name`: text。
- `order_index`: integer。
- `visible_if_permission`: text nullable。
- `width`: integer nullable。
- `created_at`。
- `updated_at`。

Unique:

- `view_id + field_name`。

### 2.18 view_filters

Purpose: 多维表格视图筛选条件配置。

Fields:

- `id`: uuid。
- `view_id`: uuid。
- `field_name`: text。
- `operator`: text。
- `value`: jsonb。
- `role_scope`: jsonb nullable。
- `created_at`。
- `updated_at`。

Unique:

- `id`。

### 2.19 field_permissions

Purpose: 字段级权限配置，控制用户和 Agent 对金额、卡资源、支付凭证引用、失败原因等敏感字段的读写。

Fields:

- `id`: uuid。
- `table_name`: text。
- `field_name`: text。
- `role`: text。
- `actor_type`: user / agent / system。
- `can_read`: boolean。
- `can_write`: boolean。
- `masking_rule`: none / redacted / partial / aggregate_only。
- `created_at`。
- `updated_at`。

Unique:

- `table_name + field_name + role + actor_type`。

Sensitive:

- 权限配置本身只能由管理角色查看和修改。

### 2.20 automation_rules

Purpose: 多维表格自动化规则，用于状态变化触发提醒、日报、执行 ticket、异常升级和 Telegram 回传。

Fields:

- `id`: uuid。
- `trigger_table`: text。
- `trigger_event`: record_created / field_changed / status_changed / scheduled。
- `condition_json`: jsonb。
- `action_type`: enqueue_job / notify_user / create_draft / issue_ticket / send_telegram / create_risk_event。
- `action_payload`: jsonb。
- `status`: active / disabled。
- `created_at`。
- `updated_at`。

Unique:

- `id`。

Sensitive:

- action_payload 可能包含通知范围和权限条件，需要管理权限。

## 3. Relationships

核心关系：

- customer has many customer_groups。
- customer has many account_assets。
- customer has many account_inventory assignments。
- customer has many service_drafts。
- customer has many service_records。
- customer has many collection_records。
- message may create many service_drafts。
- service_draft may become one service_record。
- service_record may have one recharge_record。
- recharge_record may have one collection_record。
- service_record may have one or many account_card_bindings depending on retry history。
- service_record has many execution_logs。
- all important entities have many ops_audit_events。
- agent_run may create service_draft。
- execution_ticket authorizes one controlled execution。
- account_inventory may link to account_asset after activation。
- account_inventory and account_asset have many account_status_events。
- account_daily_metrics feed customer_daily_reports and company_daily_reports。
- payment_profile has many account_card_bindings over time, but active binding is constrained。

## 4. Transaction Boundaries

- message insert + audit event: same transaction。
- draft create + audit event: same transaction。
- draft confirm + service_record create + audit event: same transaction。
- execution job enqueue should happen after transaction commit or via outbox pattern。
- provider call outside DB transaction。
- execution_log insert + service status update + audit event: same transaction。

## 5. Indexing Strategy

建议索引：

- messages: `telegram_chat_id + telegram_message_id`。
- messages: `customer_group_id + received_at`。
- service_drafts: `status + draft_type + created_at`。
- service_records: `customer_id + status + created_at`。
- recharge_records: `execution_status + readback_status`。
- collection_records: `customer_id + collection_status + created_at`。
- account_assets: `customer_id + status`。
- account_inventory: `inventory_status + assigned_customer_id`。
- account_card_bindings: `account_asset_id + binding_status`。
- account_status_events: `account_inventory_id + created_at` and `account_asset_id + created_at`。
- risk_events: `status + severity + created_at`。
- execution_logs: `service_record_id`。
- ops_audit_events: `trace_id`。
- agent_runs: `trace_id`。
- table_views: `view_key`。

## 6. Stage 02 Data Decisions

Stage 02 已确认：

- 第一版不做多租户 `tenant_id`。
- 第一版采用 outbox table 保证 DB transaction 与 Redis enqueue 一致。
- 第一版 `payment_profiles` 落库，但只保存 tokenized / masked payment profile，不保存 raw card / CVV。
- 第一版 LLM prompt 和 output 只保存脱敏摘要；完整 prompt 存储留到后续安全评审。
