import { X } from 'lucide-react'

import { getTableOperationDefinitions, type TableOperationKey } from './capability-registry'

export type TableOperationScope =
  | { kind: 'workspace' }
  | { kind: 'base'; baseName: string; tableName: string; viewName: string }

export type TableOperationActions = {
  onCreateBase?: () => void
  onOpenTemplates?: () => void
  onCreateTable?: () => void
  onCreateField?: () => void
  onCreateView?: () => void
  onConfigureView?: () => void
  onCreateRecord?: () => void
  onImportIntoBase?: () => void
  onSaveTemplate?: () => void
}

type TableOperationCenterProps = {
  scope: TableOperationScope
  actions: TableOperationActions
  onClose: () => void
}

const groupLabels = {
  workspace: '工作区',
  authoring: '表格搭建',
  data: '数据与模板',
  planned: '后续能力',
} as const

export function TableOperationCenter({ scope, actions, onClose }: TableOperationCenterProps) {
  const availableGroups = ['workspace', 'authoring', 'data', 'planned'] as const
  const definitions = getTableOperationDefinitions(scope.kind)
  const scopeSummary = scope.kind === 'base'
    ? `${scope.baseName} / ${scope.tableName} / ${scope.viewName}`
    : '从当前工作区开始创建、导入或安装一个 Base。'

  const actionByKey: Partial<Record<TableOperationKey, () => void>> = {
    create_base: actions.onCreateBase,
    templates_import: actions.onOpenTemplates,
    create_table: actions.onCreateTable,
    create_field: actions.onCreateField,
    create_view: actions.onCreateView,
    configure_view: actions.onConfigureView,
    create_record: actions.onCreateRecord,
    import_into_base: actions.onImportIntoBase,
    save_template: actions.onSaveTemplate,
  }

  function dispatch(key: TableOperationKey) {
    const action = actionByKey[key]
    if (!action) return
    onClose()
    action()
  }

  return <div className="table-operation-backdrop" role="presentation">
    <aside className="table-operation-center" aria-label="表格操作中心" aria-modal="true" role="dialog">
      <header className="table-operation-header">
        <div><p>TABLE OPERATIONS</p><h2>表格操作中心</h2><span>{scopeSummary}</span></div>
        <button type="button" aria-label="关闭表格操作中心" onClick={onClose}><X size={19} /></button>
      </header>
      <p className="table-operation-intro">这里的每一项都会打开现有的受控工作流；不会绕过 Base、字段、视图、记录或权限服务。</p>
      <div className="table-operation-groups">
        {availableGroups.map((group) => {
          const entries = definitions.filter((definition) => definition.group === group)
          if (entries.length === 0) return null
          return <section key={group} className="table-operation-group" aria-label={groupLabels[group]}>
            <h3>{groupLabels[group]}</h3>
            <div>{entries.map((definition) => {
              const action = actionByKey[definition.key]
              const enabled = definition.availability === 'available' && Boolean(action)
              return <button
                type="button"
                key={definition.key}
                disabled={!enabled}
                data-availability={definition.availability}
                aria-label={definition.label}
                onClick={() => dispatch(definition.key)}
              >
                <strong>{definition.label}</strong>
                <span>{definition.description}</span>
                {definition.availability === 'planned' && <small>即将上线</small>}
              </button>
            })}</div>
          </section>
        })}
      </div>
      <p className="table-operation-boundary">这些能力尚未有受控的后端契约，不能以静态页面冒充可用。</p>
    </aside>
  </div>
}
