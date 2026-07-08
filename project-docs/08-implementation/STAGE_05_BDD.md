# Stage 05 BDD

## Status

- Document status: active behavior design draft
- Scope: Stage05 behavior scenarios for Agent routing, draft creation, account inventory exceptions, confirmation, send/no-op evidence, views and failure handling.
- Current Progress: 2026-07-08 BDD scenarios remain the behavior source for Stage05. Automated local tests cover Agent routing, draft creation, account inventory exceptions, confirmation/no-op branches, customer reply send-confirm/fake-worker branches and Bitable-like views. Tencent Cloud staging scenarios have been exercised with real OpenRouter, real Telegram inbound, allowlisted reply send, no-op evidence, account exception evidence, additional real-case messages and safety close.

## 1. Feature: Bound Telegram Message Runs Stage05 Agent

### Scenario 1.1: Bound message enters Agent workflow

Given a Telegram message is stored in `messages`  
And the message has `binding_status = bound`  
And the message has `customer_id`  
And the message has `intent_status = intent_ready`  
When the Stage05 worker or manual API triggers the Agent workflow  
Then the message status becomes `agent_running` before the LLM call  
And an audit event records the workflow start  
And the Supervisor graph receives the message id, trace id and customer context.

### Scenario 1.2: Unbound message does not call OpenRouter

Given a Telegram message has `binding_status = needs_manual_binding`  
When Stage05 workflow is requested  
Then OpenRouter is not called  
And no service draft is created  
And the message remains reviewable through Telegram inbox or manual review views  
And audit records the rejected workflow reason.

### Scenario 1.3: Message not in `intent_ready` returns conflict

Given a message has `intent_status = routed`  
When Stage05 workflow is requested again without an explicit manual retry mode  
Then the API returns a stable conflict or the worker treats it as idempotent no-op  
And no duplicate drafts are created.

## 2. Feature: Multi-Intent Router

### Scenario 2.1: Mixed Chinese/English message produces multiple intents

Given a bound message text says `帮 act_123 充值 100 USD，顺便看下 BM invite，回复客户说我们在确认`  
When Message Intake Router calls OpenRouter  
Then the structured result contains `recharge`, `bm_invite` and `customer_reply` intents  
And the Router result includes account hint `act_123`  
And the Router result includes amount `100` and currency `USD`  
And the result has a redacted summary  
And the result is saved in `agent_runs` without full prompt exposure.

### Scenario 2.2: Router returns invalid JSON

Given OpenRouter returns content that is not a JSON object  
When the Router parser validates the response  
Then no service draft is created  
And `agent_runs.status = failed`  
And `messages.intent_status = agent_failed`  
And audit records `agent.output_invalid`.

### Scenario 2.3: Router returns low confidence

Given OpenRouter returns `overall_confidence < configured_threshold`  
When the Supervisor applies policy  
Then no `pending_confirmation` business draft is created  
And the message appears in `agent_review_queue`  
And audit records low confidence and review reason.

## 3. Feature: Child Draft Agents

### Scenario 3.1: Recharge draft is complete

Given Router intent type is `recharge`  
And entities include account hint, amount and currency  
When Recharge Draft Agent runs  
Then it creates `service_drafts.draft_type = recharge`  
And draft status is `pending_confirmation`  
And payload includes account hint, amount and currency  
And confidence is saved  
And no provider call is made.

### Scenario 3.2: Recharge draft is missing amount

Given Router intent type is `recharge`  
And entities include account hint but no amount  
When Recharge Draft Agent runs  
Then it creates `service_drafts.draft_type = recharge`  
And draft status is `needs_more_info`  
And `missing_fields` includes `amount` and `currency`  
And suggested follow-up text is stored in payload or redacted summary  
And the draft is not confirmable.

### Scenario 3.3: Card binding draft is complete enough for confirmation

Given Router intent type is `card_binding`  
And entities include account hint and card/profile hint that is already tokenized or safely referenced  
When Card Binding Draft Agent runs  
Then it creates `service_drafts.draft_type = card_binding`  
And draft status is `pending_confirmation` unless required fields are missing  
And raw card number or CVV is not stored.

### Scenario 3.4: BM invite draft is created

Given Router intent type is `bm_invite`  
And entities include BM hint and invitee/contact hint  
When BM Invite Draft Agent runs  
Then it creates `service_drafts.draft_type = bm_invite`  
And provider execution remains disabled  
And confirmation later creates only no-op service evidence.

### Scenario 3.5: Customer reply draft is created

Given Router intent type is `customer_reply`  
When Customer Reply Draft Agent runs  
Then it creates `service_drafts.draft_type = customer_reply`  
And payload includes reply text  
And status is `pending_confirmation` if reply text is safe and complete  
And the reply is not sent until a human confirms.

## 4. Feature: Account Inventory Agent

### Scenario 4.1: Agent does not produce accounts

Given a message asks `生产几个新账户`  
When Stage05 Router identifies account production intent  
Then Stage05 does not create `account_inventory` records  
And the message enters `manual_review` or a future-stage note  
And audit records that account production is out of Stage05 scope.

### Scenario 4.2: Agent creates account assignment draft only

