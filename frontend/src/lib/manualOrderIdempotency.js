export const buildManualOrderFingerprint = (order) => JSON.stringify([
  order.exchange,
  order.symbol,
  order.action,
  order.order_type,
  order.quantity,
  order.price,
  order.broker_env,
  order.auto_exit,
  order.target_profit_rate,
  order.stop_loss_rate,
  order.auto_exit_execution_mode,
  order.auto_restart_on_partial_fill,
  order.position_side,
  order.reduce_only,
  order.leverage,
  order.margin_type,
])

export const resolveManualOrderIdempotency = (current, fingerprint, createKey) => {
  if (current?.fingerprint === fingerprint && current?.key) {
    return current
  }
  return {
    fingerprint,
    key: createKey(),
  }
}

export const shouldResetManualOrderIdempotency = (responsePayload) => (
  responsePayload?.success === true
  || responsePayload?.error?.code === 'ORDER_NOT_ACCEPTED'
)
