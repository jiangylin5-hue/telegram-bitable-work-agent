export type CapabilityAvailability = 'available' | 'planned'

export type TableOperationKey =
  | 'create_base'
  | 'templates_import'
  | 'create_table'
  | 'create_field'
  | 'create_view'
  | 'configure_view'
  | 'create_record'
  | 'import_into_base'
  | 'save_template'
  | 'base_lifecycle'
  | 'bulk_record_edit'
  | 'export_data'

export type TableOperationDefinition = {
  key: TableOperationKey
  label: string
  description: string
  group: 'workspace' | 'authoring' | 'data' | 'planned'
  availability: CapabilityAvailability
  baseOnly?: boolean
}

export const tableOperationDefinitions: readonly TableOperationDefinition[] = [
  { key: 'create_base', label: '新建 Base', description: '创建带首张表和默认视图的空 Base。', group: 'workspace', availability: 'available' },
  { key: 'templates_import', label: '模板与导入', description: '安装模板，或导入 CSV/XLSX 并在提交前预览映射。', group: 'workspace', availability: 'available' },
  { key: 'create_table', label: '新建数据表', description: '在当前 Base 创建一张受控数据表。', group: 'authoring', availability: 'available', baseOnly: true },
  { key: 'create_field', label: '添加字段', description: '添加普通、关系或查找字段；候选记录由服务端权限过滤。', group: 'authoring', availability: 'available', baseOnly: true },
  { key: 'create_view', label: '新建视图', description: '创建 Grid、Kanban、Calendar 或 Form 保存视图。', group: 'authoring', availability: 'available', baseOnly: true },
  { key: 'configure_view', label: '配置当前视图', description: '修改当前授权视图的筛选、排序、分组和可见字段。', group: 'authoring', availability: 'available', baseOnly: true },
  { key: 'create_record', label: '新建记录', description: '在当前表创建记录，并由服务端校验字段与版本。', group: 'data', availability: 'available', baseOnly: true },
  { key: 'import_into_base', label: '导入到当前 Base', description: '将 CSV/XLSX 映射后显式提交到当前 Base。', group: 'data', availability: 'available', baseOnly: true },
  { key: 'save_template', label: '保存为模板', description: '将当前 Base 保存为可复用的受控模板。', group: 'data', availability: 'available', baseOnly: true },
  { key: 'base_lifecycle', label: '复制或归档 Base', description: 'Base/Table/Field/View 生命周期将在下一模块提供。', group: 'planned', availability: 'planned' },
  { key: 'bulk_record_edit', label: '批量编辑记录', description: '批量编辑、归档和恢复需要独立的权限与审计契约。', group: 'planned', availability: 'planned' },
  { key: 'export_data', label: '导出数据', description: '导出需要字段脱敏、权限和异步任务设计。', group: 'planned', availability: 'planned' },
]

export function getTableOperationDefinitions(scope: 'workspace' | 'base'): readonly TableOperationDefinition[] {
  return tableOperationDefinitions.filter((definition) => scope === 'base' || !definition.baseOnly)
}
