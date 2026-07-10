import { Columns3, Plus, Trash2, X } from 'lucide-react'
import { type FormEvent, useEffect, useRef, useState } from 'react'

import { ApiError } from './api'

const choiceFieldTypes = new Set<FieldBuilderValues['fieldType']>([
  'status',
  'single_select',
  'multi_select',
])

const fieldTypeOptions: { value: FieldBuilderValues['fieldType']; label: string }[] = [
  { value: 'text', label: '文本' },
  { value: 'number', label: '数字' },
  { value: 'date', label: '日期' },
  { value: 'status', label: '状态' },
  { value: 'single_select', label: '单选' },
  { value: 'multi_select', label: '多选' },
  { value: 'user', label: '成员' },
  { value: 'checkbox', label: '复选框' },
  { value: 'url', label: '链接' },
  { value: 'email', label: '邮箱' },
  { value: 'phone', label: '电话' },
]

export type FieldBuilderValues = {
  name: string
  fieldType: 'text' | 'number' | 'date' | 'status' | 'single_select' |
    'multi_select' | 'user' | 'checkbox' | 'url' | 'email' | 'phone'
  required: boolean
  choices: string[]
}

type FieldBuilderPanelProps = {
  onSubmit: (values: FieldBuilderValues, idempotencyKey: string) => Promise<void>
  onClose: () => void
}

export function FieldBuilderPanel({ onSubmit, onClose }: FieldBuilderPanelProps) {
  const firstInputRef = useRef<HTMLInputElement>(null)
  const attemptKeyRef = useRef<string | null>(null)
  const [name, setName] = useState('')
  const [fieldType, setFieldType] = useState<FieldBuilderValues['fieldType']>('text')
  const [required, setRequired] = useState(false)
  const [choices, setChoices] = useState([''])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [conflicted, setConflicted] = useState(false)
  const requiresChoices = choiceFieldTypes.has(fieldType)

  useEffect(() => {
    firstInputRef.current?.focus()
  }, [])

  function updateChoice(index: number, value: string) {
    setChoices((current) => current.map((choice, currentIndex) => currentIndex === index ? value : choice))
  }

  function removeChoice(index: number) {
    setChoices((current) => current.length === 1 ? current : current.filter((_, currentIndex) => currentIndex !== index))
  }

  function validate(): FieldBuilderValues | null {
    const normalizedName = name.trim()
    if (!normalizedName) {
      setError('请输入字段名称')
      return null
    }
    if (normalizedName.length > 160) {
      setError('字段名称不能超过 160 个字符')
      return null
    }
    const normalizedChoices = choices.map((choice) => choice.trim())
    if (requiresChoices) {
      if (!normalizedChoices.length || normalizedChoices.some((choice) => !choice)) {
        setError('请填写每个选项')
        return null
      }
      if (normalizedChoices.length > 100 || normalizedChoices.some((choice) => choice.length > 64)) {
        setError('选项数量不能超过 100 个，单个选项不能超过 64 个字符')
        return null
      }
      const choiceKeys = normalizedChoices.map((choice) => choice.toLocaleLowerCase())
      if (new Set(choiceKeys).size !== choiceKeys.length) {
        setError('选项不能重复')
        return null
      }
    }
    return {
      name: normalizedName,
      fieldType,
      required,
      choices: requiresChoices ? normalizedChoices : [],
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = validate()
    if (!values) return

    const idempotencyKey = attemptKeyRef.current ?? crypto.randomUUID()
    attemptKeyRef.current = idempotencyKey
    setSaving(true)
    setError(null)
    try {
      await onSubmit(values, idempotencyKey)
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setError('创建请求发生冲突，请关闭后重新创建。')
        setConflicted(true)
      } else if (caught instanceof ApiError && caught.status === 422 && caught.code === 'duplicate_field_name') {
        setError('字段名称已存在，请使用其他名称。')
      } else {
        setError('创建失败，请稍后重试。')
      }
    } finally {
      setSaving(false)
    }
  }

  return <div className="field-builder-backdrop" role="presentation">
    <aside className="field-builder-panel" aria-labelledby="field-builder-title" aria-modal="true" role="dialog">
      <header className="field-builder-header">
        <div className="field-builder-heading"><span className="field-builder-icon"><Columns3 size={17} /></span><div><p>字段配置</p><h2 id="field-builder-title">添加字段</h2></div></div>
        <button className="field-builder-close" type="button" aria-label="关闭" onClick={onClose} disabled={saving}><X size={18} /></button>
      </header>
      <p className="field-builder-intro">字段会显示在当前数据表的可见列中，可随时在后续阶段继续调整。</p>
      <form className="field-builder-form" onSubmit={handleSubmit} noValidate>
        <label><span>字段名称</span><input ref={firstInputRef} value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：客户阶段" disabled={saving || conflicted} /></label>
        <label><span>字段类型</span><select value={fieldType} onChange={(event) => setFieldType(event.target.value as FieldBuilderValues['fieldType'])} disabled={saving || conflicted}>{fieldTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        <label className="field-builder-required"><input type="checkbox" checked={required} onChange={(event) => setRequired(event.target.checked)} disabled={saving || conflicted} /><span>设为必填字段</span></label>
        {requiresChoices && <section className="field-choice-editor" aria-label="选项设置">
          <div className="field-choice-heading"><span>选项</span><small>按展示顺序保存</small></div>
          <div className="field-choice-list">{choices.map((choice, index) => <div className="field-choice-row" key={index}><input aria-label={`选项 ${index + 1}`} value={choice} onChange={(event) => updateChoice(index, event.target.value)} placeholder={`选项 ${index + 1}`} disabled={saving || conflicted} /><button type="button" aria-label={`移除选项 ${index + 1}`} onClick={() => removeChoice(index)} disabled={choices.length === 1 || saving || conflicted}><Trash2 size={15} /></button></div>)}</div>
          <button className="field-choice-add" type="button" onClick={() => setChoices((current) => [...current, ''])} disabled={saving || conflicted}><Plus size={15} /> 添加选项</button>
        </section>}
        {error && <p className="field-builder-error" role="alert">{error}</p>}
        <footer className="field-builder-actions"><button type="button" className="button-secondary" onClick={onClose} disabled={saving}>取消</button><button type="submit" className="button-primary" disabled={saving || conflicted}>{saving ? '创建中…' : '创建字段'}</button></footer>
      </form>
    </aside>
  </div>
}
