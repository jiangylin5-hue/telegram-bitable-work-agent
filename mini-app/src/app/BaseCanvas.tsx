import { ArrowLeft, ChevronDown, MoreHorizontal, Plus, Table2 } from 'lucide-react'

import type { BaseSummary, PlatformTable, TableSchema, ViewRecords, ViewSummary } from './api'

type BaseCanvasProps = {
  base: BaseSummary
  table: PlatformTable | null
  view: ViewSummary | null
  schema: TableSchema | null
  records: ViewRecords | null
  onBack: () => void
}

export function BaseCanvas({ base, table, view, schema, records, onBack }: BaseCanvasProps) {
  if (!table || !view || !schema || !records) {
    return <main className="base-canvas empty-canvas" aria-label="Base 工作台"><button className="back-link" type="button" onClick={onBack}><ArrowLeft size={16} /> 返回工作区</button><h1>{base.name}</h1><p>这个 Base 还没有可访问的表或保存视图。</p></main>
  }

  return <main className="base-canvas" aria-label="Base 工作台">
    <header className="canvas-header"><button className="back-link" type="button" onClick={onBack}><ArrowLeft size={16} /> 工作区</button><span className="canvas-separator">/</span><h1>{base.name}</h1><button className="icon-button" aria-label="更多 Base 操作" type="button"><MoreHorizontal size={19} /></button></header>
    <div className="canvas-table-tabs"><button className="table-tab active" type="button"><Table2 size={16} />{table.name}<ChevronDown size={14} /></button><button className="add-table" type="button" aria-label="新建表"><Plus size={16} /></button></div>
    <div className="view-toolbar"><div role="tablist" aria-label="保存视图"><button role="tab" aria-selected="true" className="view-tab" type="button">{view.name}</button></div><div className="view-tools"><button type="button">筛选</button><button type="button">排序</button><button type="button">分组</button></div></div>
    <div className="grid-scroll"><table className="record-grid"><thead><tr><th aria-label="选择记录" /><th scope="col">#</th>{schema.fields.map((field) => <th scope="col" key={field.id}>{field.name}</th>)}</tr></thead><tbody>{records.records.map((record, index) => <tr key={record.id}><td><span className="row-check" /></td><td>{index + 1}</td>{schema.fields.map((field) => <td key={field.id}>{displayCell(record.fields[field.key])}</td>)}</tr>)}</tbody></table></div>
    {records.records.length === 0 && <div className="grid-empty">当前视图没有可访问记录。</div>}
  </main>
}

function displayCell(value: unknown): string {
  if (value === null || value === undefined) return ''
  return typeof value === 'string' ? value : JSON.stringify(value)
}
