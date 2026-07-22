import { useEffect, useMemo, useRef, useState } from 'react'

import type {
  ManagedEmployeeDetail,
  ManagedEmployeeDirectory,
  ManagedEmployeeManagementContext,
  ManagedEmployeeUpdateValues,
} from './digital-employee-management-types'

type DigitalEmployeeManagementWorkbenchProps = {
  context: ManagedEmployeeManagementContext | null
  directory: ManagedEmployeeDirectory | null
  detail: ManagedEmployeeDetail | null
  loading: boolean
  failed?: boolean
  onSelectEmployee: (employeeId: string) => void
  onCreate: (values: { name: string; description: string; telegramAlias: string | null }) => Promise<void>
  onUpdate: (employeeId: string, values: ManagedEmployeeUpdateValues, expectedVersion: number) => Promise<void>
  onReplaceGrants: (employeeId: string, memberIds: string[], expectedVersion: number) => Promise<void>
  onActivate: (employeeId: string, expectedVersion: number) => Promise<void>
  onPause: (employeeId: string, expectedVersion: number) => Promise<void>
  onReload?: () => Promise<void>
  onClose: () => void
}

function fixedError(error: unknown): string {
  const status = error && typeof error === 'object' && 'status' in error
    ? (error as { status?: unknown }).status
    : undefined
  if (status === 409) return '配置已被其他操作更新，请重新读取后再试。'
  if (status === 401 || status === 403 || status === 404) return '当前管理权限已失效，请重新打开数字员工管理。'
  return '暂时无法提交数字员工配置，请稍后重试。'
}

function sameIds(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index])
}

