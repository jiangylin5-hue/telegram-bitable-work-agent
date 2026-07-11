import { useEffect, useRef, useState } from 'react'

import type { RelationCandidate, RelationCandidatePage } from './api'

type RelationPickerProps = {
  fieldId: string
  value: RelationCandidate[]
  onChange: (value: RelationCandidate[]) => void
  loadCandidates: (fieldId: string, query: string, cursor: string | null) => Promise<RelationCandidatePage>
  disabled?: boolean
}

export function RelationPicker({ fieldId, value, onChange, loadCandidates, disabled = false }: RelationPickerProps) {
  const [query, setQuery] = useState('')
  const [candidates, setCandidates] = useState<RelationCandidate[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const requestGeneration = useRef(0)

  async function loadPage(cursor: string | null, nextQuery = query) {
    const generation = ++requestGeneration.current
    setLoading(true)
    try {
      const page = await loadCandidates(fieldId, nextQuery, cursor)
      if (generation !== requestGeneration.current || page.field_id !== fieldId) return
      setCandidates((current) => cursor === null ? page.records : [...current, ...page.records.filter((item) => !current.some((existing) => existing.id === item.id))])
      setNextCursor(page.next_cursor)
      setHasMore(page.has_more)
    } finally {
      if (generation === requestGeneration.current) setLoading(false)
    }
  }

  useEffect(() => {
    setCandidates([])
    setNextCursor(null)
    setHasMore(false)
    void loadPage(null, '')
  }, [fieldId])

  function toggle(candidate: RelationCandidate) {
    if (disabled) return
    const existing = value.some((item) => item.id === candidate.id)
    onChange(existing ? value.filter((item) => item.id !== candidate.id) : [...value, candidate])
  }

  return <section className="relation-picker" aria-label="Relation picker">
    <div className="relation-chips">{value.map((item) => <button type="button" key={item.id} onClick={() => toggle(item)} disabled={disabled}>{item.label} ×</button>)}</div>
    <input aria-label="Search related records" value={query} disabled={disabled || loading} onChange={(event) => {
      const nextQuery = event.target.value
      setQuery(nextQuery)
      void loadPage(null, nextQuery)
    }} />
    <div className="relation-candidate-list">{candidates.map((candidate) => <button type="button" key={candidate.id} onClick={() => toggle(candidate)} disabled={disabled || loading}>{candidate.label}</button>)}</div>
    {hasMore && <button type="button" onClick={() => void loadPage(nextCursor)} disabled={disabled || loading}>Load more</button>}
  </section>
}
