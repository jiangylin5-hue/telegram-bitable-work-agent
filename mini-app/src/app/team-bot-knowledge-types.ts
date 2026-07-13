export type TeamBotViewType = 'grid' | 'kanban' | 'calendar' | 'form'

export type TeamBotContact = {
  id: string
  baseId: string
  name: string
  description: string
  availableIntents: readonly ['summarize']
}

export type TeamBotContactPage = {
  workspaceId: string
  contacts: TeamBotContact[]
  nextCursor: string | null
  hasMore: boolean
}

export type TeamBotKnowledgeView = {
  id: string
  name: string
  viewType: TeamBotViewType
}

export type TeamBotKnowledgeContextPage = {
  employee: { id: string; name: string; description: string; baseId: string }
  views: TeamBotKnowledgeView[]
  nextCursor: string | null
  hasMore: boolean
}

export type TeamBotSelectedView = TeamBotKnowledgeView & { baseId: string }

export type TeamBotSummaryRequest = {
  baseId: string
  viewId: string
  instruction?: string
}

export type TeamBotCitation = { recordId: string }

export type TeamBotSummary = {
  kind: 'summary' | 'empty_context'
  employeeId: string
  baseId: string
  viewId: string
  answer: string
  citations: TeamBotCitation[]
  knowledgeWindowTruncated: boolean
  auditEventId: string
}
