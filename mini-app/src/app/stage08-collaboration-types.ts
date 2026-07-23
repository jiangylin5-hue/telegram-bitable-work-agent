export type Stage08AssistantIntent = 'business_fact' | 'memory_lookup' | 'mixed' | 'general_advice'
export type Stage08RequestedAction = 'read_only' | 'draft_update'
export type Stage08AssistantStatus = 'completed' | 'draft_pending' | 'degraded' | 'denied' | 'failed' | 'cancelled' | 'timed_out'
export type Stage08CitationLabel = 'business_data' | 'confirmed_memory' | 'group_context' | 'retrieved_material' | 'analysis_from_current_material' | 'general_advice'
export type Stage08DegradationCode = 'context_unavailable' | 'retrieval_unavailable' | 'compression_unavailable' | 'analysis_unavailable' | 'no_evidence' | 'policy_denied' | 'cancelled' | 'timed_out' | 'internal_failure'

export type Stage08AssistantQuery = {
  workspaceId: string
  employeeId: string
  intent: Stage08AssistantIntent
  query: string
  requestedAction: Stage08RequestedAction
  targetRecordId: string | null
}

export type Stage08AssistantCitation = { ordinal: number; label: Stage08CitationLabel }
export type Stage08AssistantSafeView = {
  status: Stage08AssistantStatus
  answer: string | null
  citations: Stage08AssistantCitation[]
  degradationCodes: Stage08DegradationCode[]
  draftId: string | null
}

export type Stage08CollaborationInvocation = Omit<Stage08AssistantQuery, 'workspaceId'>
