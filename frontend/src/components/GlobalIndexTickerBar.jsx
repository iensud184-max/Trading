import { useEffect, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050'
const INDEX_ENDPOINT = `${API_BASE_URL}/api/market/indices`
const REFRESH_INTERVAL_MS = 60000
const ALLOWED_INDEX_KEYS = ['USDKRW', 'KOSPI', 'KOSDAQ', 'NASDAQ100_F', 'SP500']
const INDEX_LABELS = {
  USDKRW: 'USD/KRW',
  KOSPI: 'KOSPI',
  KOSDAQ: 'KOSDAQ',
  NASDAQ100_F: '나스닥 100 선물',
  SP500: 'S&P 500',
}

function formatValue(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '-'

  return numeric.toLocaleString('ko-KR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatDelta(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '-'
  const prefix = numeric > 0 ? '+' : ''
  return `${prefix}${numeric.toLocaleString('ko-KR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function formatPercent(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '-'
  const prefix = numeric > 0 ? '+' : ''
  return `${prefix}${numeric.toFixed(2)}%`
}

function changeClass(direction) {
  if (direction === 'up') return 'text-rose-400'
  if (direction === 'down') return 'text-sky-400'
  return 'text-slate-400'
}

function getDisplayItems(items) {
  const byKey = new Map(items.map((item) => [item.key, item]))

  // We only surface the KIS-backed feeds that are wired into the market index store.
  // 프론트는 서버가 내려주는 여러 필드 이름을 한 번에 흡수해서 표시만 책임진다.
  // 즉, API 응답 구조가 조금 바뀌어도 이 컴포넌트는 가능한 한 그대로 유지되도록 한다.
  return ALLOWED_INDEX_KEYS
    .map((key) => {
      const item = byKey.get(key)
      if (!item) return null
      return {
        ...item,
        label: INDEX_LABELS[key] || item.label || key,
        currentPrice: item.currentPrice ?? item.current_price ?? item.value,
        changePrice: item.changePrice ?? item.change_price ?? item.change,
        changeRate: item.changeRate ?? item.changePercent ?? item.change_rate ?? item.change_percent,
      }
    })
    .filter(Boolean)
}

export default function GlobalIndexTickerBar() {
  const [items, setItems] = useState([])
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    let disposed = false
    let timeoutId = null
    let retryCount = 0

    const scheduleNext = (delayMs) => {
      if (disposed) return
      if (timeoutId) {
        window.clearTimeout(timeoutId)
      }
      timeoutId = window.setTimeout(loadIndices, delayMs)
    }

    const loadIndices = async () => {
      try {
        const response = await fetch(INDEX_ENDPOINT)
        const contentType = response.headers.get('content-type') || ''
        if (!contentType.includes('application/json')) {
          throw new Error('지수 API가 JSON 대신 HTML을 반환했습니다. 백엔드 서버 주소를 확인해 주세요.')
        }
        const payload = await response.json()

        if (!response.ok || !payload.success) {
          throw new Error(payload.message || '지수 데이터를 불러오지 못했습니다.')
        }

        if (!disposed) {
          const nextItems = Array.isArray(payload.data?.items) ? payload.data.items : []
          setItems(getDisplayItems(nextItems))
          setErrorMessage('')
          retryCount = 0
          scheduleNext(REFRESH_INTERVAL_MS)
        }
      } catch (error) {
        if (!disposed) {
          setErrorMessage(error.message || '지수 데이터를 불러오지 못했습니다.')
          retryCount += 1
          const backoffMs = Math.min(REFRESH_INTERVAL_MS * retryCount, 5 * 60 * 1000)
          scheduleNext(backoffMs)
        }
      }
    }

    loadIndices()

    return () => {
      disposed = true
      if (timeoutId) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [])

  if (!items.length && !errorMessage) {
    return null
  }

  return (
    <div className="fixed inset-x-0 bottom-0 z-30 border-t border-[#1f2945] bg-[#07101d]/92 text-slate-100 shadow-[0_-10px_30px_rgba(2,6,23,0.45)] backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-[1600px] items-center gap-3 overflow-x-auto px-4 py-3 sm:px-6">
        <div className="shrink-0 rounded-full border border-cyan-900/60 bg-cyan-950/30 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-300">
          Market
        </div>

        <div className="flex min-w-max items-center gap-2">
          {items.map((item) => (
            <div
              key={item.key}
              className="flex shrink-0 items-center gap-3 rounded-lg border border-[#1f2945] bg-[#0b1628]/95 px-3 py-2 text-sm"
            >
              <div className="flex flex-col">
                <span className="whitespace-nowrap text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                  {item.label}
                </span>
                <span className="whitespace-nowrap font-semibold text-slate-100">
                  {formatValue(item.currentPrice)}
                </span>
              </div>
              <span className={`whitespace-nowrap text-xs font-bold ${changeClass(item.direction)}`}>
                {formatDelta(item.changePrice)} ({formatPercent(item.changeRate)})
              </span>
            </div>
          ))}
        </div>

        {errorMessage && (
          <div className="ml-auto shrink-0 whitespace-nowrap rounded border border-amber-900/60 bg-amber-950/30 px-2 py-1 text-[11px] text-amber-300">
            {errorMessage}
          </div>
        )}
      </div>
    </div>
  )
}
