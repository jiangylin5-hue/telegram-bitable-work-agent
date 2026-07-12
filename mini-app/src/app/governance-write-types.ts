export type GovernanceRole = 'owner' | 'admin' | 'builder' | 'operator' | 'viewer'
export type GovernanceAssignableRole = Exclude<GovernanceRole, 'owner'>
export type GovernanceFieldPermissionMode = 'hidden' | 'read' | 'write'
export type GovernanceFieldPermissionPolicy = Record<GovernanceRole, GovernanceFieldPermissionMode>

export type GovernanceEditableMember = {
  id: string
  userId: string
  role: GovernanceRole
  status: 'active'
  version: number
  assignableRoles: GovernanceAssignableRole[]
}

export type GovernanceEditableMemberPage = {
  workspaceId: string
  members: GovernanceEditableMember[]
  nextCursor: string | null
  hasMore: boolean
}

export type GovernanceMemberRoleReceipt = {
  id: string
  userId: string
  role: GovernanceRole
  status: 'active'
  version: number
}

export type GovernanceFieldPermission = {
  id: string
  key: string
  label: string
  fieldType: string
  policy: GovernanceFieldPermissionPolicy
  permissionVersion: number
}

export type GovernanceFieldPermissionPage = {
  tableId: string
  fields: GovernanceFieldPermission[]
}

export type GovernanceFieldPermissionReceipt = {
  id: string
  key: string
  policy: GovernanceFieldPermissionPolicy
  permissionVersion: number
}
