export type GovernanceMember = {
  id: string
  userId: string
  role: string
  status: string
}

export type GovernanceMemberPage = {
  workspaceId: string
  members: GovernanceMember[]
  nextCursor: string | null
  hasMore: boolean
}

export type GovernanceAuditActorType = 'user' | 'digital_employee' | 'system'

export type GovernanceAuditEvent = {
  id: string
  occurredAt: string
  actorType: GovernanceAuditActorType
  eventType: string
  entityType: string
}

export type GovernanceAuditPage = {
  baseId: string
  events: GovernanceAuditEvent[]
  nextCursor: string | null
  hasMore: boolean
}
