import {
  formatDecimalMetric,
  formatMetric,
  formatPercent,
  formatProbability,
  formatRatio,
  formatReturnPercent,
  formatSignalScore,
  formatStaleness,
  getPolicyReasonLabels,
  getProbabilityLevel,
  getSignalGradeLabel,
  getSignalGradeTone,
} from './assetDetailModel.js'

const buildMlSignalInterpretation = (signal, resolvedAssetType, isResolvedUsStock) => {
  if (!signal) return null
  const up = getProbabilityLevel(signal.up_probability, 'up')
  const risk = getProbabilityLevel(signal.risk_probability, 'risk')
  const grade = String(signal.signal_grade || '')
  const position = String(signal.position || '').toUpperCase()
  const isRisky = grade === 'RISKY' || Number(signal.risk_probability) >= 0.6
  const isCandidate = grade === 'STRONG_BUY_CANDIDATE' || position === 'LONG'
  const actionLabel = isRisky ? '주의' : isCandidate ? '후보' : '관망'
  const actionTone = isRisky
    ? 'border-rose-500/40 bg-rose-950/30 text-rose-200'
    : isCandidate
      ? 'border-emerald-500/40 bg-emerald-950/25 text-emerald-200'
      : 'border-cyan-500/35 bg-cyan-950/20 text-cyan-100'
  const reason = isRisky
    ? '하락 위험 또는 정책 차단 신호가 있어 매수보다 리스크 확인이 먼저입니다.'
    : isCandidate
      ? '상승 신호가 우세하고 현재 정책 필터를 통과한 후보입니다.'
      : '매수/매도 결론보다 관찰이 더 적합한 상태입니다.'

  return {
    actionLabel,
    actionTone,
    up,
    risk,
    reason,
    modelScope: resolvedAssetType === 'CRYPTO'
      ? '코인 전용 모델'
      : isResolvedUsStock
        ? '해외주식 모델'
        : '국내주식 모델',
  }
}

