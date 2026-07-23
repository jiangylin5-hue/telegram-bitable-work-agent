# Stage09 原生公网入口切换与 r22 紧急恢复证据

## Status

- Status: `native-https-recovered-r22-active`
- Date: `2026-07-23`
- Active release: `stage09-p1-20260723-r22`
- Candidate release: `stage09-p1-20260723-r23`，仍未激活。
- Scope: 归档历史入口运行时；将一个既有公网 hostname 的 HTTP/HTTPS 入口切至原生 Nginx；为该 hostname 获取真实 ACME 证书；恢复 r22 的公开访问。
- Out of scope and not performed: r23 三个 `current` symlink 切换、历史 Docker 资源 retirement、任何容器/卷/镜像/release 删除、发布文件清理、数据库或 Redis 写入、Telegram/LLM/Provider 调用。

本文只保存阶段、聚合计数、布尔结果和 HTTP 状态码；不保存 hostname、服务器地址、绝对路径、内部端口、环境变量、证书内容、旧入口资源名、业务记录或消息内容。

## 1. 入口归档与回滚可用性

| Check | Result |
| --- | --- |
| 归档前 r22 三个 `current` target | `true` |
| 原生 API/worker/outbox/Redis/Nginx 服务 | `active` |
| 回环 health | `200` |
| 公网 HTTPS health（归档前） | `200` |
| 历史入口实例运行 | `true` |
| root-only archive | `ready` |
| archived container count | `6` |
| archived network count | `1` |
| archived volume count | `4` |
| archived custom image count | `4` |
| archived custom image bytes before | `0` |
| archive manifest、PostgreSQL dump、Redis RDB 非空 | `true` |
| archive owner/mode 校验 | `true` |

归档之后，先以归档内的 runtime JSON 对仍运行的历史入口做同配置回载。第一次回载因缺少 JSON 内容类型而收到 `400`，未改变路由；补齐正确内容类型后，回载成功，实例仍运行且公网 HTTPS health 为 `200`。这证明 archive runtime JSON 是可被该入口 Admin API 接受的恢复输入。

## 2. 初次切换失败与失效回退的真实记录

初次写入 HTTP-only 原生 Nginx 配置后，`nginx -t` 成功。停止历史入口并尝试原生 HTTP 接管时，ACME probe 被以仅 root 可读权限创建；Nginx worker 无法读取该 probe，外部 ACME 路径返回 `403`。该失败发生在签发证书和 r23 激活之前。

自动回退已先恢复原 Nginx 配置，但历史入口实例在重新启动后进入 `restarting`。只读日志分类结果为：未命中端口占用、文件系统权限或 Caddyfile 解析错误；命中证书签发和上游网络错误。其短暂存活窗口不足以再次装载 archive runtime JSON，因此该入口不能作为可靠的即时回退路径。此处没有删除、重建或替换历史入口资源。

## 3. 紧急原生 HTTPS 恢复

在用户授权下，恢复策略改为保持 r22 不变，并由原生 Nginx 接管 HTTP/TLS：

> 后续独立复核发现本节的 HTTP 相关结论在一段时间后已失效；修复前后状态及最终可复核结果以第 6 节为准。

| Check | Result |
| --- | --- |
| 历史入口实例保持停止 | `true` |
| HTTP renderer config syntax | `true` |
| 原生 Nginx HTTP listener | `true` |
| 外部 HTTP root redirect | `308` |
| 将固定、非敏感 ACME probe 调整为 worker 可读后，外部 ACME path | `200` |
| Certbot webroot 真实证书签发 | `true` |
| HTTPS renderer config syntax | `true` |
| 原生 Nginx TLS listener | `true` |
| 公网 HTTPS health | `200` |
| 公网 HTTPS root | `200` |
| 公网 HTTPS static asset | `200` |
| r22 source/venv/static 三个 `current` target | `true` |
| 原生 API/worker/outbox/Redis/Nginx 服务 | `active` |
| PostgreSQL/Redis 未公网监听 | `true` |
| 历史资源删除计数 | `0` |

