import { type KeyboardEvent as ReactKeyboardEvent, type MouseEvent, useEffect, useRef, useState } from 'react'
import { ArrowLeft, ChevronDown, MoreHorizontal, Plus, Table2 } from 'lucide-react'

import type { BaseSummary, BusinessContextRelation, PlatformTable, TableSchema, ViewPresentation, ViewRecords, ViewSummary } from './api'
import { RelationChips, relationLabels } from './RelationChips'

type BaseCanvasProps = { base: BaseSummary; tables: PlatformTable[]; views: ViewSummary[]; table: PlatformTable | null; view: ViewSummary | null; schema: TableSchema | null; records: ViewRecords | null; presentation: ViewPresentation | null; loadingMore?: boolean; loadMoreError?: boolean; serverQuerySummary?: string; businessContextRelations?: BusinessContextRelation[]; onBack: () => void; onOpenRecord: (recordId: string) => void; onOpenRecordReference?: (reference: BusinessContextRelation['customer']) => void; onOpenEmployeeReference?: (trigger: HTMLElement, employee: BusinessContextRelation['employee']) => void; onOpenAssistantContext?: (trigger: HTMLElement) => void; onSelectTable?: (tableId: string) => void; onSelectView: (viewId: string) => void; onLoadMore?: (cursor: string) => void; onCreateRecord?: () => void; canManageSchema?: boolean; canCreateViews?: boolean; canManageViews?: boolean; canCreateRecords?: boolean; canManageDigitalEmployees?: boolean; onCreateTable?: () => void; onCreateField?: () => void; onCreateView?: () => void; onConfigureView?: () => void; onSaveTemplate?: () => void; onImportIntoBase?: (trigger: HTMLElement) => void; onOpenTableOperations?: (trigger: HTMLElement) => void; onOpenCollaboration?: (trigger: HTMLElement) => void; onOpenDraftHub?: (trigger: HTMLElement) => void; onOpenDigitalEmployeeManagement?: (trigger: HTMLElement) => void }

