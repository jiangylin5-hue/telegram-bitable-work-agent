import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import type { RelationCandidate, RelationCandidatePage } from './api'
import { RelationPicker } from './RelationPicker'
import type {
  SafeViewField,
  SafeViewMemberCandidate,
  ViewFilterCondition,
  ViewFilterValue,
  ViewPresentationCommand,
  ViewSortRule,
} from './view-builder-types'

type QueryablePresentation = Exclude<ViewPresentationCommand, { view_type: 'form' }>

type ViewQueryControlsProps = {
  presentation: QueryablePresentation
  fields: SafeViewField[]
  memberCandidates: SafeViewMemberCandidate[]
  onChange: (presentation: QueryablePresentation) => void
  disabled?: boolean
  loadRelationCandidates?: (fieldId: string, query: string, cursor: string | null) => Promise<RelationCandidatePage>
}

const emptyValueOperators = new Set(['is_empty', 'is_not_empty', 'is_true', 'is_false'])

function isEmptyValueOperator(operator: string): boolean {
  return emptyValueOperators.has(operator)
}

function firstOperator(field: SafeViewField): string {
  return field.filter_operators.find((operator) => !isEmptyValueOperator(operator))
    ?? field.filter_operators[0]
    ?? ''
}

function defaultValue(field: SafeViewField, operator: string, members: SafeViewMemberCandidate[]): ViewFilterValue {
  if (isEmptyValueOperator(operator)) return null
  if (field.field_type === 'status' || field.field_type === 'single_select') return field.filter_values[0] ?? ''
  if (field.field_type === 'multi_select') return field.filter_values.slice(0, 1)
  if (field.field_type === 'user') return members[0]?.id ?? ''
  if (field.field_type === 'checkbox') return null
  if (field.field_type === 'number' || field.field_type === 'lookup') return 0
  return ''
}

function fieldByKey(fields: SafeViewField[], key: string): SafeViewField | undefined {
  return fields.find((field) => field.key === key)
}

function relationCandidate(value: ViewFilterValue, labels: Map<string, RelationCandidate>): RelationCandidate[] {
  return typeof value === 'string' && labels.has(value) ? [labels.get(value)!] : []
}

function QueryValueEditor({
  condition,
  field,
  index,
  members,
  disabled,
  onChange,
  loadRelationCandidates,
}: {
  condition: ViewFilterCondition
  field: SafeViewField
  index: number
  members: SafeViewMemberCandidate[]
  disabled: boolean
  onChange: (value: ViewFilterValue) => void
  loadRelationCandidates?: (fieldId: string, query: string, cursor: string | null) => Promise<RelationCandidatePage>
}) {
  const [relationLabels, setRelationLabels] = useState<Map<string, RelationCandidate>>(() => new Map())
  const label = `筛选值 ${index + 1}`
  if (isEmptyValueOperator(condition.operator)) return <output className="view-query-empty-value">无需填写值</output>
  if (field.field_type === 'linked_record') {
    if (!loadRelationCandidates) return <p className="view-query-hint">关联候选会在当前权限范围内加载。</p>
    const selected = relationCandidate(condition.value, relationLabels)
    return <div className="view-query-relation" aria-label={label}>
      {typeof condition.value === 'string' && selected.length === 0 ? <p className="view-query-hint">已设置关联筛选；重新选择会覆盖该记录。</p> : null}
      <RelationPicker
        fieldId={field.field_id}
        value={selected}
        disabled={disabled}
        loadCandidates={loadRelationCandidates}
        onChange={(next) => {
          const candidate = next.at(-1)
          if (!candidate) return onChange(null)
          setRelationLabels((current) => new Map(current).set(candidate.id, candidate))
          onChange(candidate.id)
        }}
      />
    </div>
  }
  if (field.field_type === 'status' || field.field_type === 'single_select') {
    return <select aria-label={label} value={typeof condition.value === 'string' ? condition.value : ''} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
      <option value="">请选择</option>
      {field.filter_values.map((value) => <option key={value} value={value}>{value}</option>)}
    </select>
  }
  if (field.field_type === 'multi_select') {
    const selected = Array.isArray(condition.value) ? condition.value : []
    return <select aria-label={label} multiple value={selected} disabled={disabled} onChange={(event) => onChange([...event.target.selectedOptions].map((option) => option.value))}>
      {field.filter_values.map((value) => <option key={value} value={value}>{value}</option>)}
    </select>
  }
  if (field.field_type === 'user') {
    return <select aria-label={label} value={typeof condition.value === 'string' ? condition.value : ''} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
      <option value="">请选择</option>
      {members.map((member) => <option key={member.id} value={member.id}>{member.label}</option>)}
    </select>
  }
  const inputType = field.field_type === 'number' || field.field_type === 'lookup'
    ? 'number'
    : field.field_type === 'date' ? 'date' : 'text'
  const value = typeof condition.value === 'number' || typeof condition.value === 'string' ? String(condition.value) : ''
  return <input aria-label={label} type={inputType} value={value} disabled={disabled} onChange={(event) => onChange(inputType === 'number' && event.target.value !== '' ? Number(event.target.value) : event.target.value)} />
}