Given a customer asks for an account  
And unused inventory accounts exist  
When Account Inventory Agent runs  
Then it may create `service_drafts.draft_type = account_assignment`  
And status is `pending_confirmation` or `needs_more_info`  
And no inventory account is allocated until human confirmation and backend permission checks.

### Scenario 4.3: High-confidence blocked account is automatically marked

Given a bound message or structured context clearly says an allocated account is封号/blocked  
And the account can be resolved to an existing inventory account  
When Account Inventory Agent evaluates the evidence  
Then `account_inventory.inventory_status` becomes `blocked` or `disabled` according to policy  
And `account_status_events` records before and after status  
And `ops_audit_events` records the automatic high-risk mark  
And no replacement account is recommended, reserved or assigned.

### Scenario 4.4: Ambiguous account risk enters manual review

Given a message says the account seems unstable but does not clearly prove block/risk-control  
When Account Inventory Agent evaluates it  
Then no account status is mutated  
And the issue appears in `agent_review_queue`  
And audit records the ambiguous risk reason.

### Scenario 4.5: Replacement request is not automated

Given an account was marked blocked  
And the customer asks for a replacement  
When Stage05 runs  
Then no replacement account is automatically recommended  
And no account is reserved  
And no account is assigned  
And the replacement request is visible for human handling.

## 5. Feature: Confirmation

### Scenario 5.1: Customer reply confirmation creates send request

Given a `customer_reply` draft has `status = pending_confirmation`  
And a manager/admin actor confirms it  
When the confirmation API runs  
Then the draft becomes `confirmed`  
And a `telegram_send_requests` row is created or linked  
And the target chat must be in the staging allowlist before real send  
And audit records confirmation.

### Scenario 5.2: Customer reply send is allowlisted only

Given a confirmed customer reply send request targets a non-allowlisted chat  
When send confirmation or worker handler runs  
Then Telegram API is not called  
And the send request is `blocked` or `failed` with safe error code  
And audit records the allowlist block.

### Scenario 5.3: Business draft confirmation creates no-op evidence

Given a `recharge`, `card_binding`, `bm_invite` or `account_assignment` draft is pending confirmation  
When an authorized actor confirms it  
Then a `service_records` row is created  
And an `execution_logs` row may be created with provider `noop` and status `skipped` or equivalent  
And no provider API is called  
And no execution ticket for real provider execution is used.

### Scenario 5.4: Draft with missing fields cannot be confirmed

Given a draft has `status = needs_more_info`  
When a confirm request is sent  
Then the API returns a stable conflict  
And no service record, send request or execution evidence is created.

## 6. Feature: Bitable-like Views

### Scenario 6.1: Service draft view shows business processing fields

Given Stage05 creates several service drafts  
When `GET /views/service_drafts/records` is called by an authorized actor  
Then records include draft type, status, customer id, source message id, confidence, missing fields, risk flags and trace id  
And sensitive fields are masked for unauthorized roles.

### Scenario 6.2: Agent review queue combines review sources

Given a message is low confidence  
Or a draft is `manual_review`  
Or an Agent run failed  
When `GET /views/agent_review_queue/records` is called  
Then the view shows the reason, trace id, linked message/draft/run and customer id where allowed.

### Scenario 6.3: Pending confirmation view shows confirmable work only

Given drafts exist in several statuses  
When `GET /views/pending_confirmation/records` is called  
Then only `pending_confirmation` drafts appear  
And drafts with missing fields or missing customer context do not appear  
And `needs_more_info`, `manual_review`, `rejected`, `confirmed` drafts do not appear.

### Scenario 6.4: Customer reply send request view is scoped and masked

Given customer reply send requests are linked to service drafts for multiple customers  
When a customer-scoped actor calls `GET /views/customer_reply_send_requests/records`  
Then only records linked to that actor's authorized customers appear  
And Telegram response details are masked for scoped actors.

### Scenario 6.5: Inbox and inventory views show Agent evidence

Given a message has related Stage05 AgentRun evidence and service drafts  
When `GET /views/telegram_inbox/records` is called  
Then the inbox row may show derived Agent status, draft count and last Agent error code  
And raw prompt or raw LLM response is not exposed.

Given account inventory has related abnormal status events  
When `GET /views/account_inventory/records` is called by manager/admin  
Then the row may show latest risk signal time and source  
And customer-scoped actors see only authorized rows with external account ids masked.

## 7. Feature: Staging Acceptance

### Scenario 7.1: Real OpenRouter staging run

Given Stage05 code is deployed to Tencent Cloud staging  
And OpenRouter key is configured server-side only  
And provider mode remains disabled  
When a mixed Chinese/English Telegram message is sent to the test bot  
Then OpenRouter is called once or according to the graph design  
And `agent_runs` records model/usage/cost/latency  
And multiple Stage05 outputs are visible in views.

### Scenario 7.2: Safety close after staging

Given Stage05 staging rehearsal completes  
When the operator closes the test window  
Then `TELEGRAM_SEND_MODE` returns to `dry_run`  
And test send allowlist is cleared or disabled  
And provider mode remains `disabled`  
And secrets are not recorded in docs.
