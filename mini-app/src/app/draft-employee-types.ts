export type S5Intent = 'summarize' | 'draft_update'
export type S5Contact = { id: string; baseId: string; name: string; description: string; status: 'active'; availableIntents: S5Intent[] }
export type S5ContactPage = { workspaceId: string; contacts: S5Contact[]; nextCursor: string | null; hasMore: boolean }
export type S5DraftField = { key: string; label: string; fieldType: string; beforeValue: string | number | boolean | null; proposedValue: string | number | boolean | null }
export type S5DraftDetail = { id: string; baseId: string; tableId: string; recordId: string | null; draftType: string; status: 'pending_confirmation' | 'confirmed' | 'rejected' | 'expired'; version: number; fields: S5DraftField[]; actions: { canConfirm: boolean; canReject: boolean }; terminalAuditEventId: string | null }
export type S5TerminalReceipt = { id: string; status: 'confirmed' | 'rejected'; version: number; terminalAuditEventId: string }
