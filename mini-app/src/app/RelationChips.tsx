import type { RelationCell } from './api'

function isRelationCell(value: unknown): value is RelationCell {
  return value !== null
    && typeof value === 'object'
    && 'id' in value
    && 'label' in value
    && typeof value.id === 'string'
    && value.id.length > 0
    && typeof value.label === 'string'
    && value.label.trim().length > 0
}

export function safeRelationCells(value: unknown): RelationCell[] {
  return Array.isArray(value) ? value.filter(isRelationCell) : []
}

export function relationLabels(value: unknown): string[] {
  return safeRelationCells(value).map((item) => item.label)
}

export function RelationChips({ value }: { value: unknown }) {
  const cells = safeRelationCells(value)
  if (cells.length === 0) return null
  return <span className="relation-chip-list" aria-label="Related records">{cells.map((item) => <span className="relation-chip" key={item.id}>{item.label}</span>)}</span>
}
