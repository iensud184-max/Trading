import assert from 'node:assert/strict'
import test from 'node:test'

import { buildApiErrorText } from './apiError.js'

test('includes a safe request id in structured API error text', () => {
  const text = buildApiErrorText({
    error: {
      title: 'API 키 확인 필요',
      message: '키가 없습니다.',
      action: '설정에서 등록하세요.',
    },
    meta: { request_id: 'req-1' },
  })

  assert.equal(
    text,
    'API 키 확인 필요\n키가 없습니다.\n설정에서 등록하세요.\n요청 ID: req-1',
  )
})

test('does not expose a malformed request id', () => {
  const text = buildApiErrorText({
    message: '요청 처리 실패',
    meta: { request_id: 'req-1\nsecret' },
  })

  assert.equal(text, '요청 처리 실패')
})