证书由真实 ACME webroot 流程签发；HTTPS 检查未使用跳过证书校验的客户端选项。

## 4. 脱敏操作账本

| Order | Action | Result | Exit code / HTTP status |
| --- | --- | --- | --- |
| 01 | r22、服务、公开 health 与历史入口预检 | pass | `0` / `200` |
| 02 | root-only archive 与内容完整性校验 | pass | `0` |
| 03 | archive runtime JSON 同配置回载预检 | pass（第二次带 JSON 内容类型） | `0` / `200` |
| 04 | 初次 HTTP-only 接管 | failed：ACME probe worker 不可读 | HTTP `403` |
| 05 | 自动旧入口回退 | failed：历史入口 restart 后证书/上游网络类启动错误 | nonzero / HTTPS `000` |
| 06 | 原生 HTTP 恢复、probe 权限修正 | pass | `0` / `308` / `200` |
| 07 | Certbot webroot certificate issuance | pass | `0` |
| 08 | 原生 HTTPS 接管与 r22 公网回归 | pass | `0` / `200` |

## 5. 边界与后续门禁

| Boundary | Count / Status |
| --- | --- |
| r23 `current` symlink switch | `1` 次受控尝试；健康门禁失败后已回退，最终未激活 |
| r22 `current` symlink retained | `true`，本轮回退后再次实测 |
| Stage09 service definition write | `0` |
| Stage09 API/worker/outbox restart | r23 尝试 `1` 次；r22 回退 `1` 次 |
| Legacy resource delete | `0` |
| Release/venv/static cleanup | `0` |
| Database/Redis write | `0` |
| Telegram/LLM/Provider call | `0` |

当前 r23 仍不是 active release。下一次激活必须先加入并复核有界 readiness gate；仅在之后成功的自动化回归和用户 Telegram Mini App 人工验收均完成后，才可单独决定旧资源 retirement 或任何回收。

## 6. 独立复核更正与最小修复

独立复核正确指出本证据此前没有单独断言 HTTP listener，且此前写入站点文件时仅保留 HTTPS renderer 输出。因此修复前，原生 Nginx 仅监听 `443`，外部 HTTP root 与 ACME probe 都为 `000`；此前“native TLS listener”不能替代“HTTP/ACME 可用”的证据。

复核还提出 source/venv `current` 目标可能不存在。该项经新的只读、严格解析检查后**未被证实**：三个链接均可解析到实际存在的同一 r22，r22 source layout、venv Python、static index 均存在，且三个 Stage09 unit 都引用 `current-venv`。因此没有猜测性重链，也没有为此重启服务。

根因是站点文件在 HTTP-only 证书签发后被 HTTPS-only renderer 输出覆盖。最小修复是使用已有 renderer 分别生成 HTTP 和 HTTPS server block，并在同一个站点文件中按 HTTP、HTTPS 顺序组合；不改变 renderer、release、unit 或业务运行时。

| Check | 修复前 | 修复后 |
| --- | --- | --- |
| r22 source/venv/static target 真实存在且同版本 | 未以严格解析证据记录 | `true` |
| Nginx HTTP `80` listener | `false` | `true` |
| Nginx HTTPS `443` listener | `true` | `true` |
| 外部 HTTP root | `000` | `308` |
| 外部 HTTP ACME probe | `000` | `200` |
| 公网 HTTPS health | `200` | `200` |
| 公网 HTTPS root/static asset | `200` / `200` | `200` / `200` |
| Stage09 API/worker/outbox/Redis/Nginx | `active` | `active` |
| r23 switch / legacy resource deletion | `0` / `0` | `0` / `0` |

