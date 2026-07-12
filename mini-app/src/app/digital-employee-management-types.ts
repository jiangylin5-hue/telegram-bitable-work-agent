export type ManagedEmployeeStatus = 'draft' | 'active' | 'paused'
export type ManagedEmployeeAccessMode = 'workspace' | 'assigned'
export type ManagedEmployeeAction = 'summarize' | 'draft_update'
export type ManagedEmployeeViewType = 'grid' | 'kanban' | 'calendar' | 'form'
export type ManagedEmployeeMemberRole = 'owner' | 'admin' | 'builder' | 'operator' | 'viewer'

export type ManagedEmployeeSummary = {
  id: string
  name: string
  description: string
  status: ManagedEmployeeStatus
  accessMode: ManagedEmployeeAccessMode
  tableCount: number
  viewCount: number
  memberCount: number
  version: number
}

export type ManagedEmployeeDetail = ManagedEmployeeSummary & {
  baseId: string
  telegramAlias: string | null
  accessibleTableIds: string[]
  accessibleViewIds: string[]
  allowedActions: ManagedEmployeeAction[]
  memberIds: string[]
}

export type ManagedEmployeeDirectory = {
  baseId: string
  employees: ManagedEmployeeSummary[]
  nextCursor: string | null
  hasMore: boolean
}

export type ManagedEmployeeManagementContext = {
  base: { id: string; name: string }
  tables: { id: string; name: string }[]
  views: { id: string; tableId: string; name: string; viewType: ManagedEmployeeViewType }[]
  members: { id: string; label: string; role: ManagedEmployeeMemberRole }[]
}

export type ManagedEmployeeCreateValues = {
  name: string
  description: string
  telegramAlias: string | null
}

export type ManagedEmployeeUpdateValues = {
  name?: string
  description?: string
  telegramAlias?: string | null
  accessibleTableIds?: string[]
  accessibleViewIds?: string[]
  allowedActions?: ManagedEmployeeAction[]
  accessMode?: ManagedEmployeeAccessMode
}

export type ManagedEmployeeLifecycleReceipt = {
  id: string
  status: 'active' | 'paused'
  version: number
  auditEventId: string
}
