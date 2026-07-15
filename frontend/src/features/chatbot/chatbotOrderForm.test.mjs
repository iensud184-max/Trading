import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

test('자연어 주문은 폼 액션만 열고 조건감시 입력은 없다', () => {
  const source = readFileSync(resolve(__dirname, 'ChatbotWidget.jsx'), 'utf8')

  assert.match(source, /<OrderEntryFlow/)
  assert.match(source, /action\?\.type === 'open_order_form'/)
  assert.match(source, /initialPrefill=\{orderFormPrefill\}/)
  assert.equal(source.includes('ChatOrderForm'), false)
  assert.equal(source.includes('조건감시'), false)
  assert.equal(source.includes('챗봇이 인식한 임시 입력값입니다'), false)
  assert.equal(source.includes('alert('), false)
})
