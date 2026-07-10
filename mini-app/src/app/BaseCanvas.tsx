import { ArrowLeft, ChevronDown, MoreHorizontal, Plus, Table2 } from 'lucide-react'

import type { BaseSummary, PlatformTable, TableSchema, ViewPresentation, ViewRecords, ViewSummary } from './api'

type BaseCanvasProps = { base: BaseSummary; tables: PlatformTable[]; views: ViewSummary[]; table: PlatformTable | null; view: ViewSummary | null; schema: TableSchema | null; records: ViewRecords | null; presentation: ViewPresentation | null; onBack: () => void; onOpenRecord: (recordId: string) => void; onSelectView: (viewId: string) => void }

export function BaseCanvas({ base, tables: _tables, views, table, view, schema, records, presentation, onBack, onOpenRecord, onSelectView }: BaseCanvasProps) {
  if (!table || !view || !schema || !records || !presentation) return <main className="base-canvas empty-canvas" aria-label="Base 工作台"><button className="back-link" type="button" onClick={onBack}><ArrowLeft size={16} /> 返回工作区</button><h1>{base.name}</h1><p>这个 Base 还没有可访问的表或保存视图。</p></main>
  return <main className="base-canvas" aria-label="Base 工作台">
    <header className="canvas-header"><button className="back-link" type="button" onClick={onBack}><ArrowLeft size={16} /> 工作区</button><span className="canvas-separator">/</span><h1>{base.name}</h1><button className="icon-button" aria-label="更多 Base 操作" type="button"><MoreHorizontal size={19} /></button></header>
    <div className="canvas-table-tabs"><button className="table-tab active" type="button"><Table2 size={16} />{table.name}<ChevronDown size={14} /></button><button className="add-table" type="button" aria-label="新建表"><Plus size={16} /></button></div>
    <div className="view-toolbar"><div role="tablist" aria-label="保存视图">{views.filter((item) => item.table_id === table.id).map((item) => <button role="tab" aria-selected={item.id === view.id} className={item.id === view.id ? 'view-tab active' : 'view-tab'} type="button" key={item.id} onClick={() => onSelectView(item.id)}>{item.name}</button>)}</div><div className="view-tools"><button type="button">筛选</button><button type="button">排序</button><button type="button">分组</button></div></div>
    <ViewSurface presentation={presentation} schema={schema} records={records} onOpenRecord={onOpenRecord} />
  </main>
}

type Field = TableSchema['fields'][number]
type RecordsProps = { fields: Field[]; records: ViewRecords; onOpenRecord: (recordId: string) => void }

function ViewSurface({ presentation, schema, records, onOpenRecord }: { presentation: ViewPresentation; schema: TableSchema; records: ViewRecords; onOpenRecord: (recordId: string) => void }) {
  const fields = schema.fields.filter((field) => presentation.visible_field_keys.includes(field.key))
  if (presentation.view_type === 'kanban') return <KanbanSurface fields={fields} records={records} groupBy={presentation.group_by_field_key} onOpenRecord={onOpenRecord} />
  if (presentation.view_type === 'calendar') return <CalendarSurface fields={fields} records={records} dateField={presentation.date_field_key} onOpenRecord={onOpenRecord} />
  if (presentation.view_type === 'form') return <FormSurface fields={fields} record={records.records[0]} formFieldKeys={presentation.form_field_keys} onOpenRecord={onOpenRecord} />
  return <GridSurface fields={fields} records={records} onOpenRecord={onOpenRecord} />
}

function GridSurface({ fields, records, onOpenRecord }: RecordsProps) {
  return <><div className="grid-scroll"><table className="record-grid"><thead><tr><th aria-label="选择记录" /><th scope="col">#</th>{fields.map((field) => <th scope="col" key={field.id}>{field.name}</th>)}</tr></thead><tbody>{records.records.map((record, index) => <tr key={record.id} onClick={() => onOpenRecord(record.id)}><td><span className="row-check" /></td><td>{index + 1}</td>{fields.map((field) => <td key={field.id}>{displayCell(record.fields[field.key])}</td>)}</tr>)}</tbody></table></div>{records.records.length === 0 && <div className="grid-empty">当前视图没有可访问记录。</div>}</>
}

function KanbanSurface({ fields, records, groupBy, onOpenRecord }: RecordsProps & { groupBy: string | null }) {
  const groups = new Map<string, typeof records.records>()
  for (const record of records.records) { const key = groupBy ? displayCell(record.fields[groupBy]) || '未分组' : '未分组'; groups.set(key, [...(groups.get(key) ?? []), record]) }
  return <div className="kanban-surface">{[...groups.entries()].map(([name, items]) => <section className="kanban-column" key={name}><header><strong>{name}</strong><span>{items.length}</span></header>{items.map((record) => <button type="button" key={record.id} onClick={() => onOpenRecord(record.id)}>{fields.slice(0, 3).map((field) => <span key={field.id}><small>{field.name}</small>{displayCell(record.fields[field.key])}</span>)}</button>)}</section>)}</div>
}

function CalendarSurface({ fields, records, dateField, onOpenRecord }: RecordsProps & { dateField: string | null }) {
  const groups = new Map<string, typeof records.records>()
  for (const record of records.records) { const key = dateField ? displayCell(record.fields[dateField]) || '未排期' : '未排期'; groups.set(key, [...(groups.get(key) ?? []), record]) }
  return <div className="calendar-surface">{[...groups.entries()].map(([date, items]) => <section key={date}><h2>{date}</h2>{items.map((record) => <button type="button" key={record.id} onClick={() => onOpenRecord(record.id)}>{fields.map((field) => <span key={field.id}>{displayCell(record.fields[field.key])}</span>)}</button>)}</section>)}</div>
}

function FormSurface({ fields, record, formFieldKeys, onOpenRecord }: { fields: Field[]; record: ViewRecords['records'][number] | undefined; formFieldKeys: string[]; onOpenRecord: (recordId: string) => void }) {
  if (!record) return <div className="grid-empty">当前表单没有可访问记录。</div>
  return <form className="record-form" onSubmit={(event) => event.preventDefault()}>{fields.filter((field) => formFieldKeys.includes(field.key)).map((field) => <label key={field.id}>{field.name}<output>{displayCell(record.fields[field.key])}</output></label>)}<button type="button" onClick={() => onOpenRecord(record.id)}>查看记录详情</button></form>
}

function displayCell(value: unknown): string { if (value === null || value === undefined) return ''; return typeof value === 'string' ? value : JSON.stringify(value) }