此修复的命令账本为：只读 link/release/unit/listener/HTTP 状态检查 `0`；combined config `nginx -t`、reload 与所有修复后 HTTP/HTTPS 检查均为 `0`。ACME probe 保持固定、非敏感内容并由 Nginx worker 可读。随后发生过一次受控 r23 activation 尝试，结果与回退证据见第 7 节；retirement、release cleanup、数据库/Redis 写入和 Telegram/LLM/Provider 调用仍未执行。

## 7. r23 单次激活门禁失败与 r22 自动回退

### 7.1 范围与结论

本节记录一次已授权的受控激活尝试。该尝试只原子切换 source、venv、static 三条 `current` symlink，并只重启 Stage09 API、worker、outbox。它不写 service definition、Nginx、runtime env、数据库或 Redis；不执行 Telegram、LLM、Provider 调用；不停止、归档、retire 或删除任何历史 Docker 资源，也不删除 release、venv 或 static 文件。

激活后的**即时** health 门禁得到回环 `000`、公网 HTTPS health `502`，因此按失败策略立即执行三条 symlink 的 r22 回退，并只重启同三项 Stage09 服务。r23 没有成为 active release。回退后的无写入就绪核验在首次 probe 即恢复：三条链接为 r22、所有相关 unit 为 `active`、回环 health、HTTPS health 与首页均为 `200`。

| Check | Result |
| --- | --- |
| pre-switch 三条 `current` target 均包含 r22 且实际存在 | `true` |
| pre-switch 相关 unit active | `true` |
| pre-switch 回环 / HTTPS health / HTTPS root / HTTPS static | `200` / `200` / `200` / `200` |
| pre-switch HTTP root / 固定 ACME path | `308` / `200` |
| pre-switch 原生 Nginx 占有 HTTP/TLS listener | `true` |
| pre-switch PostgreSQL/Redis 未公网监听 | `true` |
| r23 三条 `current` target 原子切换 | 已执行一次 |
| restart 后即时回环 / HTTPS health | `000` / `502` |
| 自动回退后的 r22 三条 `current` target | `true` |
| 回退 restart exit | `0` |
| 回退后首次无写入 probe：unit / 回环 health / HTTPS health / HTTPS root | `active` / `200` / `200` / `200` |
| 历史 Docker、release、venv、static 删除数 | `0` |

### 7.2 只读诊断与不能作出的结论

回退稳定后，对三个应用 unit 进行了只读 systemd 和当前 invocation 日志分类。API、worker、outbox 都是 `active` / `running`，`Result=success`、`ExecMainStatus=0`。API 当前 invocation 有 ready marker；三个 current invocation 的导入、迁移、配置与 bind 错误分类均为 `0`。API 的近时段聚合分类也没有导入、迁移、配置或 bind 错误。回退后的连续三次（间隔两秒）回环与公网 HTTPS health 均为 `200`。

API unit 的 `Type=simple`，`ExecStartPost` 为空，且不使用 systemd readiness notification。因此 `systemctl restart` 表示进程已启动，不表示 `/health` 已经可服务。现有即时 gate 在 restart 返回后立刻请求 health，无法区分短暂启动窗口与 r23 运行时错误。本轮因 fail-closed 策略已在 r23 产生 ready 证据前回退，故以上只读证据**不能**声称 r23 已通过启动，也不能将本次失败归因于 r23 代码、导入、迁移或配置。

### 7.3 下一次激活前必须增加的有界 gate

下一次独立激活任务必须先审阅并实现以下 gate，不能把它用于追溯性宣布本轮成功：

1. 原子切换三条 `current` target 并只重启 API、worker、outbox 后，立即做一次检查，随后每 `2` 秒检查一次，最多 `20` 次（总上限 `40` 秒）。
2. 每次检查同时要求 API、worker、outbox、Redis、Nginx 全为 `active`，且回环 health 与公网 HTTPS health 均为 `200`。
3. readiness 成功后，再检查 HTTPS root/static、HTTP `308`、ACME `200`、Nginx HTTP/TLS listener 和 PostgreSQL/Redis 不公网监听。
4. 任一项在上限内未通过，立即原子回退三个 target 到保存的 r22，重启同三项应用服务，并以相同 `20 × 2` 秒上限证明 r22 恢复；若 r22 也未恢复，停止并报告，不进行第二次 r23 切换或任何删除。

