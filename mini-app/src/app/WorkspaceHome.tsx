import { ArrowUpRight, Bot, CheckCircle2, ChevronRight, CircleDot, Database, FileSpreadsheet, FolderOpen, MessageSquareText, Network, Plus, Sparkles } from 'lucide-react'

import type { BaseSummary, Workspace, WorkspaceHome as WorkspaceHomeData } from './api'

type BusinessRelation = NonNullable<WorkspaceHomeData['business_context_relations']>[number]
type BusinessRecordReference = BusinessRelation['customer']
type BusinessEmployeeReference = BusinessRelation['employee']

type WorkspaceHomeProps = {
  home: WorkspaceHomeData
  workspace: Workspace
  onOpenBase: (base: BaseSummary) => void
  onCreateBase?: () => void
  onOpenTemplateImport?: () => void
  onOpenTableOperations?: (trigger: HTMLElement) => void
  onOpenDraftHub?: (trigger: HTMLElement, draftId?: string) => void
  onOpenAssistantContext?: (trigger: HTMLElement) => void
  onOpenCollaboration?: (trigger: HTMLElement) => void
  onOpenMemory?: (trigger: HTMLElement) => void
  onOpenTeamBot?: (trigger: HTMLElement) => void
  onOpenRecordReference?: (reference: BusinessRecordReference) => void
  onOpenEmployeeReference?: (trigger: HTMLElement, employee: BusinessEmployeeReference) => void
}

