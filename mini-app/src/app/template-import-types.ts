export type TemplateSummary = {
  id: string
  name: string
  category: string
  description: string
  version: string
  status: string
}

export type TemplateInstallationReceipt = {
  id: string
  workspaceId: string
  baseId: string
  templateId: string
  templateVersion: string
}

export type SaveTemplateValues = {
  name: string
  category: string
  description: string
  createdByUserId: string
}

/**
 * Import intentionally exposes only portable field types. Relation, lookup
 * and formula fields require an existing table/schema and are added later in
 * the Base instead of being guessed from a spreadsheet column.
 */
export type ImportScalarFieldType =
  | 'text'
  | 'number'
  | 'date'
  | 'checkbox'
  | 'status'
  | 'single_select'
  | 'multi_select'
  | 'url'
  | 'email'
  | 'phone'

export type ImportSchemaField = {
  key: string
  name: string
  fieldType: ImportScalarFieldType
}

export type ImportMapping = {
  sourceKey: string
  targetKey: string
  fieldType: ImportScalarFieldType
  name?: string
}

export type CreateImportValues = {
  sourceType: 'csv' | 'excel'
  fileName: string
  content: string
  createdByUserId: string
  baseId?: string
}

export type ImportPreview = {
  id: string
  workspaceId: string
  baseId: string | null
  sourceType: 'csv' | 'excel'
  detectedSchema: ImportSchemaField[]
  previewRows: Record<string, unknown>[]
  mapping: ImportMapping[]
  status: 'awaiting_confirmation' | 'committed'
}

export type CommitImportValues = {
  baseName: string
  tableName: string
  tableKey: string
  fieldMapping?: ImportMapping[]
}

export type ImportCommitReceipt = {
  importJobId: string
  status: 'committed'
  baseId: string
  tableId: string
}
