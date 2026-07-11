function toTimestamp(value) {
  const timestamp = Date.parse(value || '')
  return Number.isFinite(timestamp) ? timestamp : Number.MAX_SAFE_INTEGER
}

function toTimelineOrder(value) {
  if (value === null || value === undefined || value === '') return null
  const order = Number(value)
  return Number.isFinite(order) ? order : null
}

export function formatChatbotProposalNumber(value) {
  if (value === null || value === undefined || value === '') return '-'
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '-'
  return numeric.toLocaleString('ko-KR', { maximumFractionDigits: 8 })
}

export function buildChatbotTimeline(messages = [], pendingProposals = []) {
  return [
    ...messages.map((message) => ({
      type: 'message',
      id: `message-${message.id}`,
      createdAt: message.createdAt,
      timelineOrder: message.timelineOrder,
      data: message,
    })),
    ...pendingProposals.map((proposal) => ({
      type: 'proposal',
      id: `proposal-${proposal.id}`,
      createdAt: proposal.created_at,
      timelineOrder: proposal.timelineOrder,
      data: proposal,
    })),
  ].sort((left, right) => {
    const leftOrder = toTimelineOrder(left.timelineOrder)
    const rightOrder = toTimelineOrder(right.timelineOrder)
    if (leftOrder !== null && rightOrder !== null) return leftOrder - rightOrder
    return toTimestamp(left.createdAt) - toTimestamp(right.createdAt)
  })
}
