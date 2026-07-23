import type { Stage08MemoryItem } from './stage08-memory-types'

type MemoryWorkbenchProps = {
  items: Stage08MemoryItem[]
  loading: boolean
  failed: boolean
  onRetry: () => void
  onClose: () => void
}

const memoryTypeLabel: Record<Stage08MemoryItem['memoryType'], string> = {
  decision: '决策',
  preference: '偏好',
  risk: '风险',
  customer_fact: '客户事实',
  project_fact: '项目事实',
}

function displayValue(value: unknown): string {
  if (value === null) return '未设置'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

export function MemoryWorkbench({ items, loading, failed, onRetry, onClose }: MemoryWorkbenchProps) {
  return <div className="memory-backdrop" role="presentation">
    <aside className="memory-workbench" aria-label="记忆与知识" aria-modal="true" role="dialog">
      <header className="memory-header"><div><p>MEMORY ENGINEERING</p><h2>记忆与知识</h2><span>记忆指导做法，表格决定实时业务事实。</span></div><button type="button" aria-label="关闭记忆与知识" onClick={onClose}>×</button></header>
      {loading ? <section className="memory-state"><p>正在读取当前工作区可见的长期记忆…</p></section> : failed ? <section className="memory-state" role="alert"><p>暂时无法读取长期记忆，请稍后重试。</p><button type="button" onClick={onRetry}>重试</button></section> : <div className="memory-columns">
        <section className="memory-section" aria-label="长期记忆列表"><header><p>ACTIVE MEMORY</p><h3>当前可见的长期记忆</h3></header>{items.length === 0 ? <p>当前没有可见的长期记忆。</p> : <ul>{items.map((item, index) => <li key={`${item.memoryType}:${item.version}:${index}`}><strong>{memoryTypeLabel[item.memoryType]}</strong><small>版本 {item.version}{item.validUntil ? ` · 有效至 ${item.validUntil}` : ''}</small><dl>{Object.entries(item.payload).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{displayValue(value)}</dd></div>)}</dl></li>)}</ul>}</section>
        <section className="memory-section" aria-label="知识库边界"><header><p>KNOWLEDGE</p><h3>知识库如何参与</h3></header><p>知识库资料不会整库塞入模型。协作请求只会在服务端检索当前有权访问、仍有效的资料，并在结果中显示“知识库资料”这一安全证据类别。</p><p>知识库重建需要安全知识源目录投影，当前不会让客户端填写或猜测来源 ID。</p><p>当安全目录契约补齐后，这里会提供带权限、幂等和 ticket 回执的重建操作；页面加载本身不会产生任何写入。</p></section>
      </div>}
    </aside>
  </div>
}
