# Conflict Analysis Report for PR #92

* **Source PR**: #92 (Y-youngchan:yyc)
* **Target Base**: develop
* **Date**: 2026-07-01T21:10:21.592782

## Conflict Details

### File: [frontend/src/pages/AssetDetail.jsx](file:///Users/kangheesung/10-19_개발/13_프로젝트/13.05_트레이딩/teamproject/frontend/src/pages/AssetDetail.jsx)

```diff
2341: <<<<<<< HEAD
2342:                       {getCurrencySign()}{Number(myHolding.avg_price || 0).toLocaleString(undefined, { maximumFractionDigits: getCurrencyDigits() })}
2343:                       {exchange === 'BINANCE_UM_FUTURES' && myHolding.avg_price_source === 'ACCOUNT_FALLBACK' && (
2344:                         <span className="ml-1 text-[9px] text-amber-300">추정</span>
2345:                       )}
2346: =======
2347:                       {formatUnitPrice(myHolding.avg_price)}
2348: >>>>>>> 7cdbbf38662b0cfe119534baa66fd7d1d81da205

```

### File: [frontend/src/pages/AssetsTab.jsx](file:///Users/kangheesung/10-19_개발/13_프로젝트/13.05_트레이딩/teamproject/frontend/src/pages/AssetsTab.jsx)

```diff
342: <<<<<<< HEAD
343:         assetType: isCoin ? 'CRYPTO' : 'STOCK',
344:         source: 'MOCK',
345:         quantityNumeric: qtyNum,
346:         average: formatCurrency(rawAvg, stockCurrency, currentDisplayCurrency),
347: =======
348:         average: formatUnitCurrency(rawAvg, stockCurrency, currentDisplayCurrency),
349: >>>>>>> 7cdbbf38662b0cfe119534baa66fd7d1d81da205

```

