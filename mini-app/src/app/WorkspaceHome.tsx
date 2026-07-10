import { ArrowUpRight, Bot, CheckCircle2, ChevronRight, CircleDot, Search } from 'lucide-react'

import type { Workspace, WorkspaceHome as WorkspaceHomeData } from './api'

type WorkspaceHomeProps = { home: WorkspaceHomeData; workspace: Workspace }

export function WorkspaceHome({ home, workspace }: WorkspaceHomeProps) {
  return <main className="workspace-home" aria-label="工作区首页">
    <section className="queue-surface" aria-labelledby="today-work-heading">
      <header className="page-toolbar"><div><h1 id="today-work-heading">今天工作</h1><p>{workspace.name} · 当前需处理的持久化事项</p></div><div className="toolbar-actions"><button type="button"><Search size={17} /> 搜索</button><button type="button">按时间排序 <ChevronRight size={15} /></button></div></header>
      <div className="queue-section-title"><span className="section-icon blue"><CircleDot size={16} /></span><h2>待确认</h2><span className="count">{home.queue.length}</span></div>
      {home.queue.length > 0 ? <div className="queue-list" aria-label="待确认队列">{home.queue.map((item) => <article className="queue-row" key={item.id}><span className="row-check" aria-hidden="true" /><span className="record-icon"><CheckCircle2 size={16} /></span><div className="queue-row-main"><strong>{item.title}</strong><span>草稿 #{item.destination.draft_id.slice(0, 8)}</span></div><span className="queue-status">等待你的决定</span><a href={`#draft/${item.destination.draft_id}`} className="row-link">查看草稿 <ArrowUpRight size={14} /></a></article>)}</div> : <div className="empty-queue">没有待确认的变更。</div>}
    </section>
    <aside className="base-rail" aria-labelledby="recent-bases-heading"><div className="rail-heading"><h2 id="recent-bases-heading">最近 Base</h2><a href="#bases">全部 <ChevronRight size={15} /></a></div><div className="base-list">{home.recent_bases.map((base, index) => <a className="base-preview" href={`#base/${base.id}`} key={base.id} aria-label={base.name}><div className="base-preview-title"><span className={`base-glyph glyph-${index % 3}`}>▣</span><strong>{base.name}</strong></div><span className="base-kind">{base.source_type === 'blank' ? '多维表格' : base.source_type}</span><div className="preview-grid" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /><i /></div></a>)}</div></aside>
    <aside className="assistant-dock" aria-label="个人助理"><div className="assistant-title"><Bot size={19} /><strong>个人助理</strong><ChevronRight size={16} /></div><p>你好，{workspace.name}</p><span>需要时选择上下文，再开始协作。</span><button type="button">快速查找记录 <ChevronRight size={16} /></button><button type="button">新建记录 <ChevronRight size={16} /></button><button type="button">智能汇总 <ChevronRight size={16} /></button></aside>
  </main>
}
