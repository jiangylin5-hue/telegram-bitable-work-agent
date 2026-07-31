export type Stage08AssistantIntent = 'business_fact' | 'memory_lookup' | 'mixed' | 'general_advice' | 'risk_review' | 'daily_summary' | 'controlled_action'
export type Stage08RequestedAction = 'auto' | 'read_only' | 'draft_create' | 'draft_update' | 'task_create' | 'reminder_request'
export type Stage08SkillDisabledReason = 'context_required' | 'read_scope_unavailable' | 'write_scope_unavailable' | 'chat_scope_unavailable' | 'runtime_unsupported'
export type Stage08SkillConfirmationPolicy = 'read_only' | 'draft_required_for_write'
export type Stage08SkillSummary = {
  skillId: string
  label: string
  manifestVersion: string
  selectionMode: 'explicit' | 'auto'
}
export type Stage08AssistantSkill = {
  skillId: string
  label: string
  description: string
  enabled: boolean
  disabledReason: Stage08SkillDisabledReason | null
  supportedIntents: readonly ('business_fact' | 'mixed')[]
  supportedActions: readonly Stage08RequestedAction[]
  confirmationPolicy: Stage08SkillConfirmationPolicy
}
export type Stage08AssistantSkillCatalog = {
  manifestVersion: 'stage06-larksuite-skills-v1'
  defaultSelection: 'auto'
  skills: Stage08AssistantSkill[]
}
export type Stage08AssistantStatus = 'completed' | 'draft_pending' | 'degraded' | 'denied' | 'failed' | 'cancelled' | 'timed_out'
export type Stage08CitationLabel = 'business_data' | 'confirmed_memory' | 'group_context' | 'retrieved_material' | 'analysis_from_current_material' | 'general_advice'
export type Stage08DegradationCode = 'context_unavailable' | 'retrieval_unavailable' | 'compression_unavailable' | 'analysis_unavailable' | 'no_evidence' | 'policy_denied' | 'cancelled' | 'timed_out' | 'internal_failure'
export type Stage08AssistantStreamPhase = 'authorizing' | 'planning_context' | 'analysing' | 'creating_draft' | 'completed'

export type Stage08AssistantQuery = {
  workspaceId: string
  employeeId: string
  intent: Stage08AssistantIntent
  query: string
  requestedAction: Stage08RequestedAction
  targetRecordId: string | null
  skillId?: string | null
}

export type Stage08AssistantCitation = { ordinal: number; label: Stage08CitationLabel }
export type Stage08AssistantSafeView = {
  status: Stage08AssistantStatus
  answer: string | null
  citations: Stage08AssistantCitation[]
  degradationCodes: Stage08DegradationCode[]
  draftId: string | null
  skill?: Stage08SkillSummary | null
}

export type Stage08AssistantStreamEvent =
  | { event: 'status'; sequence: number; requestId: string; phase: Stage08AssistantStreamPhase }
  | { event: 'answer_delta'; sequence: number; requestId: string; text: string }
  | { event: 'result'; sequence: number; requestId: string; safeView: Stage08AssistantSafeView }
  | { event: 'error'; sequence: number; requestId: string; code: string; message: string }
  | { event: 'done'; sequence: number; requestId: string }

export type Stage08CollaborationInvocation = Omit<Stage08AssistantQuery, 'workspaceId'>