export default function AssetDetailMlSignalPanel({
  isMlSignalExpanded,
  setIsMlSignalExpanded,
  mlSignal,
  mlSignalLoading,
  mlSignalMessage,
  resolvedAssetType,
  isResolvedUsStock,
  onFetchMlSignal,
}) {
  return (
    <>
            {/* AI 시그널 카드 */}
            <div className="bg-[#0e1529]/90 border border-cyan-500/30 rounded-xl p-4 flex flex-col gap-3 backdrop-blur-md">
              <div className="flex items-start justify-between gap-3 border-b border-[#1f2945] pb-2">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-cyan-300">AI Signal</span>
                  <h2 className="mt-1 text-xs font-bold text-white">ML 참고 신호</h2>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setIsMlSignalExpanded((prev) => !prev)}
                    className="rounded border border-slate-700 px-2 py-1 text-[10px] font-bold text-slate-300 transition hover:border-cyan-500/30 hover:text-white"
                  >
                    {isMlSignalExpanded ? '접기' : '펼치기'}
                  </button>
                  <button
                    type="button"
                    onClick={onFetchMlSignal}
                    disabled={mlSignalLoading}
                    className="rounded border border-cyan-500/30 px-2 py-1 text-[10px] font-bold text-cyan-300 transition hover:bg-cyan-950/30 disabled:opacity-50"
                  >
                    {mlSignalLoading ? '조회 중' : '갱신'}
                  </button>
                </div>
              </div>

              {!isMlSignalExpanded ? (
                <div className="rounded border border-[#1f2945] bg-[#070b19] px-3 py-3 text-[11px] leading-5 text-slate-400">
                  펼쳐서 ML 참고 신호를 확인할 수 있습니다.
                </div>
              ) : mlSignalLoading ? (
                <div className="rounded border border-[#1f2945] bg-[#070b19] px-3 py-4 text-center text-[11px] font-mono text-cyan-300">
                  활성 모델 신호 확인 중...
                </div>
              ) : mlSignal ? (
                <div className="flex flex-col gap-3">
                  {(() => {
                    const interpretation = buildMlSignalInterpretation(mlSignal, resolvedAssetType, isResolvedUsStock)
                    if (!interpretation) return null

                    return (
                      <div className={`rounded-lg border px-3 py-3 ${interpretation.actionTone}`}>
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <p className="text-[10px] font-bold uppercase tracking-[0.16em] opacity-80">AI 참고 판단</p>
                            <p className="mt-1 text-lg font-black text-white">{interpretation.actionLabel}</p>
                          </div>
                          <div className="flex flex-wrap gap-2 text-[10px] font-bold">
                            <span className="rounded border border-white/15 bg-black/15 px-2 py-1">{interpretation.modelScope}</span>
                            <span className="rounded border border-white/15 bg-black/15 px-2 py-1">
                              {mlSignal.meta?.serving_version ? '서비스 모델' : '추천/최신 모델'}
                            </span>
                          </div>
                        </div>
                        <p className="mt-3 break-words text-xs leading-5 text-slate-100">{interpretation.reason}</p>
                        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                          <div className="rounded border border-white/10 bg-black/15 p-2">
                            <p className="text-[10px] text-slate-300">상승 가능성</p>
                            <p className={`mt-1 text-sm font-black ${interpretation.up.tone}`}>
                              {interpretation.up.label} <span className="font-mono text-xs">({formatProbability(mlSignal.up_probability)})</span>
                            </p>
                            <p className="mt-1 text-[10px] leading-4 text-slate-300">{interpretation.up.detail}</p>
                          </div>
                          <div className="rounded border border-white/10 bg-black/15 p-2">
                            <p className="text-[10px] text-slate-300">하락 위험</p>
                            <p className={`mt-1 text-sm font-black ${interpretation.risk.tone}`}>
                              {interpretation.risk.label} <span className="font-mono text-xs">({formatProbability(mlSignal.risk_probability)})</span>
                            </p>
                            <p className="mt-1 text-[10px] leading-4 text-slate-300">{interpretation.risk.detail}</p>
                          </div>
                        </div>
                      </div>
                    )
                  })()}

                  {(() => {
                    const performance = mlSignal.meta?.performance
                    if (!performance) return null

                    return (
                      <div className="rounded border border-emerald-900/30 bg-emerald-950/10 px-3 py-2">
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-[9px] font-bold uppercase tracking-[0.18em] text-emerald-300">Model Quality</span>
                          <span className="text-[9px] text-slate-500">최근 활성 모델 기준</span>
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-2">
                          <div className="rounded border border-[#1f2945] bg-[#070b19] p-2">
                            <p className="text-[9px] text-slate-500">CV ROC AUC</p>
                            <p className="mt-1 font-mono text-xs font-bold text-white">{formatMetric(performance.cv_roc_auc)}</p>
                          </div>
                          <div className="rounded border border-[#1f2945] bg-[#070b19] p-2">
                            <p className="text-[9px] text-slate-500">상위 10% 적중</p>
                            <p className="mt-1 font-mono text-xs font-bold text-white">{formatPercent(performance.precision_at_top_10pct)}</p>
                          </div>
                          <div className="rounded border border-[#1f2945] bg-[#070b19] p-2">
                            <p className="text-[9px] text-slate-500">복합 초과수익</p>
                            <p className="mt-1 font-mono text-xs font-bold text-emerald-300">{formatReturnPercent(performance.composite_excess_return_net)}</p>
                          </div>
                          <div className="rounded border border-[#1f2945] bg-[#070b19] p-2">
                            <p className="text-[9px] text-slate-500">최대 낙폭</p>
                            <p className="mt-1 font-mono text-xs font-bold text-rose-300">{formatReturnPercent(performance.composite_max_drawdown_net)}</p>
                          </div>
                        </div>
                      </div>
                    )
                  })()}

                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded border px-2 py-1 text-[10px] font-black tracking-widest ${getSignalGradeTone(mlSignal.signal_grade)}`}>
                      {getSignalGradeLabel(mlSignal.signal_grade)}
                    </span>
                    <span className="rounded border border-slate-700 bg-slate-900/70 px-2 py-1 text-[10px] font-bold text-slate-300">
                      {mlSignal.position || 'HOLD'}
                    </span>
                    <span className="rounded border border-cyan-500/20 bg-cyan-950/20 px-2 py-1 text-[10px] font-bold text-cyan-300">
                      {mlSignal.model_version || mlSignal.meta?.model_version || '-'}
                    </span>
                  </div>

                  <p className="break-words text-[11px] leading-5 text-slate-300">
                    {mlSignal.reason_summary || '현재 모델 신호를 요약할 수 없습니다.'}
                  </p>

                  {getPolicyReasonLabels(mlSignal).length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {getPolicyReasonLabels(mlSignal).slice(0, 4).map((reason) => (
                        <span
                          key={reason}
                          className="rounded border border-slate-700/80 bg-slate-900/70 px-2 py-1 text-[9px] font-bold text-slate-300"
                        >
                          {reason}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="grid grid-cols-3 gap-2">
                    <div className="rounded border border-[#1f2945] bg-[#070b19] p-2">
                      <p className="text-[9px] text-slate-500">상승 확률</p>
                      <p className="mt-1 font-mono text-xs font-bold text-emerald-300">{formatProbability(mlSignal.up_probability)}</p>
                    </div>
                    <div className="rounded border border-[#1f2945] bg-[#070b19] p-2">
                      <p className="text-[9px] text-slate-500">하락 위험</p>
                      <p className="mt-1 font-mono text-xs font-bold text-amber-300">{formatProbability(mlSignal.risk_probability)}</p>
                    </div>
                    <div className="rounded border border-[#1f2945] bg-[#070b19] p-2">
                      <p className="text-[9px] text-slate-500">복합 점수</p>
                      <p className="mt-1 font-mono text-xs font-bold text-cyan-300">{formatSignalScore(mlSignal.signal_score)}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="rounded border border-[#1f2945] bg-[#070b19] p-2">
                      <p className="text-[9px] text-slate-500">진입 거리</p>
                      <p className="mt-1 font-mono text-xs font-bold text-white">{formatDecimalMetric(mlSignal.long_entry_distance, 3)}</p>
                    </div>
                    <div className="rounded border border-[#1f2945] bg-[#070b19] p-2">
                      <p className="text-[9px] text-slate-500">거래량 확인</p>
                      <p className={`mt-1 font-mono text-xs font-bold ${Number(mlSignal.volume_ratio_5 || 0) >= 0.7 ? 'text-emerald-300' : 'text-amber-300'}`}>
                        {formatRatio(mlSignal.volume_ratio_5)}
                      </p>
                    </div>
                    <div className="rounded border border-[#1f2945] bg-[#070b19] p-2">
                      <p className="text-[9px] text-slate-500">시장 폭</p>
                      <p className="mt-1 font-mono text-xs font-bold text-slate-200">{formatProbability(mlSignal.market_breadth_5)}</p>
                    </div>
                    <div className="rounded border border-[#1f2945] bg-[#070b19] p-2">
                      <p className="text-[9px] text-slate-500">섹터 강도</p>
                      <p className="mt-1 font-mono text-xs font-bold text-slate-200">{formatDecimalMetric(mlSignal.sector_strength_score, 2)}</p>
                    </div>
                  </div>

                  <div className="rounded border border-[#1f2945] bg-[#070b19]/80 px-3 py-2 text-[10px] leading-4 text-slate-400">
                    <div className="flex justify-between gap-3">
                      <span>추천 티어</span>
                      <span className="font-mono font-bold text-white">{mlSignal.recommendation_tier || mlSignal.position || '-'}</span>
                    </div>
                    <div className="mt-1 flex justify-between gap-3">
                      <span>정책 국면</span>
                      <span className="font-mono font-bold text-white">{mlSignal.market_regime_state || '-'}</span>
                    </div>
                    <div className="mt-1 flex justify-between gap-3">
                      <span>조정 스프레드</span>
                      <span className="font-mono font-bold text-white">{formatDecimalMetric(mlSignal.adjusted_composite_spread, 3)}</span>
                    </div>
                  </div>

                  <div className="rounded border border-amber-900/40 bg-amber-950/10 px-3 py-2 text-[9px] leading-4 text-amber-300">
                    AI 신호는 주문 실행 근거가 아니라 참고 지표입니다. 주문 전 사전검증과 사용자 승인을 우선합니다.
                  </div>

                  <p className="font-mono text-[10px] text-slate-500">
                    예측 {formatStaleness(mlSignal.staleness_minutes)} · {mlSignal.predicted_at || mlSignal.date || '-'}
                  </p>
                </div>
              ) : (
                <div className="rounded border border-[#1f2945] bg-[#070b19] px-3 py-4 text-[11px] leading-5 text-slate-400">
                  {mlSignalMessage || '현재 표시할 AI 시그널이 없습니다.'}
                </div>
              )}
            </div>
            
    </>
  )
}
