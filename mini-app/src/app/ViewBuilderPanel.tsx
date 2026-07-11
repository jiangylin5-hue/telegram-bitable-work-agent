import { ChevronDown, ChevronUp, Columns3, Settings2, X } from 'lucide-react'
import { type FormEvent, useEffect, useRef, useState } from 'react'

import { toSafeViewError, type RelationCandidatePage } from './api'
import { ViewAccessPanel } from './ViewAccessPanel'
import { ViewQueryControls } from './ViewQueryControls'
import type {
  SafeViewField,
  ViewBuilderContext,
  ViewBuilderResponse,
  ViewInitializationRequest,
  ViewMemberReplaceRequest,
  ViewPresentationCommand,
  ViewPresentationPatchRequest,
  ViewType,
} from './view-builder-types'

type ViewBuilderPanelProps = {
  context: ViewBuilderContext
  builder?: ViewBuilderResponse
  onCreate: (request: ViewInitializationRequest, idempotencyKey: string) => Promise<ViewBuilderResponse>
  onSave: (request: ViewPresentationPatchRequest) => Promise<ViewBuilderResponse>
  onReplaceMembers: (request: ViewMemberReplaceRequest) => Promise<void>
  onClose: () => void
  loadRelationCandidates?: (fieldId: string, query: string, cursor: string | null) => Promise<RelationCandidatePage>
}

const viewTypeLabels: Record<ViewType, string> = {
  grid: '表格',
  kanban: '看板',
  calendar: '日历',
  form: '表单',
}

function initialPresentation(viewType: ViewType, fields: SafeViewField[]): ViewPresentationCommand {
  const visibleFieldKeys = fields.map((field) => field.key)
  if (viewType === 'kanban') return { view_type: 'kanban', visible_field_keys: visibleFieldKeys, filters: [], sort_rules: [], group_by_field_key: fields.find((field) => field.groupable)?.key ?? '' }
  if (viewType === 'calendar') return { view_type: 'calendar', visible_field_keys: visibleFieldKeys, filters: [], sort_rules: [], date_field_key: fields.find((field) => field.field_type === 'date')?.key ?? '' }
  if (viewType === 'form') return { view_type: 'form', visible_field_keys: visibleFieldKeys, form_field_keys: fields.filter((field) => field.form_eligible).map((field) => field.key) }
  return { view_type: 'grid', visible_field_keys: visibleFieldKeys, filters: [], sort_rules: [], group_by_field_key: null }
}

function presentationCommand(builder: ViewBuilderResponse): ViewPresentationCommand {
  const { presentation } = builder
  if (presentation.view_type === 'kanban') return { view_type: 'kanban', visible_field_keys: presentation.visible_field_keys, filters: presentation.filters, sort_rules: presentation.sort_rules, group_by_field_key: presentation.group_by_field_key ?? '' }
  if (presentation.view_type === 'calendar') return { view_type: 'calendar', visible_field_keys: presentation.visible_field_keys, filters: presentation.filters, sort_rules: presentation.sort_rules, date_field_key: presentation.date_field_key ?? '' }
  if (presentation.view_type === 'form') return { view_type: 'form', visible_field_keys: presentation.visible_field_keys, form_field_keys: presentation.form_field_keys }
  return { view_type: 'grid', visible_field_keys: presentation.visible_field_keys, filters: presentation.filters, sort_rules: presentation.sort_rules, group_by_field_key: presentation.group_by_field_key }
}

function moveKey(keys: string[], key: string, delta: -1 | 1): string[] {
  const index = keys.indexOf(key)
  const target = index + delta
  if (index < 0 || target < 0 || target >= keys.length) return keys
  const next = [...keys]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}

function presentationIsReady(presentation: ViewPresentationCommand): boolean {
  if (presentation.view_type === 'kanban') return Boolean(presentation.group_by_field_key)
  if (presentation.view_type === 'calendar') return Boolean(presentation.date_field_key)
  if (presentation.view_type === 'form') return presentation.form_field_keys.length > 0
  return true
}

