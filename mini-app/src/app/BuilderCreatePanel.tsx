import { type FormEvent, useEffect, useRef, useState } from 'react'

import { ApiError } from './api'

type BaseValues = { baseName: string; tableName: string }
type TableValues = { tableName: string }

type BuilderCreatePanelProps = {
  mode: 'base' | 'table'
  onSubmit: (values: BaseValues | TableValues, idempotencyKey: string) => Promise<void>
  onClose: () => void
}

export function BuilderCreatePanel({ mode, onSubmit, onClose }: BuilderCreatePanelProps) {
  const isBase = mode === 'base'
  const firstInputRef = useRef<HTMLInputElement>(null)
  const attemptKeyRef = useRef<string | null>(null)
  const [baseName, setBaseName] = useState('')
  const [tableName, setTableName] = useState('数据表')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [conflicted, setConflicted] = useState(false)

  useEffect(() => {
    firstInputRef.current?.focus()
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedBaseName = baseName.trim()
    const normalizedTableName = tableName.trim()

    if (isBase && !normalizedBaseName) {
      setError('请填写 Base 名称。')
      return
    }
    if (!normalizedTableName) {
      setError('请填写首张表名称。')
      return
    }

    const idempotencyKey = attemptKeyRef.current ?? crypto.randomUUID()
    attemptKeyRef.current = idempotencyKey
    setSaving(true)
    setError(null)

    try {
      await onSubmit(
        isBase
          ? { baseName: normalizedBaseName, tableName: normalizedTableName }
          : { tableName: normalizedTableName },
        idempotencyKey,
      )
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setError('创建请求发生冲突，请关闭后重新创建。')
        setConflicted(true)
      } else {
        setError('创建失败，请稍后重试。')
      }
    } finally {
      setSaving(false)
    }
  }

  const submitLabel = isBase ? '创建 Base' : '创建数据表'

  return <div className="builder-create-backdrop" role="presentation">
    <aside className="builder-create-panel" aria-labelledby="builder-create-title" aria-modal="true" role="dialog">
      <header>
        <p className="builder-create-eyebrow">BUILDER</p>
        <h2 id="builder-create-title">{isBase ? '新建 Base' : '新建数据表'}</h2>
        <p>{isBase ? '从一个空白 Base 和首张数据表开始。' : '添加一张空白数据表，字段可在下一步配置。'}</p>
      </header>
      <form className="builder-create-form" onSubmit={handleSubmit} noValidate>
        {isBase && <label>
          <span>Base 名称</span>
          <input ref={firstInputRef} value={baseName} onChange={(event) => setBaseName(event.target.value)} placeholder="例如：客户运营" disabled={saving || conflicted} />
        </label>}
        <label>
          <span>{isBase ? '首张表名称' : '数据表名称'}</span>
          <input ref={isBase ? undefined : firstInputRef} value={tableName} onChange={(event) => setTableName(event.target.value)} disabled={saving || conflicted} />
        </label>
        {error && <p className="builder-create-error" role="alert">{error}</p>}
        <div className="builder-create-actions">
          <button type="button" className="button-secondary" onClick={onClose} disabled={saving}>取消</button>
          <button type="submit" className="button-primary" disabled={saving || conflicted}>{saving ? '创建中…' : submitLabel}</button>
        </div>
      </form>
    </aside>
  </div>
}