export function BaseCanvas({ base, tables, views, table, view, schema, records, presentation, loadingMore, loadMoreError, serverQuerySummary, businessContextRelations = [], onBack, onOpenRecord, onOpenRecordReference, onOpenEmployeeReference, onOpenAssistantContext, onSelectTable, onSelectView, onLoadMore, onCreateRecord, canManageSchema = false, canCreateViews = false, canManageViews = false, canCreateRecords = false, canManageDigitalEmployees = false, onCreateTable, onCreateField, onCreateView, onConfigureView, onSaveTemplate, onImportIntoBase, onOpenTableOperations, onOpenCollaboration, onOpenDraftHub, onOpenDigitalEmployeeManagement }: BaseCanvasProps) {
  const [objectMenu, setObjectMenu] = useState<{ kind: 'base' | 'table'; trigger: HTMLElement; x: number; y: number } | null>(null)
  const [recordContextMenu, setRecordContextMenu] = useState<{ recordId: string; x: number; y: number } | null>(null)
  const objectMenuRef = useRef<HTMLDivElement>(null)
  const recordContextTrigger = useRef<HTMLElement | null>(null)
  const recordContextMenuRef = useRef<HTMLDivElement>(null)
  const baseRelations = businessContextRelations.filter((relation) => relation.employee.base_id === base.id || relation.customer.base_id === base.id || relation.project.base_id === base.id)

  function closeRecordContextMenu() {
    setRecordContextMenu(null)
    const trigger = recordContextTrigger.current
    recordContextTrigger.current = null
    queueMicrotask(() => trigger?.focus())
  }

  function openRecordContextMenu(event: MouseEvent<HTMLElement> | ReactKeyboardEvent<HTMLElement>, recordId: string) {
    event.preventDefault()
    recordContextTrigger.current = event.currentTarget
    const pointerEvent = 'clientX' in event ? event : null
    setRecordContextMenu({ recordId, x: pointerEvent?.clientX ?? 24, y: pointerEvent?.clientY ?? 24 })
  }

  function openBaseMenu(event: MouseEvent<HTMLElement>) {
    event.preventDefault()
    const rect = event.currentTarget.getBoundingClientRect()
    setObjectMenu({
      kind: 'base',
      trigger: event.currentTarget,
      x: event.clientX || rect.left,
      y: event.clientY || rect.bottom,
    })
  }

  function openTableMenu(event: MouseEvent<HTMLElement> | ReactKeyboardEvent<HTMLElement>) {
    event.preventDefault()
    const rect = event.currentTarget.getBoundingClientRect()
    const pointerEvent = 'clientX' in event ? event : null
    setObjectMenu({
      kind: 'table',
      trigger: event.currentTarget,
      x: pointerEvent?.clientX || rect.left,
      y: pointerEvent?.clientY || rect.bottom,
    })
  }

  function closeObjectMenu() {
    const trigger = objectMenu?.trigger
    setObjectMenu(null)
    queueMicrotask(() => trigger?.focus())
  }

  useEffect(() => {
    if (!objectMenu) return
    objectMenuRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeObjectMenu()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [objectMenu])

  useEffect(() => {
    if (!recordContextMenu) return
    recordContextMenuRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeRecordContextMenu()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [recordContextMenu])

  if (!table || !view || !schema || !records || !presentation) return <main className="base-canvas empty-canvas" aria-label="Base 工作台"><button className="back-link" type="button" onClick={onBack}><ArrowLeft size={16} /> 返回工作区</button><h1>{base.name}</h1><p>这个 Base 还没有可访问的表或保存视图。</p></main>
  return <main className="base-canvas" aria-label="Base 工作台">
    <header className="canvas-header"><button className="back-link" type="button" onClick={onBack}><ArrowLeft size={16} /> 工作区</button><span className="canvas-separator">/</span><h1 onContextMenu={openBaseMenu}>{base.name}</h1>{onOpenTableOperations ? <button className="canvas-operation-center-button" type="button" onClick={(event) => onOpenTableOperations(event.currentTarget)}>表格操作</button> : null}{canManageSchema && (onSaveTemplate || onImportIntoBase) ? <div className="base-more-actions"><button className="icon-button" aria-label="更多 Base 操作" aria-expanded={objectMenu?.kind === 'base'} type="button" onClick={openBaseMenu}><MoreHorizontal size={19} /></button></div> : null}</header>
    <div className="canvas-table-tabs" role="tablist" aria-label="数据表">{tables.map((item) => <div role="presentation" className={item.id === table.id ? 'table-tab-shell active' : 'table-tab-shell'} key={item.id}><button role="tab" aria-selected={item.id === table.id} className="table-tab" type="button" onClick={() => onSelectTable?.(item.id)} onContextMenu={openTableMenu} onKeyDown={(event) => { if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) openTableMenu(event) }}><Table2 size={16} />{item.name}</button><button className="table-tab-menu-trigger" type="button" aria-label={`更多 ${item.name} 操作`} aria-expanded={objectMenu?.kind === 'table'} onClick={openTableMenu}><ChevronDown size={14} /></button></div>)}{canManageSchema && onCreateTable && <button className="add-table" type="button" aria-label="新建表" onClick={onCreateTable}><Plus size={16} /></button>}</div>
    <div className="view-toolbar"><div role="tablist" aria-label="保存视图">{views.filter((item) => item.table_id === table.id).map((item) => <button role="tab" aria-selected={item.id === view.id} className={item.id === view.id ? 'view-tab active' : 'view-tab'} type="button" key={item.id} onClick={() => onSelectView(item.id)}>{item.name}</button>)}</div><div className="view-tools">{serverQuerySummary ? <output className="view-query-summary" aria-label="服务器查询摘要">{serverQuerySummary}</output> : null}{onOpenCollaboration ? <button className="open-collaboration" type="button" onClick={(event) => onOpenCollaboration(event.currentTarget)}>AI 对话</button> : null}{canManageDigitalEmployees && onOpenDigitalEmployeeManagement ? <button className="open-employee-management" type="button" onClick={(event) => onOpenDigitalEmployeeManagement(event.currentTarget)}>数字员工管理</button> : null}{onOpenDraftHub ? <button className="open-employee-hub" type="button" onClick={(event) => onOpenDraftHub(event.currentTarget)}>数字员工</button> : null}{canManageViews && onConfigureView ? <button className="configure-view-button" type="button" onClick={onConfigureView}>配置视图</button> : null}{canCreateViews && onCreateView ? <button className="create-view-button" type="button" onClick={onCreateView}>新建视图</button> : null}{canManageSchema && onCreateField ? <button className="add-field-button" type="button" onClick={onCreateField}>添加字段</button> : null}{canCreateRecords && schema.fields.length > 0 && onCreateRecord ? <button className="create-record-button" type="button" onClick={onCreateRecord}>新建记录</button> : null}</div></div>
    <div className="base-workbench-body" data-workbench-layout="table-context">
      <div className="base-workbench-main">
        {presentation.view_type === 'grid' && schema.fields.length === 0 ? <div className="grid-empty grid-empty-onboarding" role="status"><p>此数据表尚未添加字段。</p><span>先导入 Excel/CSV，或从零创建第一列。</span>{canManageSchema && (onImportIntoBase || onCreateField) ? <div className="grid-empty-actions">{onImportIntoBase ? <button className="import-first-data-button" type="button" onClick={(event) => onImportIntoBase(event.currentTarget)}>从 Excel/CSV 导入</button> : null}{onCreateField ? <button className="add-first-field-button" type="button" onClick={onCreateField}>添加第一个字段</button> : null}</div> : null}</div> : <ViewSurface presentation={presentation} schema={schema} records={records} onOpenRecord={onOpenRecord} onOpenRecordContextMenu={openRecordContextMenu} />}
        {records.has_more && records.next_cursor && onLoadMore && <div className="record-pagination"><button type="button" disabled={loadingMore} onClick={() => onLoadMore(records.next_cursor!)}>{loadingMore ? '正在加载…' : '加载更多记录'}</button>{loadMoreError && <p role="alert">加载失败，请重试。</p>}</div>}
      </div>
      <aside className="base-workbench-context" data-testid="base-workbench-context" aria-label="当前表格上下文">
        <header><p>CONTEXT</p><h2>当前工作范围</h2></header>
        <dl><div><dt>Base</dt><dd>{base.name}</dd></div><div><dt>数据表</dt><dd>{table.name}</dd></div><div><dt>保存视图</dt><dd>{view.name}</dd></div><div><dt>可访问记录</dt><dd>{records.records.length} 条可访问记录</dd></div><div><dt>可见字段</dt><dd>{schema.fields.length} 个字段</dd></div></dl>
        <p>该侧栏只显示当前已授权的 Base、表、视图和计数，不读取或推断群聊、客户或隐藏记录。</p>
      </aside>
    </div>
    {baseRelations.length > 0 ? <section className="workbench-business-context" data-testid="base-business-context" aria-label="当前 Base 的已授权业务关联"><header><p>BUSINESS CONTEXT</p><h2>已授权业务关联</h2></header>{baseRelations.map((relation) => <div key={`${relation.group.id}:${relation.mapping_version}`}>
      {onOpenEmployeeReference ? <button type="button" aria-label={`打开数字员工 ${relation.employee.name}`} onClick={(event) => onOpenEmployeeReference(event.currentTarget, relation.employee)}>{relation.employee.name}</button> : <strong>{relation.employee.name}</strong>}
      {onOpenAssistantContext ? <button type="button" aria-label={`查看群聊上下文 ${relation.group.label}`} onClick={(event) => onOpenAssistantContext(event.currentTarget)}>{relation.group.label}</button> : <span>{relation.group.label}</span>}
      {onOpenRecordReference ? <button type="button" aria-label={`打开客户记录 ${relation.customer.label}`} onClick={() => onOpenRecordReference(relation.customer)}>客户 · {relation.customer.label}</button> : <span>客户 · {relation.customer.label}</span>}
      {onOpenRecordReference ? <button type="button" aria-label={`打开项目记录 ${relation.project.label}`} onClick={() => onOpenRecordReference(relation.project)}>项目 · {relation.project.label}</button> : <span>项目 · {relation.project.label}</span>}
    </div>)}</section> : null}
    {objectMenu ? <div className="record-context-backdrop" role="presentation" onMouseDown={closeObjectMenu}>
      <div ref={objectMenuRef} className="record-context-menu" role="menu" aria-label={objectMenu.kind === 'base' ? 'Base 操作' : '数据表操作'} tabIndex={-1} style={{ left: objectMenu.x, top: objectMenu.y }} onMouseDown={(event) => event.stopPropagation()}>
        {objectMenu.kind === 'base' && onImportIntoBase ? <button type="button" role="menuitem" onClick={() => { const trigger = objectMenu.trigger; closeObjectMenu(); onImportIntoBase(trigger) }}>导入到当前 Base</button> : null}
        {objectMenu.kind === 'base' && onSaveTemplate ? <button type="button" role="menuitem" onClick={() => { closeObjectMenu(); onSaveTemplate() }}>保存为模板</button> : null}
        {objectMenu.kind === 'base' && onOpenTableOperations ? <button type="button" role="menuitem" onClick={() => { const trigger = objectMenu.trigger; closeObjectMenu(); onOpenTableOperations(trigger) }}>表格操作</button> : null}
        {objectMenu.kind === 'table' && onOpenTableOperations ? <button type="button" role="menuitem" onClick={() => { const trigger = objectMenu.trigger; closeObjectMenu(); onOpenTableOperations(trigger) }}>表格操作</button> : null}
        {objectMenu.kind === 'table' && canCreateRecords && onCreateRecord ? <button type="button" role="menuitem" onClick={() => { closeObjectMenu(); onCreateRecord() }}>新建记录</button> : null}
        {objectMenu.kind === 'table' && canManageSchema && onCreateField ? <button type="button" role="menuitem" onClick={() => { closeObjectMenu(); onCreateField() }}>添加字段</button> : null}
        <button type="button" role="menuitem" disabled aria-label={objectMenu.kind === 'base' ? '复制或归档 Base（即将上线）' : '复制或归档数据表（即将上线）'}>{objectMenu.kind === 'base' ? '复制或归档 Base（即将上线）' : '复制或归档数据表（即将上线）'}</button>
      </div>
    </div> : null}
    {recordContextMenu ? <div className="record-context-backdrop" role="presentation" onMouseDown={closeRecordContextMenu}>
      <div ref={recordContextMenuRef} className="record-context-menu" role="menu" aria-label="记录操作" tabIndex={-1} style={{ left: recordContextMenu.x, top: recordContextMenu.y }} onMouseDown={(event) => event.stopPropagation()}>
        <button type="button" role="menuitem" onClick={() => { const recordId = recordContextMenu.recordId; closeRecordContextMenu(); onOpenRecord(recordId) }}>查看记录详情</button>
        <button type="button" role="menuitem" disabled aria-label="复制或归档记录（即将上线）">复制或归档记录（即将上线）</button>
      </div>
    </div> : null}
  </main>
}

type Field = TableSchema['fields'][number]
type RecordsProps = { fields: Field[]; allFields: Field[]; records: ViewRecords; onOpenRecord: (recordId: string) => void; onOpenRecordContextMenu: (event: MouseEvent<HTMLElement> | ReactKeyboardEvent<HTMLElement>, recordId: string) => void }

function ViewSurface({ presentation, schema, records, onOpenRecord, onOpenRecordContextMenu }: { presentation: ViewPresentation; schema: TableSchema; records: ViewRecords; onOpenRecord: (recordId: string) => void; onOpenRecordContextMenu: (event: MouseEvent<HTMLElement> | ReactKeyboardEvent<HTMLElement>, recordId: string) => void }) {
  const fields = schema.fields.filter((field) => presentation.visible_field_keys.includes(field.key))
  if (presentation.view_type === 'kanban') return <KanbanSurface fields={fields} allFields={schema.fields} records={records} groupBy={presentation.group_by_field_key} onOpenRecord={onOpenRecord} onOpenRecordContextMenu={onOpenRecordContextMenu} />
  if (presentation.view_type === 'calendar') return <CalendarSurface fields={fields} allFields={schema.fields} records={records} dateField={presentation.date_field_key} onOpenRecord={onOpenRecord} onOpenRecordContextMenu={onOpenRecordContextMenu} />
  if (presentation.view_type === 'form') return <FormSurface fields={fields} allFields={schema.fields} record={records.records[0]} formFieldKeys={presentation.form_field_keys} onOpenRecord={onOpenRecord} onOpenRecordContextMenu={onOpenRecordContextMenu} />
  return <GridSurface fields={fields} allFields={schema.fields} records={records} onOpenRecord={onOpenRecord} onOpenRecordContextMenu={onOpenRecordContextMenu} />
}

function GridSurface({ fields, records, onOpenRecord, onOpenRecordContextMenu }: RecordsProps) {
  return <section data-testid="view-grid"><div className="grid-scroll"><table className="record-grid"><thead><tr><th aria-label="选择记录" /><th scope="col">#</th>{fields.map((field) => <th scope="col" key={field.id}>{field.name}</th>)}</tr></thead><tbody>{records.records.map((record, index) => <tr key={record.id} tabIndex={0} onClick={() => onOpenRecord(record.id)} onContextMenu={(event) => onOpenRecordContextMenu(event, record.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onOpenRecord(record.id) } else if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) onOpenRecordContextMenu(event, record.id) }}><td><span className="row-check" /></td><td>{index + 1}</td>{fields.map((field) => <td key={field.id}>{displayCell(field, record.fields[field.key])}</td>)}</tr>)}</tbody></table></div>{records.records.length === 0 && <div className="grid-empty">当前视图没有可访问记录。</div>}</section>
}

function KanbanSurface({ fields, allFields, records, groupBy, onOpenRecord, onOpenRecordContextMenu }: RecordsProps & { groupBy: string | null }) {
  const groups = new Map<string, typeof records.records>()
  const groupField = allFields.find((field) => field.key === groupBy)
  for (const record of records.records) { const key = groupBy ? displayText(groupField, record.fields[groupBy]) || '未分组' : '未分组'; groups.set(key, [...(groups.get(key) ?? []), record]) }
  return <div className="kanban-surface" data-testid="view-kanban">{[...groups.entries()].map(([name, items]) => <section className="kanban-column" key={name}><header><strong>{name}</strong><span>{items.length}</span></header>{items.map((record) => <button type="button" key={record.id} onClick={() => onOpenRecord(record.id)} onContextMenu={(event) => onOpenRecordContextMenu(event, record.id)}>{fields.slice(0, 3).map((field) => <span key={field.id}><small>{field.name}</small>{displayCell(field, record.fields[field.key])}</span>)}</button>)}</section>)}</div>
}

function CalendarSurface({ fields, allFields, records, dateField, onOpenRecord, onOpenRecordContextMenu }: RecordsProps & { dateField: string | null }) {
  const groups = new Map<string, typeof records.records>()
  const dateFieldDefinition = allFields.find((field) => field.key === dateField)
  for (const record of records.records) { const key = dateField ? displayText(dateFieldDefinition, record.fields[dateField]) || '未排期' : '未排期'; groups.set(key, [...(groups.get(key) ?? []), record]) }
  return <div className="calendar-surface" data-testid="view-calendar">{[...groups.entries()].map(([date, items]) => <section key={date}><h2>{date}</h2>{items.map((record) => <button type="button" key={record.id} onClick={() => onOpenRecord(record.id)} onContextMenu={(event) => onOpenRecordContextMenu(event, record.id)}>{fields.map((field) => <span key={field.id}>{displayCell(field, record.fields[field.key])}</span>)}</button>)}</section>)}</div>
}

function FormSurface({ fields, record, formFieldKeys, onOpenRecord, onOpenRecordContextMenu }: { fields: Field[]; allFields: Field[]; record: ViewRecords['records'][number] | undefined; formFieldKeys: string[]; onOpenRecord: (recordId: string) => void; onOpenRecordContextMenu: (event: MouseEvent<HTMLElement> | ReactKeyboardEvent<HTMLElement>, recordId: string) => void }) {
  if (!record) return <div className="grid-empty">当前表单没有可访问记录。</div>
  return <form className="record-form" data-testid="view-form" onSubmit={(event) => event.preventDefault()}>{fields.filter((field) => formFieldKeys.includes(field.key)).map((field) => <label key={field.id}>{field.name}<output>{displayCell(field, record.fields[field.key])}</output></label>)}<button type="button" onClick={() => onOpenRecord(record.id)} onContextMenu={(event) => onOpenRecordContextMenu(event, record.id)}>查看记录详情</button></form>
}

function displayCell(field: Field, value: unknown) {
  if (field.field_type === 'linked_record') return <RelationChips value={value} />
  if (field.field_type === 'single_select' || field.field_type === 'multi_select' || field.field_type === 'status') return <SelectionChips fieldType={field.field_type} value={value} />
  return displayText(field, value)
}

function choiceValues(value: unknown): string[] {
  if (typeof value === 'string' && value.trim()) return [value]
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : []
}

function choiceTone(value: string): number {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) hash = (hash * 31 + value.charCodeAt(index)) % 6
  return hash
}

function SelectionChips({ fieldType, value }: { fieldType: string; value: unknown }) {
  const values = choiceValues(value)
  if (values.length === 0) return null
  return <span className="selection-chip-list" data-field-type={fieldType}>{values.map((item) => <span className={`selection-chip tone-${choiceTone(item)}`} key={item}>{item}</span>)}</span>
}

function displayText(field: Field | undefined, value: unknown): string {
  if (field?.field_type === 'linked_record') return relationLabels(value).join(', ')
  if (value === null || value === undefined) return ''
  return typeof value === 'string' ? value : JSON.stringify(value)
}
