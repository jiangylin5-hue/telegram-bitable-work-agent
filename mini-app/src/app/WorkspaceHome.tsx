import { ArrowUpRight, Bot, CheckCircle2, ChevronRight, CircleDot, Plus } from 'lucide-react'

import type { BaseSummary, Workspace, WorkspaceHome as WorkspaceHomeData } from './api'

type WorkspaceHomeProps = { home: WorkspaceHomeData; workspace: Workspace; onOpenBase: (base: BaseSummary) => void; onCreateBase?: () => void; onOpenTemplateImport?: () => void; onOpenDraftHub?: (trigger: HTMLElement, draftId?: string) => void; onOpenAssistantContext?: (trigger: HTMLElement) => void; onOpenTeamBot?: (trigger: HTMLElement) => void }

export function WorkspaceHome({ home, workspace, onOpenBase, onCreateBase, onOpenTemplateImport, onOpenDraftHub, onOpenAssistantContext, onOpenTeamBot }: WorkspaceHomeProps) {
  const basesById = new Map(home.recent_bases.map((base) => [base.id, base]))
  return <main className="workspace-home" aria-label="工作区首页" data-testid="workspace-home-workbench" data-workbench-layout="queue-base-assistant">
    <section className="queue-surface" aria-labelledby="today-work-heading">
      <header className="page-toolbar"><div><h1 id="today-work-heading">今天工作</h1><p>{workspace.name} · 当前需处理的持久化事项</p></div><div className="toolbar-actions">{workspace.capabilities.can_manage_schema && onCreateBase && <button type="button" onClick={onCreateBase}><Plus size={17} /> 新建 Base</button>}{workspace.capabilities.can_manage_schema && onOpenTemplateImport && <button type="button" onClick={onOpenTemplateImport}>模板与导入</button>}</div></header>
      <div className="queue-section-title"><span className="section-icon blue"><CircleDot size={16} /></span><h2>待确认</h2><span className="count">{home.queue.length}</span></div>
      {home.queue.length > 0 ? <div className="queue-list" aria-label="待确认队列">{home.queue.map((item) => {
        const linkedBase = basesById.get(item.destination.base_id)
        return <article className="queue-row" key={item.id}><span className="row-check" aria-hidden="true" /><span className="record-icon"><CheckCircle2 size={16} /></span><div className="queue-row-main"><strong>{item.title}</strong><span>草稿 #{item.destination.draft_id.slice(0, 8)}</span>{linkedBase ? <button className="queue-base-link" type="button" aria-label={`打开关联 Base ${linkedBase.name}`} onClick={() => onOpenBase(linkedBase)}>{linkedBase.name}</button> : <span className="queue-base-unavailable">关联 Base 未在当前列表</span>}</div><span className="queue-status">等待你的决定</span>{onOpenDraftHub ? <a href={`#draft/${item.destination.draft_id}`} className="row-link" onClick={(event) => { event.preventDefault(); onOpenDraftHub(event.currentTarget, item.destination.draft_id) }}>查看草稿 <ArrowUpRight size={14} /></a> : <span className="queue-base-unavailable">草稿入口暂不可用</span>}</article>
      })}</div> : <div className="empty-queue">没有待确认的变更。</div>}
    </section>
    <aside className="base-rail" aria-labelledby="recent-bases-heading"><div className="rail-heading"><h2 id="recent-bases-heading">最近 Base</h2><span>{home.recent_bases.length} 个可访问</span></div><div className="base-list">{home.recent_bases.map((base, index) => <a className="base-preview" href={`#base/${base.id}`} key={base.id} aria-label={base.name} onClick={(event) => { event.preventDefault(); onOpenBase(base) }}><div className="base-preview-title"><span className={`base-glyph glyph-${index % 3}`}>▣</span><strong>{base.name}</strong></div><span className="base-kind">{base.source_type === 'blank' ? '多维表格' : base.source_type}</span><div className="preview-grid" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /><i /></div></a>)}</div></aside>
    <aside className="assistant-dock" aria-label="个人助理与团队 Bot"><div className="assistant-title"><Bot size={19} /><strong>个人助理</strong><ChevronRight size={16} /></div><p>你好，{workspace.name}</p><span>需要时选择上下文，再开始协作。</span>{onOpenAssistantContext ? <button type="button" onClick={(event) => onOpenAssistantContext(event.currentTarget)}>智能汇总 <ChevronRight size={16} /></button> : null}{onOpenTeamBot ? <button type="button" aria-label="打开团队 Bot" onClick={(event) => onOpenTeamBot(event.currentTarget)}>团队 Bot <ChevronRight size={16} /></button> : null}</aside>
  </main>
}
