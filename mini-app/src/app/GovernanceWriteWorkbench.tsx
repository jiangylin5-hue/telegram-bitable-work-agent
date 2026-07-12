import { useEffect, useRef, useState } from 'react'

import type { BaseSummary, PlatformTable, ViewSummary } from './api'
import type {
  GovernanceAssignableRole,
  GovernanceEditableMemberPage,
  GovernanceFieldPermissionPage,
  GovernanceFieldPermissionPolicy,
} from './governance-write-types'

type GovernanceWriteWorkbenchProps = {
  bases: BaseSummary[]
  tables: PlatformTable[]
  views: ViewSummary[]
  members: GovernanceEditableMemberPage | null
  fields: GovernanceFieldPermissionPage | null
  selectedBaseId: string | null
  selectedTableId: string | null
  membersLoading: boolean
  tablesLoading: boolean
  fieldsLoading: boolean
  contextError?: 'base_not_available' | 'table_not_available'
  onSelectBase: (baseId: string) => void
  onSelectTable: (tableId: string) => void
  onChangeRole: (memberId: string, role: GovernanceAssignableRole, expectedVersion: number) => Promise<void>
  onReplacePolicy: (fieldId: string, policy: GovernanceFieldPermissionPolicy, expectedVersion: number) => Promise<void>
  onReloadMembers?: () => Promise<void>
  onReloadFields?: () => Promise<void>
  onOpenViewAccess: (viewId: string) => void
  onClose: () => void
}

const roleLabel: Record<string, string> = {
  owner: '所有者', admin: '管理员', builder: '构建者', operator: '运营者', viewer: '查看者',
}

const policyLabel: Record<string, string> = {
  hidden: '隐藏', read: '可读', write: '可写',
}

function fixedError(error: unknown): string {
  const status = error && typeof error === 'object' && 'status' in error ? (error as { status?: unknown }).status : undefined
  if (status === 409) return '数据已更新，请重新读取后再提交。'
  if (status === 401 || status === 403 || status === 404) return '权限状态已失效，请重新打开治理工作台。'
  return '无法提交权限更改，请稍后重试。'
}

function errorStatus(error: unknown): number | undefined {
  const status = error && typeof error === 'object' && 'status' in error
    ? (error as { status?: unknown }).status
    : undefined
  return typeof status === 'number' ? status : undefined
}

