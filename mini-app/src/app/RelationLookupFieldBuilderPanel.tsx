import { Columns3, Link2, Search, X } from 'lucide-react'
import { type FormEvent, useEffect, useRef, useState } from 'react'

import { ApiError, type LookupAggregation, type PlatformTable, type SafeTableField, type TableSchema } from './api'

export type F2FieldBuilderValues =
  | { kind: 'relation'; name: string; targetTableId: string; required: boolean }
  | { kind: 'lookup'; name: string; sourceRelationFieldId: string; targetFieldId: string; aggregation: LookupAggregation }

type TargetField = { table: PlatformTable; field: SafeTableField }

type RelationLookupFieldBuilderPanelProps = {
  currentTableId: string
  tables: PlatformTable[]
  schemas: TableSchema[]
  onSubmit: (values: F2FieldBuilderValues, idempotencyKey: string) => Promise<void>
  onClose: () => void
}

const basicLookupAggregations: LookupAggregation[] = ['values', 'count', 'count_distinct']
const allLookupAggregations: LookupAggregation[] = ['values', 'count', 'count_distinct', 'sum', 'average', 'min', 'max']
const aggregationLabels: Record<LookupAggregation, string> = {
  values: 'values',
  count: 'count',
  count_distinct: 'count_distinct',
  sum: 'sum',
  average: 'average',
  min: 'min',
  max: 'max',
}
const fixedErrorCopy: Record<string, string> = {
  duplicate_field_name: '字段名称已存在，请使用其他名称。',
  lookup_source_not_relation: '关联字段不可用于查找。',
  lookup_target_incompatible: '目标字段与聚合方式不兼容。',
  lookup_dependency_cycle: '查找字段不能形成循环依赖。',
  lookup_depth_exceeded: '查找字段最多支持两层。',
  relation_self_reference: '关联记录不能选择自身。',
  record_is_referenced: '该记录正在被关联使用。',
  field_has_dependencies: '该字段正被其他字段使用。',
}

function availableAggregations(field: SafeTableField | undefined): LookupAggregation[] {
  if (field?.field_type === 'number' || field?.field_type === 'lookup') return allLookupAggregations
  return basicLookupAggregations
}

function retryableSubmission(error: unknown): boolean {
  return !(error instanceof ApiError) || error.status >= 500
}