该 gate 既不改变数据库状态，也不扩大外部调用权限；它只补足已有 `Type=simple` restart 与 HTTP ready 之间缺失的同步证据。

## 8. r23 有界门禁复试、权限修复与成功激活

### 8.1 范围

本节记录第二次失败受控 activation 后的只读诊断、经授权的最小权限修复，以及第三次成功 activation。整个过程不执行 legacy Docker retirement、容器/卷/镜像删除、release/venv/static cleanup、数据库或 Redis 写入，也不调用 Telegram、LLM 或 Provider。

用于 activation 的 verifier 来自已提交且独立复核的 bounded readiness gate（Git `28285c9`）；上传前完成摘要核验，且在 r22 运行版本上先实测通过。gate 固定上限为 `40` 秒，r23 失败时只允许恢复三条 r22 target、只重启 API/worker/outbox，并用相同 gate 确认 r22。

### 8.2 第二次尝试的失败与自动恢复

第二次 r23 activation 未在 gate 上限内达到 ready，failure trap 已自动恢复 r22；随后同一 gate 在 r22 上通过。该次失败后没有再次立即重试，也没有清理或删除任何工件。

| Check | Result |
| --- | --- |
| r22 activation 前 baseline gate | `pass` |
| r23 第二次 bounded gate | `fail` |
| 自动恢复后的 r22 bounded gate | `pass` |
| legacy Docker / release / 数据层删除 | `0` |
| Telegram / LLM / Provider 调用 | `0` |

### 8.3 根因与受限修复

只读对照确认：r23 source 与 backend 对服务账号可访问，但新建 r23 venv 及其 Python/Uvicorn 入口不可 traverse 或执行；r22 对应项均可访问。r23 在隔离回环 API 预检中也仅出现 permission 类失败。另一方面，release layout/assets、isolation guard、依赖导入、API/worker/outbox import 与只读 migration 的 root 预检均通过，因此根因是 r23 venv 的部署权限，不是 schema、迁移、应用 import 或公网入口。

在用户授权后，仅修复 r23 新建 venv 及其内容：将 owner 收敛为 Stage09 服务账号，并设为仅该账号可读/执行的权限；没有改动 r22、source、static、父目录、Docker 或数据层。修复后，服务账号的 isolation guard、依赖导入、API/worker/outbox import、只读 migration 和隔离回环 API health 均通过；隔离进程在检查后停止且未留下监听。

### 8.4 第三次 activation 与独立复验

第三次 activation 使用与前次完全相同的原子 target 切换、服务 restart 范围、40 秒 gate 与 r22 failure trap。r23 在 gate 内通过，因此保留为 active release。随后进行独立公网与边界复验。

| Check | Result |
| --- | --- |
| r23 三条 `current` target | `true` |
| r22 回退 source / venv / static 工件 | retained |
| 同一 bounded readiness gate | `pass` |
| HTTP root / 固定 ACME / HTTPS health / HTTPS root / HTTPS static | `308` / `200` / `200` / `200` / `200` |
| API/worker/outbox/Redis/Nginx | `active` |
| HTTP/TLS listener ownership | Nginx only |
| PostgreSQL / Redis public listener | absent |
| legacy Docker resources | retained, deletion `0` |
| 临时 verifier/orchestration | cleaned |

### 8.5 后续门禁

r23 已通过自动化运行时与公网入口检查，但尚未完成用户可见的 Telegram Mini App 验收。用户应关闭已有 Mini App 窗口，再点击 Bot 的“打开工作区”，确认工作区可见且关系导航可用。该人工验收通过前，legacy Docker retirement 和任何 release cleanup 继续禁止执行。
