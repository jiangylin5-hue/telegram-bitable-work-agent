import { render, screen } from '@testing-library/react'
import { App } from '../app/App'

test('renders the Mini App workspace landmark', () => {
  render(<App />)
  expect(screen.getByRole('main', { name: '工作台' })).toBeInTheDocument()
})
