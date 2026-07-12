import type { BaseSummary } from './api'
import type { GovernanceAuditPage, GovernanceMemberPage } from './governance-types'

type GovernanceWorkbenchProps = {
  bases: BaseSummary[]
  members: GovernanceMemberPage | null
  audit: GovernanceAuditPage | null
  selectedBaseId: string | null
  membersLoading: boolean
  auditLoading: boolean
  membersError?: boolean
  auditError?: boolean
  membersLoadMoreError?: boolean
  auditLoadMoreError?: boolean
  onSelectBase: (baseId: string) => void
  onLoadMoreMembers: () => void
  onLoadMoreAudit: () => void
  onRetryMembers: () => void
  onRetryAudit: () => void
  onClose: () => void
}

const roleLabels: Record<string, string> = {
  owner: '所有者',
  admin: '管理员',
  builder: '构建者',
  operator: '运营者',
  viewer: '查看者',
}

const statusLabels: Record<string, string> = {
  active: '启用',
  inactive: '停用',
}

const actorLabels: Record<string, string> = {
  user: '用户',
  digital_employee: '数字员工',
  system: '系统',
}

function memberRole(value: string): string {
  return roleLabels[value] ?? '未知角色'
}

function memberStatus(value: string): string {
  return statusLabels[value] ?? '未知状态'
}

function auditActor(value: string): string {
  return actorLabels[value] ?? '系统'
}

function auditLabel(_eventType: string): string {
  return '已记录系统操作'
}

function auditTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString()
}

export function GovernanceWorkbench({
  bases,
  members,
  audit,
  selectedBaseId,
  membersLoading,
  auditLoading,
  membersError = false,
  auditError = false,
  membersLoadMoreError = false,
  auditLoadMoreError = false,
  onSelectBase,
  onLoadMoreMembers,
  onLoadMoreAudit,
  onRetryMembers,
  onRetryAudit,
  onClose,
}: GovernanceWorkbenchProps) {
  return <div className="governance-backdrop" role="presentation">
    <aside className="governance-workbench" aria-label="治理工作台" aria-modal="true" role="dialog">
      <header className="governance-header">
        <div>
          <p>GOVERNANCE</p>
          <h2>成员与审计</h2>
          <span>仅展示当前权限范围内的安全摘要。</span>
        </div>
        <button type="button" aria-label="关闭治理工作台" onClick={onClose}>×</button>
      </header>
      <div className="governance-columns">
        <section className="governance-section" aria-label="成员目录">
          <header><div><p>MEMBERS</p><h3>成员目录</h3></div></header>
          {membersLoading
            ? <p className="governance-empty">正在加载成员…</p>
            : membersError
              ? <p className="governance-error">成员暂时无法加载。<button type="button" onClick={onRetryMembers}>重试成员加载</button></p>
              : members?.members.length
                ? <ul className="governance-member-list">{members.members.map((member) => <li key={member.id}>
                  <div><strong>{member.userId}</strong><span>{memberRole(member.role)}</span></div><small>{memberStatus(member.status)}</small>
                </li>)}</ul>
                : <p className="governance-empty">当前没有可展示的成员。</p>}
          {membersLoadMoreError && <p className="governance-error">更多成员暂时无法加载。<button type="button" onClick={onRetryMembers}>重试加载更多成员</button></p>}
          {members?.hasMore && <button className="governance-more" type="button" onClick={onLoadMoreMembers}>加载更多成员</button>}
        </section>
        <section className="governance-section" aria-label="Base 审计">
          <header><div><p>AUDIT</p><h3>Base 审计</h3></div></header>
          <label className="governance-base-select">选择 Base
            <select value={selectedBaseId ?? ''} onChange={(event) => onSelectBase(event.target.value)}><option value="">选择已授权 Base</option>{bases.map((base) => <option value={base.id} key={base.id}>{base.name}</option>)}</select>
          </label>
          {!selectedBaseId
            ? <p className="governance-empty">选择一个已授权 Base 后读取审计时间线。</p>
            : auditLoading
              ? <p className="governance-empty">正在加载审计记录…</p>
              : auditError
                ? <p className="governance-error">审计记录暂时无法加载。<button type="button" onClick={onRetryAudit}>重试审计加载</button></p>
                : audit?.events.length
                  ? <ol className="governance-audit-list">{audit.events.map((event) => <li key={event.id}>
                    <time dateTime={event.occurredAt}>{auditTime(event.occurredAt)}</time>
                    <div><strong>{auditLabel(event.eventType)}</strong><span>{auditActor(event.actorType)} · {event.entityType}</span></div>
                  </li>)}</ol>
                  : <p className="governance-empty">当前 Base 没有可展示的审计记录。</p>}
          {auditLoadMoreError && <p className="governance-error">更多审计记录暂时无法加载。<button type="button" onClick={onRetryAudit}>重试加载更多审计记录</button></p>}
          {audit?.hasMore && <button className="governance-more" type="button" onClick={onLoadMoreAudit}>加载更多审计记录</button>}
        </section>
      </div>
    </aside>
  </div>
}
