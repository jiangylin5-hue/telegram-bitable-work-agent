export type Stage08MemoryType = 'decision' | 'preference' | 'risk' | 'customer_fact' | 'project_fact'

export type Stage08MemoryItem = {
  memoryType: Stage08MemoryType
  status: 'active'
  version: number
  payload: Record<string, unknown>
  validUntil: string | null
}

export type Stage08MemoryPage = { items: Stage08MemoryItem[] }