export function ViewBuilderPanel({ context, builder: suppliedBuilder, onCreate, onSave, onReplaceMembers, onClose, loadRelationCandidates }: ViewBuilderPanelProps) {
  const firstInputRef = useRef<HTMLInputElement>(null)
  const attemptKeyRef = useRef<string | null>(null)
  const [createdBuilder, setCreatedBuilder] = useState<ViewBuilderResponse>()
  const [name, setName] = useState(suppliedBuilder?.view.name ?? '')
  const [draft, setDraft] = useState<ViewPresentationCommand>(() => suppliedBuilder ? presentationCommand(suppliedBuilder) : initialPresentation('grid', context.fields))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAccess, setShowAccess] = useState(false)
  const activeBuilder = suppliedBuilder ?? createdBuilder
  const fields = activeBuilder?.fields ?? context.fields
  const canEdit = activeBuilder ? activeBuilder.can_edit_presentation : true

  useEffect(() => {
    firstInputRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!suppliedBuilder) return
    setName(suppliedBuilder.view.name)
    setDraft(presentationCommand(suppliedBuilder))
  }, [suppliedBuilder])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && !saving) onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose, saving])

  function updateVisibleField(key: string, included: boolean) {
    setDraft((current) => {
      const visible = included ? [...current.visible_field_keys, key] : current.visible_field_keys.filter((item) => item !== key)
      if (current.view_type === 'form') {
        return { ...current, visible_field_keys: visible, form_field_keys: current.form_field_keys.filter((item) => item !== key) }
      }
      return { ...current, visible_field_keys: visible }
    })
  }

  function moveVisibleField(key: string, delta: -1 | 1) {
    setDraft((current) => {
      const visible = moveKey(current.visible_field_keys, key, delta)
      if (current.view_type === 'form') return { ...current, visible_field_keys: visible, form_field_keys: moveKey(current.form_field_keys, key, delta) }
      return { ...current, visible_field_keys: visible }
    })
  }

  function updateFormField(key: string, included: boolean) {
    setDraft((current) => current.view_type === 'form'
      ? { ...current, form_field_keys: included ? [...current.form_field_keys, key] : current.form_field_keys.filter((item) => item !== key) }
      : current)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedName = name.trim()
    if (!normalizedName) return setError('请输入视图名称。')
    if (normalizedName.length > 160) return setError('视图名称不能超过 160 个字符。')
    if (!presentationIsReady(draft)) return setError(draft.view_type === 'kanban' ? '请先选择看板分组字段。' : draft.view_type === 'calendar' ? '请先选择日历日期字段。' : '请至少选择一个表单字段。')
    if (saving || !canEdit) return
    setSaving(true)
    setError(null)
    try {
      if (activeBuilder) {
        const next = await onSave({ expected_version: activeBuilder.version, name: normalizedName, presentation: draft })
        setCreatedBuilder(next)
        setName(next.view.name)
        setDraft(presentationCommand(next))
      } else {
        const idempotencyKey = attemptKeyRef.current ?? crypto.randomUUID()
        attemptKeyRef.current = idempotencyKey
        const next = await onCreate({ name: normalizedName, view_type: draft.view_type, presentation: draft }, idempotencyKey)
        setCreatedBuilder(next)
        setName(next.view.name)
        setDraft(presentationCommand(next))
        setShowAccess(true)
      }
    } catch (caught) {
      setError(toSafeViewError(caught))
    } finally {
      setSaving(false)
    }
  }

  if (showAccess && activeBuilder) return <ViewAccessPanel builder={activeBuilder} candidates={context.member_candidates} onSave={onReplaceMembers} onClose={() => setShowAccess(false)} />

  const title = activeBuilder ? '编辑视图' : '新建视图'
  return <div className="view-builder-backdrop" role="presentation">
    <aside className="view-builder-panel" aria-labelledby="view-builder-title" aria-modal="true" role="dialog">
      <header className="view-builder-header"><div className="view-builder-heading"><span className="view-builder-icon"><Columns3 size={17} /></span><div><p>VIEW BUILDER</p><h2 id="view-builder-title">{title}</h2></div></div><button className="field-builder-close" type="button" aria-label="关闭视图配置" onClick={onClose} disabled={saving}><X size={18} /></button></header>
      {!activeBuilder ? <p className="view-builder-private-note">创建后默认仅自己可见</p> : <p className="field-builder-intro">编辑结果由服务端规范化并重新读取；本地不会提交乐观视图配置。</p>}
      <form className="view-builder-form" onSubmit={submit} noValidate>
        <section className="view-builder-section"><header><div><p>基础信息</p><h3>视图配置</h3></div></header><label><span>视图名称</span><input ref={firstInputRef} aria-label="视图名称" value={name} onChange={(event) => setName(event.target.value)} disabled={saving || !canEdit} /></label><label><span>视图类型</span><select aria-label="视图类型" value={draft.view_type} disabled={saving || Boolean(activeBuilder)} onChange={(event) => setDraft(initialPresentation(event.target.value as ViewType, fields))}>{(Object.keys(viewTypeLabels) as ViewType[]).map((viewType) => <option key={viewType} value={viewType}>{viewTypeLabels[viewType]}</option>)}</select></label></section>

        <section className="view-builder-section" aria-labelledby="view-fields-title"><header><div><p>显示</p><h3 id="view-fields-title">可见字段</h3></div></header><div className="view-builder-field-list">{fields.map((field) => {
          const visibleIndex = draft.visible_field_keys.indexOf(field.key)
          const visible = visibleIndex >= 0
          const formSelected = draft.view_type === 'form' && draft.form_field_keys.includes(field.key)
          return <div className="view-builder-field-row" key={field.key}><label><input aria-label={`显示 ${field.label}`} type="checkbox" checked={visible} disabled={saving || !canEdit} onChange={(event) => updateVisibleField(field.key, event.target.checked)} /><span>{field.label}</span><small>{field.field_type}</small></label>{visible ? <div className="view-builder-move"><button type="button" aria-label={`上移 ${field.label}`} disabled={saving || !canEdit || visibleIndex === 0} onClick={() => moveVisibleField(field.key, -1)}><ChevronUp size={14} /></button><button type="button" aria-label={`下移 ${field.label}`} disabled={saving || !canEdit || visibleIndex === draft.visible_field_keys.length - 1} onClick={() => moveVisibleField(field.key, 1)}><ChevronDown size={14} /></button></div> : null}{draft.view_type === 'form' ? <label className="view-builder-form-field"><input aria-label={`表单包含 ${field.label}`} type="checkbox" checked={formSelected} disabled={saving || !canEdit || !field.form_eligible || !visible} onChange={(event) => updateFormField(field.key, event.target.checked)} /><span>用于表单</span></label> : null}</div>
        })}</div></section>

        {draft.view_type === 'form' ? <p className="view-query-hint">表单仅允许写入权限范围内且已显示的字段。</p> : <ViewQueryControls presentation={draft} fields={fields} memberCandidates={context.member_candidates} onChange={setDraft} disabled={saving || !canEdit} loadRelationCandidates={loadRelationCandidates} />}
        {error ? <p className="field-builder-error" role="alert">{error}</p> : null}
        <p className="view-builder-live" aria-live="polite">{saving ? activeBuilder ? '正在保存视图…' : '正在创建私有视图…' : ''}</p>
        <footer className="field-builder-actions"><button type="button" className="button-secondary" onClick={onClose} disabled={saving}>取消</button>{activeBuilder?.can_replace_members ? <button type="button" className="button-secondary" onClick={() => setShowAccess(true)} disabled={saving}>管理访问权限</button> : null}<button type="submit" className="button-primary" disabled={saving || !canEdit}>{saving ? '保存中…' : activeBuilder ? '保存视图' : '创建私有视图'}</button></footer>
      </form>
    </aside>
  </div>
}