export function ViewQueryControls({ presentation, fields, memberCandidates, onChange, disabled = false, loadRelationCandidates }: ViewQueryControlsProps) {
  const filterableFields = fields.filter((field) => field.filter_operators.length > 0)
  const sortableFields = fields.filter((field) => field.sortable)
  const groupableFields = fields.filter((field) => field.groupable)
  const dateFields = fields.filter((field) => field.field_type === 'date')

  function updateFilters(filters: ViewFilterCondition[]) {
    onChange({ ...presentation, filters })
  }

  function updateSorts(sortRules: ViewSortRule[]) {
    onChange({ ...presentation, sort_rules: sortRules })
  }

  function addFilter() {
    const field = filterableFields[0]
    if (!field || presentation.filters.length >= 12) return
    const operator = firstOperator(field)
    updateFilters([...presentation.filters, { field_key: field.key, operator, value: defaultValue(field, operator, memberCandidates) }])
  }

  function updateFilter(index: number, next: ViewFilterCondition) {
    updateFilters(presentation.filters.map((condition, conditionIndex) => conditionIndex === index ? next : condition))
  }

  function addSort() {
    const field = sortableFields.find((candidate) => !presentation.sort_rules.some((rule) => rule.field_key === candidate.key))
    if (!field || presentation.sort_rules.length >= 3) return
    updateSorts([...presentation.sort_rules, { field_key: field.key, direction: 'asc' }])
  }

  const groupValue = presentation.view_type === 'grid' || presentation.view_type === 'kanban'
    ? presentation.group_by_field_key ?? ''
    : ''
  const isKanban = presentation.view_type === 'kanban'

  return <div className="view-query-controls">
    <section className="view-query-section" aria-labelledby="view-filter-title">
      <header><div><p>查询</p><h3 id="view-filter-title">筛选条件</h3></div><button type="button" onClick={addFilter} disabled={disabled || !filterableFields.length || presentation.filters.length >= 12}><Plus size={15} />添加筛选条件</button></header>
      <p className="view-query-hint">所有条件同时生效（AND），最多 12 条。</p>
      {presentation.filters.map((condition, index) => {
        const field = fieldByKey(fields, condition.field_key) ?? filterableFields[0]
        if (!field) return null
        return <div className="view-query-row" key={`${condition.field_key}-${index}`}>
          <select aria-label={`筛选字段 ${index + 1}`} value={field.key} disabled={disabled} onChange={(event) => {
            const nextField = fieldByKey(filterableFields, event.target.value)
            if (!nextField) return
            const operator = firstOperator(nextField)
            updateFilter(index, { field_key: nextField.key, operator, value: defaultValue(nextField, operator, memberCandidates) })
          }}>
            {filterableFields.map((candidate) => <option key={candidate.key} value={candidate.key}>{candidate.label}</option>)}
          </select>
          <select aria-label={`筛选操作 ${index + 1}`} value={condition.operator} disabled={disabled} onChange={(event) => {
            const operator = event.target.value
            updateFilter(index, { ...condition, operator, value: defaultValue(field, operator, memberCandidates) })
          }}>
            {field.filter_operators.map((operator) => <option key={operator} value={operator}>{operator}</option>)}
          </select>
          <QueryValueEditor condition={condition} field={field} index={index} members={memberCandidates} disabled={disabled} onChange={(value) => updateFilter(index, { ...condition, value })} loadRelationCandidates={loadRelationCandidates} />
          <button type="button" aria-label={`删除筛选条件 ${index + 1}`} onClick={() => updateFilters(presentation.filters.filter((_, conditionIndex) => conditionIndex !== index))} disabled={disabled}><Trash2 size={15} /></button>
        </div>
      })}
    </section>

    <section className="view-query-section" aria-labelledby="view-sort-title">
      <header><div><p>查询</p><h3 id="view-sort-title">排序</h3></div><button type="button" onClick={addSort} disabled={disabled || !sortableFields.length || presentation.sort_rules.length >= 3}><Plus size={15} />添加排序</button></header>
      <p className="view-query-hint">最多三条；服务端会追加稳定记录顺序。</p>
      {presentation.sort_rules.map((rule, index) => <div className="view-query-row" key={`${rule.field_key}-${index}`}>
        <select aria-label={`排序字段 ${index + 1}`} value={rule.field_key} disabled={disabled} onChange={(event) => updateSorts(presentation.sort_rules.map((current, sortIndex) => sortIndex === index ? { ...current, field_key: event.target.value } : current))}>
          {sortableFields.map((field) => <option key={field.key} value={field.key}>{field.label}</option>)}
        </select>
        <select aria-label={`排序方向 ${index + 1}`} value={rule.direction} disabled={disabled} onChange={(event) => updateSorts(presentation.sort_rules.map((current, sortIndex) => sortIndex === index ? { ...current, direction: event.target.value as ViewSortRule['direction'] } : current))}>
          <option value="asc">升序</option><option value="desc">降序</option>
        </select>
        <button type="button" aria-label={`删除排序 ${index + 1}`} onClick={() => updateSorts(presentation.sort_rules.filter((_, sortIndex) => sortIndex !== index))} disabled={disabled}><Trash2 size={15} /></button>
      </div>)}
    </section>

    <section className="view-query-section" aria-labelledby="view-group-title">
      <header><div><p>类型设置</p><h3 id="view-group-title">{presentation.view_type === 'calendar' ? '日期字段' : '分组字段'}</h3></div></header>
      {presentation.view_type === 'calendar'
        ? <select aria-label="日期字段" value={presentation.date_field_key} disabled={disabled} onChange={(event) => onChange({ ...presentation, date_field_key: event.target.value })}>
          <option value="">请选择日期字段</option>{dateFields.map((field) => <option key={field.key} value={field.key}>{field.label}</option>)}
        </select>
        : <select aria-label="分组字段" value={groupValue} disabled={disabled} onChange={(event) => onChange({ ...presentation, group_by_field_key: event.target.value || null } as QueryablePresentation)}>
          {!isKanban ? <option value="">不分组</option> : <option value="">请选择分组字段</option>}
          {groupableFields.map((field) => <option key={field.key} value={field.key}>{field.label}</option>)}
        </select>}
      <p className="view-query-hint">关联记录、查找和多选字段不提供分组。</p>
    </section>
  </div>
}
