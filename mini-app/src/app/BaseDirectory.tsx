import type { BaseSummary } from './api'

export type BaseDirectoryState = 'loading' | 'ready' | 'empty' | 'retryable'

type BaseDirectoryProps = {
  state: BaseDirectoryState
  bases: BaseSummary[]
  onOpenBase: (base: BaseSummary) => void
  onHome: () => void
  onRetry: () => void
}

export function BaseDirectory({ state, bases, onOpenBase, onHome, onRetry }: BaseDirectoryProps) {
  if (state === 'loading') {
    return <main className="base-directory" aria-label="Bases" aria-busy="true">正在加载 Bases…</main>
  }

  if (state === 'empty') {
    return <main className="base-directory" aria-label="Bases"><h1>Bases</h1><p>当前工作区没有可访问的 Base。</p><button type="button" onClick={onHome}>返回首页</button></main>
  }

  if (state === 'retryable') {
    return <main className="base-directory" aria-label="Bases"><h1>Bases</h1><p>暂时无法加载 Bases，请稍后重试。</p><div className="base-directory-actions"><button type="button" onClick={onRetry}>重试</button><button type="button" onClick={onHome}>返回首页</button></div></main>
  }

  return <main className="base-directory" aria-label="Bases"><header className="base-directory-heading"><h1>Bases</h1><p>当前工作区中可访问的多维表格。</p></header><div className="base-directory-list" aria-label="Base 列表">{bases.map((base) => <button className="base-directory-row" type="button" key={base.id} aria-label={`打开 ${base.name}`} onClick={() => onOpenBase(base)}><strong>{base.name}</strong><span>{base.source_type === 'blank' ? '多维表格' : base.source_type}</span></button>)}</div></main>
}
