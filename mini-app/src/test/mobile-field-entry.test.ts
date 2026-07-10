import { readFileSync } from 'node:fs'

import { expect, test } from 'vitest'

test('mobile toolbar keeps authorized field and record creation entries visible', () => {
  const stylesheet = readFileSync('src/styles.css', 'utf8')
  const mobileSection = stylesheet.slice(stylesheet.indexOf('@media (max-width: 900px) { .canvas-header'))

  expect(mobileSection).toContain('.view-tools button.add-field-button { display: inline-flex; }')
  expect(mobileSection).toContain('.view-tools button.create-record-button { display: inline-flex; }')
})
