import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { MemoryWorkbench } from '../app/MemoryWorkbench'

test('explains memory boundaries and renders only safe memory payloads', () => {
  render(<MemoryWorkbench
    items={[{ memoryType: 'preference', status: 'active', version: 3, payload: { preference: '周报使用风险—动作—需支持格式' }, validUntil: null }]}
    loading={false}
    failed={false}
    onRetry={vi.fn()}
    onClose={vi.fn()}
  />)

  expect(screen.getByText('记忆指导做法，表格决定实时业务事实。')).toBeVisible()
  expect(screen.getByText('偏好')).toBeVisible()
  expect(screen.getByText('周报使用风险—动作—需支持格式')).toBeVisible()
  expect(screen.getByText('知识库重建需要安全知识源目录投影，当前不会让客户端填写或猜测来源 ID。')).toBeVisible()
})