export function WorkspaceHome({
  home,
  workspace,
  onOpenBase,
  onCreateBase,
  onOpenTemplateImport,
  onOpenTableOperations,
  onOpenDraftHub,
  onOpenAssistantContext,
  onOpenCollaboration,
  onOpenMemory,
  onOpenTeamBot,
  onOpenRecordReference,
  onOpenEmployeeReference,
}: WorkspaceHomeProps) {
  const basesById = new Map(home.recent_bases.map((base) => [base.id, base]))
  const businessRelations = home.business_context_relations ?? []
  const nextDraft = home.queue[0]
  const accessibleBase = home.recent_bases[0]
  const canContinue = Boolean(
    (nextDraft && onOpenDraftHub)
    || accessibleBase
    || onOpenTeamBot,
  )

  return <main className="workspace-home" aria-label="工作区首页" data-testid="workspace-home-workbench" data-workbench-layout="queue-base-assistant">
    <section className="queue-surface" aria-labelledby="today-work-heading">
      <header className="page-toolbar">
        <div>
          <h1 id="today-work-heading">今天工作</h1>
          <p>{workspace.name} · 当前需处理的持久化事项</p>
        </div>
        <div className="toolbar-actions">
          {onOpenCollaboration ? <button className="home-ai-conversation" type="button" aria-label="打开 AI 对话" onClick={(event) => onOpenCollaboration(event.currentTarget)}><Sparkles size={16} /> AI 对话</button> : null}
          {onOpenTableOperations && <button type="button" onClick={(event) => onOpenTableOperations(event.currentTarget)}>表格操作</button>}
          {workspace.capabilities.can_manage_schema && onCreateBase && <button type="button" onClick={onCreateBase}><Plus size={17} /> 新建 Base</button>}
          {workspace.capabilities.can_manage_schema && onOpenTemplateImport && <button type="button" onClick={onOpenTemplateImport}>模板与导入</button>}
        </div>
      </header>
      <section className="workspace-fact-strip" aria-label="当前工作区状态">
        <div className="workspace-fact fact-blue"><span><Database size={15} /> 可访问 Base</span><strong>{home.recent_bases.length}</strong></div>
        <div className="workspace-fact fact-amber"><span><CircleDot size={15} /> 待确认</span><strong>{home.queue.length}</strong></div>
        <div className="workspace-fact fact-violet"><span><Network size={15} /> 已授权业务关联</span><strong>{businessRelations.length}</strong></div>
      </section>
      {canContinue ? <section className="continue-work" aria-label="继续处理">
        <header><div><span>CONTINUE</span><h2>继续处理</h2></div><p>入口来自当前可访问的草稿、Base 与协作能力。</p></header>
        <div className="continue-work-list">
          {nextDraft && onOpenDraftHub ? <button type="button" className="continue-work-primary" aria-label="继续处理待确认草稿" onClick={(event) => onOpenDraftHub(event.currentTarget, nextDraft.destination.draft_id)}>
            <span className="continue-work-icon"><CheckCircle2 size={17} /></span>
            <span><strong>待确认草稿</strong><small>{home.queue.length} 个待处理</small></span>
            <ArrowUpRight size={15} />
          </button> : null}
          {accessibleBase ? <button type="button" aria-label={`打开可访问 Base ${accessibleBase.name}`} onClick={() => onOpenBase(accessibleBase)}>
            <span className="continue-work-icon"><FolderOpen size={17} /></span>
            <span><strong>{accessibleBase.name}</strong><small>打开可访问 Base</small></span>
            <ChevronRight size={15} />
          </button> : null}
          {onOpenTeamBot ? <button type="button" aria-label="继续使用团队 Bot" onClick={(event) => onOpenTeamBot(event.currentTarget)}>
            <span className="continue-work-icon"><Bot size={17} /></span>
            <span><strong>团队 Bot</strong><small>使用已授权团队助手</small></span>
            <ChevronRight size={15} />
          </button> : null}
        </div>
      </section> : null}
      <div className="queue-section-title"><span className="section-icon blue"><CircleDot size={16} /></span><h2>待确认</h2><span className="count">{home.queue.length}</span></div>
      {home.queue.length > 0 ? <div className="queue-list" aria-label="待确认队列">{home.queue.map((item) => {
        const linkedBase = basesById.get(item.destination.base_id)
        return <article className="queue-row" key={item.id}>
          <span className="row-check" aria-hidden="true" />
          <span className="record-icon"><CheckCircle2 size={16} /></span>
          <div className="queue-row-main">
            <strong>{item.title}</strong>
            <span>草稿 #{item.destination.draft_id.slice(0, 8)}</span>
            {linkedBase ? <button className="queue-base-link" type="button" aria-label={`打开关联 Base ${linkedBase.name}`} onClick={() => onOpenBase(linkedBase)}>{linkedBase.name}</button> : <span className="queue-base-unavailable">关联 Base 未在当前列表</span>}
          </div>
          <span className="queue-status">等待你的决定</span>
          {onOpenDraftHub ? <a href={`#draft/${item.destination.draft_id}`} className="row-link" onClick={(event) => { event.preventDefault(); onOpenDraftHub(event.currentTarget, item.destination.draft_id) }}>查看草稿 <ArrowUpRight size={14} /></a> : <span className="queue-base-unavailable">草稿入口暂不可用</span>}
        </article>
      })}</div> : <section className="workspace-ready-state" data-testid="workspace-ready-state" aria-label="开始协作">
        <div className="workspace-ready-mark"><CheckCircle2 size={19} /></div>
        <div className="workspace-ready-copy"><strong>工作台已准备就绪</strong><span>还没有待确认的变更。选择一个入口开始沉淀业务结果。</span></div>
        <div className="workspace-ready-actions">
          {workspace.capabilities.can_manage_schema && onCreateBase ? <button className="ready-action-ready" type="button" aria-label="从工作台新建 Base" onClick={onCreateBase}><Plus size={15} /> 新建 Base</button> : null}
          {workspace.capabilities.can_manage_schema && onOpenTemplateImport ? <button className="ready-action-import" type="button" onClick={onOpenTemplateImport}><FileSpreadsheet size={15} /> 从 Excel/CSV 导入</button> : null}
          {onOpenCollaboration ? <button className="ready-action-ai" type="button" onClick={(event) => onOpenCollaboration(event.currentTarget)}><MessageSquareText size={15} /> 开始 AI 对话</button> : null}
        </div>
      </section>}
    </section>

    <aside className="base-rail" aria-labelledby="accessible-bases-heading">
      <div className="rail-heading"><h2 id="accessible-bases-heading">可访问 Base</h2><span>{home.recent_bases.length} 个可访问</span></div>
      <div className="base-list">{home.recent_bases.map((base, index) => <a className={`base-preview palette-${index % 6}`} href={`#base/${base.id}`} key={base.id} aria-label={base.name} onClick={(event) => { event.preventDefault(); onOpenBase(base) }}><div className="base-preview-title"><span className={`base-glyph glyph-${index % 3}`}>▣</span><strong>{base.name}</strong></div><span className="base-kind">{base.source_type === 'blank' ? '多维表格' : base.source_type}</span><div className="preview-grid" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /><i /></div></a>)}</div>
    </aside>

    <aside className="assistant-dock" aria-label="个人助理与团队 Bot">
      <div className="assistant-title"><Bot size={19} /><strong>个人助理</strong><ChevronRight size={16} /></div>
      <p>你好，{workspace.name}</p>
      <span>需要时选择上下文，再开始协作。</span>
      {onOpenAssistantContext ? <button type="button" onClick={(event) => onOpenAssistantContext(event.currentTarget)}>智能汇总 <ChevronRight size={16} /></button> : null}
      {onOpenCollaboration ? <button className="assistant-dock-ai" type="button" onClick={(event) => onOpenCollaboration(event.currentTarget)}><Sparkles size={16} /> AI 对话 <ChevronRight size={16} /></button> : null}
      {onOpenMemory ? <button type="button" onClick={(event) => onOpenMemory(event.currentTarget)}>记忆与知识 <ChevronRight size={16} /></button> : null}
      {onOpenTeamBot ? <button type="button" aria-label="打开团队 Bot" onClick={(event) => onOpenTeamBot(event.currentTarget)}>团队 Bot <ChevronRight size={16} /></button> : null}
      {businessRelations.length > 0 && <section className="business-context-index" data-testid="business-context-index" aria-label="已授权业务关联">
        <header><span>业务关联</span><small>{businessRelations.length} 条已授权映射</small></header>
        <div className="business-context-list">{businessRelations.map((relation, index) => <article key={`${relation.group.id}:${relation.mapping_version}`} className={`business-context-relation relation-tone-${index % 3}`}>
          <div className="business-context-route">
            {onOpenEmployeeReference ? <button type="button" className="business-context-employee" aria-label={`打开数字员工 ${relation.employee.name}`} onClick={(event) => onOpenEmployeeReference(event.currentTarget, relation.employee)}>{relation.employee.name}</button> : <span>{relation.employee.name}</span>}
            <span aria-hidden="true">→</span>
            {onOpenAssistantContext ? <button type="button" className="business-context-group" aria-label={`查看群聊上下文 ${relation.group.label}`} onClick={(event) => onOpenAssistantContext(event.currentTarget)}>{relation.group.label}</button> : <span>{relation.group.label}</span>}
          </div>
          <div className="business-context-records">
            {onOpenRecordReference ? <button type="button" aria-label={`打开客户记录 ${relation.customer.label}`} onClick={() => onOpenRecordReference(relation.customer)}>客户 · {relation.customer.label}</button> : <span>客户 · {relation.customer.label}</span>}
            {onOpenRecordReference ? <button type="button" aria-label={`打开项目记录 ${relation.project.label}`} onClick={() => onOpenRecordReference(relation.project)}>项目 · {relation.project.label}</button> : <span>项目 · {relation.project.label}</span>}
          </div>
        </article>)}</div>
      </section>}
    </aside>
  </main>
}
