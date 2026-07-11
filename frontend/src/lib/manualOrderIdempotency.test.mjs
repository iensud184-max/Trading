import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildManualOrderFingerprint,
  resolveManualOrderIdempotency,
  shouldResetManualOrderIdempotency,
} from './manualOrderIdempotency.js'

test('동일한 수동 주문 재시도는 같은 멱등성 키를 재사용한다', () => {
  const fingerprint = buildManualOrderFingerprint({
    exchange: 'COINONE',
    symbol: 'XRP',
    action: 'BUY',
    order_type: 'LIMIT',
    quantity: 10,
    price: 800,
  })
  const first = resolveManualOrderIdempotency(null, fingerprint, () => 'key-1')
  const second = resolveManualOrderIdempotency(first, fingerprint, () => 'key-2')

  assert.equal(second.key, 'key-1')
})

test('주문 조건이 바뀌면 새 멱등성 키를 생성한다', () => {
  const first = resolveManualOrderIdempotency(null, 'order-a', () => 'key-1')
  const second = resolveManualOrderIdempotency(first, 'order-b', () => 'key-2')

  assert.equal(second.key, 'key-2')
})

test('확정적 미접수 응답은 새 주문을 위해 키를 초기화한다', () => {
  assert.equal(shouldResetManualOrderIdempotency({
    success: false,
    error: { code: 'ORDER_NOT_ACCEPTED' },
  }), true)
  assert.equal(shouldResetManualOrderIdempotency({
    success: false,
    error: { code: 'ORDER_RECEIPT_PERSIST_FAILED' },
  }), false)
})