export function GovernanceWriteWorkbench({
  bases,
  tables,
  views,
  members,
  fields,
  selectedBaseId,
  selectedTableId,
  membersLoading,
  tablesLoading,
  fieldsLoading,
  contextError,
  onSelectBase,
  onSelectTable,
  onChangeRole,
  onReplacePolicy,
  onReloadMembers,
  onReloadFields,
  onOpenViewAccess,
  onClose,
}: GovernanceWriteWorkbenchProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [roleDrafts, setRoleDrafts] = useState<Record<string, GovernanceAssignableRole>>({})
  const [policyDrafts, setPolicyDrafts] = useState<Record<string, GovernanceFieldPermissionPolicy>>({})
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null)
  const [selectedViewId, setSelectedViewId] = useState('')
  const [pendingKey, setPendingKey] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reloadTarget, setReloadTarget] = useState<'members' | 'fields' | null>(null)

  useEffect(() => { headingRef.current?.focus() }, [])
  useEffect(() => {
    setRoleDrafts(Object.fromEntries((members?.members ?? []).map((member) => [member.id, member.role as GovernanceAssignableRole])))
  }, [members])
  useEffect(() => {
    const next = Object.fromEntries((fields?.fields ?? []).map((field) => [field.id, field.policy]))
    setPolicyDrafts(next)
    setSelectedFieldId((current) => current && next[current] ? current : fields?.fields[0]?.id ?? null)
  }, [fields])
  const ownedRestrictedViews = views.filter((view) => view.scope === 'restricted' && view.caller_access_level === 'owner' && Boolean(view.table_id))
  useEffect(() => {
    setSelectedViewId((current) => ownedRestrictedViews.some((view) => view.id === current) ? current : ownedRestrictedViews[0]?.id ?? '')
  }, [views])

  const selectedField = fields?.fields.find((field) => field.id === selectedFieldId) ?? null
  const selectedPolicy = selectedField ? policyDrafts[selectedField.id] ?? selectedField.policy : null

  async function submitRole(memberId: string, role: GovernanceAssignableRole, expectedVersion: number) {
    setError(null)
    setReloadTarget(null)
    setPendingKey(`role:${memberId}`)
    try {
      await onChangeRole(memberId, role, expectedVersion)
    } catch (reason) {
      setError(fixedError(reason))
      if (errorStatus(reason) === 409) setReloadTarget('members')
    } finally {
      setPendingKey(null)
    }
  }

  async function submitPolicy() {
    if (!selectedField || !selectedPolicy) return
    setError(null)
    setReloadTarget(null)
    setPendingKey(`policy:${selectedField.id}`)
    try {
      await onReplacePolicy(selectedField.id, selectedPolicy, selectedField.permissionVersion)
    } catch (reason) {
      setError(fixedError(reason))
      if (errorStatus(reason) === 409) setReloadTarget('fields')
    } finally {
      setPendingKey(null)
    }
  }

  async function reloadConflictContext() {
    const reload = reloadTarget === 'members' ? onReloadMembers : onReloadFields
    if (!reload) return
    setPendingKey('reload')
    try {
      await reload()
      setError(null)
      setReloadTarget(null)
    } catch {
      setError('无法重新读取权限状态，请稍后重试。')
    } finally {
      setPendingKey(null)
    }
  }

  return <div className="governance-write-backdrop" role="presentation">
    <aside className="governance-write-workbench" aria-label="权限设置" aria-modal="true" role="dialog">
      <header className="governance-write-header">
        <div>
          <p>GOVERNANCE WRITE</p>
          <h2 ref={headingRef} tabIndex={-1}>成员角色与字段权限</h2>
          <span>变更会经过服务器权限、版本与审计校验。</span>
        </div>
        <button type="button" aria-label="关闭权限设置" onClick={onClose}>×</button>
      </header>
      {error && <p className="governance-write-error" role="alert">{error}</p>}
      {reloadTarget && (reloadTarget === 'members' ? onReloadMembers : onReloadFields) && <button className="governance-write-reload" type="button" disabled={pendingKey === 'reload'} onClick={() => { void reloadConflictContext() }}>{pendingKey === 'reload' ? '重新读取中…' : reloadTarget === 'members' ? '重新读取成员角色' : '重新读取字段权限'}</button>}
      {contextError && <p className="governance-write-error" role="alert">{contextError === 'base_not_available' ? '所选 Base 已不可用，请重新选择。' : '所选数据表已不可用，请重新选择。'}</p>}
      <div className="governance-write-columns">
        <section className="governance-write-section" aria-label="成员角色设置">
          <header><p>MEMBER ROLES</p><h3>成员角色</h3></header>
          {membersLoading
            ? <p className="governance-write-empty" role="status">正在读取可编辑成员…</p>
            : members?.members.length
              ? <ul className="governance-write-member-list">{members.members.map((member) => {
                const draft = roleDrafts[member.id] ?? member.role as GovernanceAssignableRole
                const pending = pendingKey === `role:${member.id}`
                return <li key={member.id}>
                  <strong>{member.userId}</strong>
                  <label>成员 {member.userId} 的角色
                    <select value={draft} disabled={pending} onChange={(event) => setRoleDrafts((current) => ({ ...current, [member.id]: event.target.value as GovernanceAssignableRole }))}>
                      {member.assignableRoles.map((role) => <option key={role} value={role}>{roleLabel[role]}</option>)}
                    </select>
                  </label>
                  <button type="button" disabled={pending || draft === member.role} onClick={() => { void submitRole(member.id, draft, member.version) }} aria-label={`确认改为 ${draft}`}>
                    {pending ? '提交中…' : `确认改为 ${draft}`}
                  </button>
                </li>
              })}</ul>
              : <p className="governance-write-empty">当前没有可编辑成员。</p>}
        </section>
        <section className="governance-write-section" aria-label="字段权限设置">
          <header><p>FIELD ACCESS</p><h3>字段权限</h3></header>
          <label className="governance-write-select">选择 Base
            <select value={selectedBaseId ?? ''} onChange={(event) => onSelectBase(event.target.value)}>
              <option value="">选择已授权 Base</option>
              {bases.map((base) => <option key={base.id} value={base.id}>{base.name}</option>)}
            </select>
          </label>
          {selectedBaseId && <label className="governance-write-select">选择数据表
            <select value={selectedTableId ?? ''} disabled={tablesLoading} onChange={(event) => onSelectTable(event.target.value)}>
              <option value="">选择数据表</option>
              {tables.map((table) => <option key={table.id} value={table.id}>{table.name}</option>)}
            </select>
          </label>}
          <div className="governance-write-view-access">
            <header><p>REUSE V1</p><h4>视图访问</h4></header>
            {ownedRestrictedViews.length
              ? <><label className="governance-write-select">选择本人拥有的受限视图
                <select value={selectedViewId} onChange={(event) => setSelectedViewId(event.target.value)}>
                  {ownedRestrictedViews.map((view) => <option key={view.id} value={view.id}>{view.name}</option>)}
                </select>
              </label>
              <button type="button" onClick={() => onOpenViewAccess(selectedViewId)} aria-label="打开已有视图访问设置">打开已有视图访问设置</button>
              <p className="governance-write-empty">使用既有 V1 版本化成员授权；此处不创建新的视图权限策略。</p></>
              : <p className="governance-write-empty">当前没有可由你管理的受限视图访问权限。</p>}
          </div>
          {fieldsLoading
            ? <p className="governance-write-empty" role="status">正在读取字段权限…</p>
            : selectedField && selectedPolicy
              ? <div className="governance-write-policy">
                <label className="governance-write-select">选择字段
                  <select value={selectedField.id} onChange={(event) => setSelectedFieldId(event.target.value)}>{fields?.fields.map((field) => <option value={field.id} key={field.id}>{field.label}</option>)}</select>
                </label>
                {(['owner', 'admin', 'builder', 'operator', 'viewer'] as const).map((role) => <label className="governance-write-policy-row" key={role}>字段 {selectedField.label} 的 {role} 权限
                  <select value={selectedPolicy[role]} disabled={role === 'owner' || pendingKey === `policy:${selectedField.id}`} onChange={(event) => setPolicyDrafts((current) => ({ ...current, [selectedField.id]: { ...selectedPolicy, [role]: event.target.value as GovernanceFieldPermissionPolicy[typeof role] } }))}>
                    {(['hidden', 'read', 'write'] as const).map((mode) => <option key={mode} value={mode}>{policyLabel[mode]}</option>)}
                  </select>
                </label>)}
                <button type="button" disabled={pendingKey === `policy:${selectedField.id}`} onClick={() => { void submitPolicy() }} aria-label="确认字段权限">
                  {pendingKey === `policy:${selectedField.id}` ? '提交中…' : '确认字段权限'}
                </button>
              </div>
              : selectedTableId ? <p className="governance-write-empty">当前数据表没有可编辑字段。</p> : <p className="governance-write-empty">选择 Base 和数据表后配置字段权限。</p>}
        </section>
      </div>
    </aside>
  </div>
}