export function DigitalEmployeeManagementWorkbench({
  context,
  directory,
  detail,
  loading,
  failed = false,
  onSelectEmployee,
  onCreate,
  onUpdate,
  onReplaceGrants,
  onActivate,
  onPause,
  onReload,
  onClose,
}: DigitalEmployeeManagementWorkbenchProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [telegramAlias, setTelegramAlias] = useState('')
  const [tableIds, setTableIds] = useState<string[]>([])
  const [viewIds, setViewIds] = useState<string[]>([])
  const [actions, setActions] = useState<ManagedEmployeeDetail['allowedActions']>(['summarize'])
  const [accessMode, setAccessMode] = useState<ManagedEmployeeDetail['accessMode']>('assigned')
  const [memberIds, setMemberIds] = useState<string[]>([])
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [needsReload, setNeedsReload] = useState(false)

  useEffect(() => { headingRef.current?.focus() }, [])
  useEffect(() => {
    setName(detail?.name ?? '')
    setDescription(detail?.description ?? '')
    setTelegramAlias(detail?.telegramAlias ?? '')
    setTableIds(detail?.accessibleTableIds ?? [])
    setViewIds(detail?.accessibleViewIds ?? [])
    setActions(detail?.allowedActions ?? ['summarize'])
    setAccessMode(detail?.accessMode ?? 'assigned')
    setMemberIds(detail?.memberIds ?? [])
    setError(null)
    setNeedsReload(false)
  }, [detail?.id, detail?.version])

  const active = detail?.status === 'active'
  const editable = Boolean(detail && !active)
  const availableViews = useMemo(
    () => (context?.views ?? []).filter((view) => tableIds.includes(view.tableId)),
    [context?.views, tableIds],
  )
  const safeScope = tableIds.length > 0
    && viewIds.length > 0
    && viewIds.every((viewId) => availableViews.some((view) => view.id === viewId))
    && actions.includes('summarize')
    && (accessMode === 'workspace' || memberIds.length > 0)
  const hasUnsavedConfiguration = Boolean(detail) && (
    name.trim() !== detail?.name
    || description.trim() !== detail?.description
    || (telegramAlias.trim() || null) !== detail?.telegramAlias
    || !sameIds(tableIds, detail?.accessibleTableIds ?? [])
    || !sameIds(viewIds, detail?.accessibleViewIds ?? [])
    || !sameIds(actions, detail?.allowedActions ?? [])
    || accessMode !== detail?.accessMode
    || !sameIds(memberIds, detail?.memberIds ?? [])
  )
  const canActivate = editable && Boolean(name.trim() && description.trim() && safeScope) && !hasUnsavedConfiguration && pending === null
  const canCreate = !detail && Boolean(name.trim() && description.trim()) && pending === null

  function toggleId(current: string[], id: string): string[] {
    return current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
  }

  function toggleTable(tableId: string) {
    const nextTables = toggleId(tableIds, tableId)
    setTableIds(nextTables)
    setViewIds((current) => current.filter((viewId) => context?.views.some((view) => view.id === viewId && nextTables.includes(view.tableId))))
  }

  async function run(action: string, operation: () => Promise<void>) {
    setError(null)
    setNeedsReload(false)
    setPending(action)
    try {
      await operation()
    } catch (reason) {
      setError(fixedError(reason))
      if (reason && typeof reason === 'object' && 'status' in reason && (reason as { status?: unknown }).status === 409) setNeedsReload(true)
    } finally {
      setPending(null)
    }
  }

  async function reload() {
    if (!onReload) return
    setPending('reload')
    try {
      await onReload()
      setError(null)
      setNeedsReload(false)
    } catch {
      setError('暂时无法重新读取数字员工配置，请稍后重试。')
    } finally {
      setPending(null)
    }
  }

  return <div className="digital-employee-management-backdrop" role="presentation">
    <section className="digital-employee-management-workbench" aria-label="数字员工管理" data-testid="digital-employee-workbench" data-workbench-layout="three-pane">
      <header className="digital-employee-management-header">
        <div><p>DIGITAL EMPLOYEE</p><h2 ref={headingRef} tabIndex={-1}>数字员工管理</h2><span>员工只能在当前 Base 的已选表、视图和成员范围内被安全使用。</span></div>
        <button type="button" aria-label="关闭数字员工管理" onClick={onClose}>×</button>
      </header>
      {(failed || error) && <div className="digital-employee-management-error" role="alert"><p>{failed ? '暂时无法读取数字员工管理数据，请稍后重试。' : error}</p></div>}
      {needsReload && onReload ? <button className="digital-employee-management-reload" type="button" aria-label="重新读取员工配置" disabled={pending === 'reload'} onClick={() => { void reload() }}>{pending === 'reload' ? '重新读取中…' : '重新读取员工配置'}</button> : null}
      <div className="digital-employee-management-columns">
        <section className="digital-employee-management-section" aria-label="员工目录">
          <header><p>DIRECTORY</p><h3>当前 Base 员工</h3></header>
          {loading ? <p role="status">正在读取数字员工…</p> : directory?.employees.length ? <ul className="digital-employee-management-directory">{directory.employees.map((employee) => <li key={employee.id}><button type="button" className={detail?.id === employee.id ? 'selected' : ''} aria-pressed={detail?.id === employee.id} onClick={() => onSelectEmployee(employee.id)}><strong>{employee.name}</strong><span>{employee.status} · {employee.accessMode}</span></button></li>)}</ul> : <p>当前 Base 还没有数字员工。</p>}
        </section>
        <section className="digital-employee-management-section" aria-label="员工配置">
          <header><p>CONFIGURATION</p><h3>{detail ? (active ? '活动员工（只读）' : '员工配置') : '创建草稿员工'}</h3></header>
          <label>员工名称<input aria-label="员工名称" value={name} maxLength={160} disabled={active || pending !== null} onChange={(event) => setName(event.target.value)} /></label>
          <label>员工说明<textarea aria-label="员工说明" value={description} maxLength={500} disabled={active || pending !== null} onChange={(event) => setDescription(event.target.value)} /></label>
          <label>Telegram 别名<input aria-label="Telegram 别名" value={telegramAlias} maxLength={80} disabled={active || pending !== null} onChange={(event) => setTelegramAlias(event.target.value)} /></label>
          {!detail ? <button className="digital-employee-management-primary" type="button" disabled={!canCreate} onClick={() => { void run('create', () => onCreate({ name: name.trim(), description: description.trim(), telegramAlias: telegramAlias.trim() || null })) }}>创建草稿员工</button> : <>
            <fieldset disabled={active || pending !== null}><legend>表与视图范围</legend><div className="digital-employee-management-checklist">{(context?.tables ?? []).map((table) => <label key={table.id}><input aria-label={`范围表 ${table.name}`} type="checkbox" checked={tableIds.includes(table.id)} onChange={() => toggleTable(table.id)} />{table.name}</label>)}</div>{availableViews.length ? <div className="digital-employee-management-checklist">{availableViews.map((view) => <label key={view.id}><input aria-label={`范围视图 ${view.name}`} type="checkbox" checked={viewIds.includes(view.id)} onChange={() => setViewIds((current) => toggleId(current, view.id))} />{view.name}</label>)}</div> : <p>先选择可用数据表，再选择视图。</p>}</fieldset>
            <fieldset disabled={active || pending !== null}><legend>固定意图</legend><label><input aria-label="允许摘要" type="checkbox" checked={actions.includes('summarize')} onChange={() => setActions((current) => toggleId(current, 'summarize') as ManagedEmployeeDetail['allowedActions'])} />允许摘要</label><label><input aria-label="允许创建草稿" type="checkbox" checked={actions.includes('draft_update')} onChange={() => setActions((current) => toggleId(current, 'draft_update') as ManagedEmployeeDetail['allowedActions'])} />允许创建草稿</label></fieldset>
            <fieldset disabled={active || pending !== null}><legend>访问范围</legend><label><input aria-label="访问范围 workspace" type="radio" name="employee-access-mode" checked={accessMode === 'workspace'} onChange={() => setAccessMode('workspace')} />工作区内已授权成员</label><label><input aria-label="访问范围 assigned" type="radio" name="employee-access-mode" checked={accessMode === 'assigned'} onChange={() => setAccessMode('assigned')} />仅已分配成员</label>{accessMode === 'assigned' ? <div className="digital-employee-management-checklist">{(context?.members ?? []).map((member) => <label key={member.id}><input aria-label={`可用成员 ${member.label}`} type="checkbox" checked={memberIds.includes(member.id)} onChange={() => setMemberIds((current) => toggleId(current, member.id))} />{member.label} · {member.role}</label>)}</div> : null}</fieldset>
            {!active && hasUnsavedConfiguration ? <p className="digital-employee-management-hint" role="status">请先保存当前配置和成员，然后激活员工。</p> : null}
            <div className="digital-employee-management-actions">{active ? <button type="button" disabled={pending !== null} onClick={() => { void run('pause', () => onPause(detail.id, detail.version)) }}>暂停员工</button> : <><button type="button" disabled={pending !== null} onClick={() => { void run('save', () => onUpdate(detail.id, { name: name.trim(), description: description.trim(), telegramAlias: telegramAlias.trim() || null, accessibleTableIds: tableIds, accessibleViewIds: viewIds, allowedActions: actions, accessMode }, detail.version)) }}>保存配置</button><button type="button" disabled={pending !== null} onClick={() => { void run('grants', () => onReplaceGrants(detail.id, memberIds, detail.version)) }}>替换成员</button><button type="button" className="digital-employee-management-primary" disabled={!canActivate} onClick={() => { void run('activate', () => onActivate(detail.id, detail.version)) }}>激活员工</button></>}</div>
          </>}
        </section>
        <aside className="digital-employee-management-review" aria-label="运行状态与审计">
          <header><p>REVIEW</p><h3>运行状态</h3></header>
          <dl className="digital-employee-management-status-list">
            <div><dt>当前生命周期</dt><dd>{detail?.status ?? '未创建'}</dd></div>
            <div><dt>授权范围</dt><dd>{detail ? `${detail.tableCount} 张表 · ${detail.viewCount} 个视图` : '创建后读取'}</dd></div>
            <div><dt>成员可用性</dt><dd>{detail?.accessMode === 'assigned' ? `${detail.memberCount} 位已分配成员` : '工作区内已授权成员'}</dd></div>
          </dl>
          <section className="digital-employee-management-review-section" aria-label="确认约束">
            <h4>确认约束</h4>
            <p>员工只能创建受控草稿；记录写入仍须由有权限的用户在当前上下文确认。</p>
          </section>
          <section className="digital-employee-management-review-section" aria-label="审计说明">
            <h4>审计说明</h4>
            <p>生命周期、范围和成员变更由服务器记录。此页面不会展示运行时配置、提示词、模型或记忆数据。</p>
          </section>
        </aside>
      </div>
    </section>
  </div>
}