export function RelationLookupFieldBuilderPanel({ currentTableId, tables, schemas, onSubmit, onClose }: RelationLookupFieldBuilderPanelProps) {
  const firstInputRef = useRef<HTMLInputElement>(null)
  const attemptRef = useRef<{ fingerprint: string; key: string; retryable: boolean } | null>(null)
  const currentSchema = schemas.find((schema) => schema.table.id === currentTableId)
  const tablesById = new Map(tables.map((table) => [table.id, table]))
  const safeSchemas = schemas.filter((schema) => tablesById.has(schema.table.id))
  const relationTables = tables.filter((table) => safeSchemas.some((schema) => schema.table.id === table.id))
  const sourceRelations = currentSchema?.fields.filter((field) => field.field_type === 'linked_record') ?? []
  const targetFields: TargetField[] = safeSchemas.flatMap((schema) => {
    const table = tablesById.get(schema.table.id)
    if (!table) return []
    return schema.fields
      .filter((field) => !['linked_record', 'json', 'formula'].includes(field.field_type))
      .map((field) => ({ table, field }))
  })
  const [kind, setKind] = useState<F2FieldBuilderValues['kind']>('relation')
  const [name, setName] = useState('')
  const [targetTableId, setTargetTableId] = useState(relationTables[0]?.id ?? '')
  const [required, setRequired] = useState(false)
  const [sourceRelationFieldId, setSourceRelationFieldId] = useState(sourceRelations[0]?.id ?? '')
  const [targetFieldId, setTargetFieldId] = useState(targetFields[0]?.field.id ?? '')
  const selectedTargetField = targetFields.find((candidate) => candidate.field.id === targetFieldId)?.field
  const [aggregation, setAggregation] = useState<LookupAggregation>(availableAggregations(selectedTargetField)[0])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [conflicted, setConflicted] = useState(false)
  const disabled = saving || conflicted

  useEffect(() => {
    firstInputRef.current?.focus()
  }, [])

  function selectTargetField(nextTargetFieldId: string) {
    const nextField = targetFields.find((candidate) => candidate.field.id === nextTargetFieldId)?.field
    const nextAggregations = availableAggregations(nextField)
    setTargetFieldId(nextTargetFieldId)
    setAggregation((current) => nextAggregations.includes(current) ? current : nextAggregations[0])
  }

  function validate(): F2FieldBuilderValues | null {
    const normalizedName = name.trim()
    if (!normalizedName) {
      setError('请输入字段名称。')
      return null
    }
    if (normalizedName.length > 160) {
      setError('字段名称不能超过 160 个字符。')
      return null
    }
    if (kind === 'relation') {
      if (!targetTableId || !relationTables.some((table) => table.id === targetTableId)) {
        setError('请选择关联目标表。')
        return null
      }
      return { kind, name: normalizedName, targetTableId, required }
    }
    if (!sourceRelationFieldId || !sourceRelations.some((field) => field.id === sourceRelationFieldId)) {
      setError('请选择关联字段。')
      return null
    }
    if (!targetFieldId || !targetFields.some((candidate) => candidate.field.id === targetFieldId)) {
      setError('请选择目标字段。')
      return null
    }
    if (!availableAggregations(selectedTargetField).includes(aggregation)) {
      setError('请选择固定聚合方式。')
      return null
    }
    return { kind, name: normalizedName, sourceRelationFieldId, targetFieldId, aggregation }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = validate()
    if (!values) return

    const fingerprint = JSON.stringify(values)
    const previousAttempt = attemptRef.current
    const idempotencyKey = previousAttempt?.retryable && previousAttempt.fingerprint === fingerprint
      ? previousAttempt.key
      : crypto.randomUUID()
    attemptRef.current = { fingerprint, key: idempotencyKey, retryable: false }
    setSaving(true)
    setError(null)
    try {
      await onSubmit(values, idempotencyKey)
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setError('创建请求发生冲突，请关闭后重新创建。')
        setConflicted(true)
      } else if (retryableSubmission(caught)) {
        attemptRef.current = { fingerprint, key: idempotencyKey, retryable: true }
        setError('创建失败，请稍后重试。')
      } else if (caught instanceof ApiError && caught.code && fixedErrorCopy[caught.code]) {
        attemptRef.current = null
        setError(fixedErrorCopy[caught.code])
      } else {
        attemptRef.current = null
        setError('创建失败，请稍后重试。')
      }
    } finally {
      setSaving(false)
    }
  }

  if (safeSchemas.length === 0) {
    return <div className="field-builder-backdrop" role="presentation">
      <aside className="field-builder-panel relation-lookup-builder-panel" aria-labelledby="relation-lookup-builder-title" aria-modal="true" role="dialog">
        <header className="field-builder-header"><div className="field-builder-heading"><span className="field-builder-icon"><Columns3 size={17} /></span><div><p>关系字段</p><h2 id="relation-lookup-builder-title">添加关系字段</h2></div></div><button className="field-builder-close" type="button" aria-label="关闭" onClick={onClose}><X size={18} /></button></header>
        <p className="field-builder-intro">当前没有可用的授权表结构。</p>
      </aside>
    </div>
  }

  const submitLabel = kind === 'relation' ? '创建关联字段' : '创建查找字段'
  return <div className="field-builder-backdrop" role="presentation">
    <aside className="field-builder-panel relation-lookup-builder-panel" aria-labelledby="relation-lookup-builder-title" aria-modal="true" role="dialog">
      <header className="field-builder-header">
        <div className="field-builder-heading"><span className="field-builder-icon">{kind === 'relation' ? <Link2 size={17} /> : <Search size={17} />}</span><div><p>关系字段</p><h2 id="relation-lookup-builder-title">{kind === 'relation' ? '添加关联字段' : '添加查找字段'}</h2></div></div>
        <button className="field-builder-close" type="button" aria-label="关闭" onClick={onClose} disabled={saving}><X size={18} /></button>
      </header>
      <p className="field-builder-intro">只显示当前 Base 内已授权的表和字段；关联与查找规则由服务端最终校验。</p>
      <div className="relation-lookup-builder-modes" aria-label="字段类型">
        <button type="button" aria-pressed={kind === 'relation'} onClick={() => { setKind('relation'); setError(null) }} disabled={disabled}>关联记录</button>
        <button type="button" aria-pressed={kind === 'lookup'} onClick={() => { setKind('lookup'); setError(null) }} disabled={disabled}>查找</button>
      </div>
      <form className="field-builder-form relation-lookup-builder-form" onSubmit={handleSubmit} noValidate>
        <label><span>字段名称</span><input ref={firstInputRef} value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：关联客户" disabled={disabled} /></label>
        {kind === 'relation' ? <>
          <label><span>关联目标表</span><select value={targetTableId} onChange={(event) => setTargetTableId(event.target.value)} disabled={disabled}><option value="" disabled>请选择</option>{relationTables.map((table) => <option key={table.id} value={table.id}>{table.name}</option>)}</select></label>
          <label className="field-builder-required"><input type="checkbox" checked={required} onChange={(event) => setRequired(event.target.checked)} disabled={disabled} /><span>设为必填字段</span></label>
        </> : <>
          <label><span>关联字段</span><select value={sourceRelationFieldId} onChange={(event) => setSourceRelationFieldId(event.target.value)} disabled={disabled}><option value="" disabled>请选择</option>{sourceRelations.map((field) => <option key={field.id} value={field.id}>{field.name}</option>)}</select></label>
          <label><span>目标字段</span><select value={targetFieldId} onChange={(event) => selectTargetField(event.target.value)} disabled={disabled}><option value="" disabled>请选择</option>{targetFields.map(({ table, field }) => <option key={field.id} value={field.id}>{table.name} / {field.name}</option>)}</select></label>
          <label><span>聚合方式</span><select value={aggregation} onChange={(event) => setAggregation(event.target.value as LookupAggregation)} disabled={disabled}>{availableAggregations(selectedTargetField).map((value) => <option key={value} value={value}>{aggregationLabels[value]}</option>)}</select></label>
        </>}
        {error ? <p className="field-builder-error" role="alert">{error}</p> : null}
        <footer className="field-builder-actions"><button type="button" className="button-secondary" onClick={onClose} disabled={saving}>取消</button><button type="submit" className="button-primary" disabled={disabled}>{saving ? '创建中…' : submitLabel}</button></footer>
      </form>
    </aside>
  </div>
}
