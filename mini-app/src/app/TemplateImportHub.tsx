import { type MouseEvent, useEffect, useState } from 'react'

import type { TemplateSummary } from './template-import-types'

type Props = {
  templates: TemplateSummary[]
  loading: boolean
  error: string | null
  onRetry: () => void
  onInstall: (template: TemplateSummary) => Promise<void> | void
  onInstallError?: () => void
  onStartWorkspaceImport?: () => void
  onClose: () => void
}

export function TemplateImportHub({ templates, loading, error, onRetry, onInstall, onInstallError, onStartWorkspaceImport, onClose }: Props) {
  const [installingId, setInstallingId] = useState<string | null>(null)
  const [conflictLockedId, setConflictLockedId] = useState<string | null>(null)
  const [installError, setInstallError] = useState<string | null>(null)

  function isConflict(reason: unknown) {
    return Boolean(reason && typeof reason === 'object' && 'status' in reason && (reason as { status?: unknown }).status === 409)
  }

  async function install(template: TemplateSummary) {
    if (conflictLockedId === template.id) return
    setInstallError(null)
    setInstallingId(template.id)
    try {
      await onInstall(template)
    } catch (reason) {
      if (isConflict(reason)) {
        setConflictLockedId(template.id)
        setInstallError('模板安装状态已变化，请关闭后重新打开。')
      } else {
        onInstallError?.()
      }
    } finally {
      setInstallingId(null)
    }
  }

  useEffect(() => {
    if (installingId !== null) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [installingId, onClose])

  function closeFromBackdrop(event: MouseEvent<HTMLDivElement>) {
    if (installingId === null && event.target === event.currentTarget) onClose()
  }

  return <div className="template-import-backdrop" role="presentation" onMouseDown={closeFromBackdrop}>
    <aside className="template-import-panel" aria-labelledby="template-import-title" aria-modal="true" role="dialog">
      <header className="template-import-header"><div><p>WORKSPACE SETUP</p><h2 id="template-import-title">模板与导入</h2><span>从已有结构开始，或导入一个文件创建持久化数据表。</span></div><button type="button" aria-label="关闭模板与导入" onClick={onClose}>×</button></header>
      {onStartWorkspaceImport && <div className="template-import-actions"><button type="button" className="button-primary" onClick={onStartWorkspaceImport}>导入到新 Base</button></div>}
      {installError ? <div className="template-import-error" role="alert">{installError}</div> : null}
      <section className="template-shelf" aria-labelledby="template-shelf-title"><header><h3 id="template-shelf-title">模板</h3><small>安装后将刷新工作区资源</small></header>
        {loading ? <p role="status">正在加载模板…</p> : error ? <div className="template-import-error" role="alert"><span>{error}</span><button type="button" onClick={onRetry}>重试</button></div> : templates.length === 0 ? <p className="template-import-empty">当前没有可用模板。</p> : <div className="template-card-list">{templates.map((template) => <article className="template-card" key={template.id}><div><span>{template.category}</span><h4>{template.name}</h4><p>{template.description}</p><small>v{template.version} · {template.status}</small></div><button type="button" aria-label={`安装模板 ${template.name}`} disabled={installingId !== null || conflictLockedId === template.id} onClick={() => { void install(template) }}>{installingId === template.id ? '安装中…' : conflictLockedId === template.id ? '请关闭后重新打开' : '安装模板'}</button></article>)}</div>}
      </section>
    </aside>
  </div>
}
