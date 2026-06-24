import os
import sys
import subprocess
import re
from pathlib import Path
from datetime import datetime, timezone

from backend.utils.file_helpers import (
    read_json_file,
    read_csv_rows,
    count_csv_rows,
    read_model_artifact,
    extract_version_number
)
from backend.services.supabase_client import query_supabase, safe_query_supabase
from backend.services.auth_service import get_user_id_from_header
from backend.services.ml_registry_service import list_model_registry
from backend.services.symbol_metadata import enrich_symbol

PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def build_readiness_payload(auth_header: str) -> dict:
    """ML 자동화 및 모델 서빙을 위한 데이터셋과 API 키 준비 상태 페이로드를 생성합니다."""
    records = query_supabase(auth_header, "user_api_keys", "GET")
    key_status = {
        "TOSS": False,
        "BINANCE": False,
        "COINONE": False,
        "KIS": False,
    }
    toss_record_count = 0
    toss_account_seq_ready = False
    toss_broker_env = None

    for record in records:
        exchange = str(record.get("exchange") or "").upper()
        if exchange in key_status and record.get("encrypted_access_key") and record.get("encrypted_secret_key"):
            key_status[exchange] = True

        if exchange == "TOSS":
            toss_record_count += 1
            if record.get("toss_account_seq"):
                toss_account_seq_ready = True
            if not toss_broker_env and record.get("broker_env"):
                toss_broker_env = record.get("broker_env")

    stock_raw_path = PROJECT_ROOT / "ml" / "data" / "raw" / "stock_candles.csv"
    crypto_raw_path = PROJECT_ROOT / "ml" / "data" / "raw" / "crypto_candles.csv"
    macro_path = PROJECT_ROOT / "ml" / "data" / "raw" / "macro_indices.csv"
    news_path = PROJECT_ROOT / "ml" / "data" / "raw" / "news_features.csv"
    crypto_feature_path = PROJECT_ROOT / "ml" / "data" / "raw" / "crypto_market_features.csv"
    stock_event_path = PROJECT_ROOT / "ml" / "data" / "raw" / "stock_event_features.csv"

    registry_groups = load_registry_groups(auth_header)
    stock_serving = next((row.get("model_version") for row in registry_groups["stock"] if row.get("is_serving")), None)
    crypto_serving = next((row.get("model_version") for row in registry_groups["crypto"] if row.get("is_serving")), None)

    return {
        "keys": {
            "toss_ready": key_status["TOSS"],
            "toss_source": "supabase.user_api_keys -> encrypted_access_key/encrypted_secret_key -> crypto.decrypt",
            "toss_record_count": toss_record_count,
            "toss_account_seq_ready": toss_account_seq_ready,
            "toss_broker_env": toss_broker_env,
            "binance_ready": True,
            "binance_source": "public market candles (no personal key required)",
            "coinone_ready": key_status["COINONE"],
            "kis_ready": key_status["KIS"],
        },
        "datasets": {
            "stock_raw": {
                "path": str(stock_raw_path),
                "exists": stock_raw_path.exists(),
                "rows": count_csv_rows(stock_raw_path),
            },
            "crypto_raw": {
                "path": str(crypto_raw_path),
                "exists": crypto_raw_path.exists(),
                "rows": count_csv_rows(crypto_raw_path),
            },
            "macro_raw": {
                "path": str(macro_path),
                "exists": macro_path.exists(),
                "rows": count_csv_rows(macro_path),
            },
        },
        "feature_sources": {
            "news_features": {
                "path": str(news_path),
                "exists": news_path.exists(),
                "rows": count_csv_rows(news_path),
            },
            "crypto_market_features": {
                "path": str(crypto_feature_path),
                "exists": crypto_feature_path.exists(),
                "rows": count_csv_rows(crypto_feature_path),
            },
            "stock_event_features": {
                "path": str(stock_event_path),
                "exists": stock_event_path.exists(),
                "rows": count_csv_rows(stock_event_path),
            },
        },
        "artifacts": {
            "stock_v6_summary": (PROJECT_ROOT / "ml" / "data" / "processed" / "stock_v6_summary.json").exists(),
            "stock_v7_summary": (PROJECT_ROOT / "ml" / "data" / "processed" / "stock_v7_summary.json").exists(),
            "crypto_v6_summary": (PROJECT_ROOT / "ml" / "data" / "processed" / "crypto_v6_summary.json").exists(),
            "crypto_v7_summary": (PROJECT_ROOT / "ml" / "data" / "processed" / "crypto_v7_summary.json").exists(),
        },
        "registry": {
            "stock_serving": stock_serving,
            "crypto_serving": crypto_serving,
        },
    }

def default_summary_path(filename: str) -> Path:
    """요약 JSON 파일의 기본 저장 경로를 반환합니다."""
    return PROJECT_ROOT / "ml" / "data" / "processed" / filename

def list_experiment_reports(limit: int = 20) -> list[dict]:
    """생성된 실험 리포트(.md) 목록을 조회하여 수정 시간 내림차순으로 반환합니다."""
    reports_dir = PROJECT_ROOT / "ml" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_paths = sorted(
        reports_dir.glob("*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:limit]
    rows = []
    for path in report_paths:
        stat = path.stat()
        rows.append(
            {
                "name": path.name,
                "path": str(path),
                "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "size_bytes": stat.st_size,
            }
        )
    return rows

def run_experiment_report(
    auth_header: str,
    stock_summary: str | None = None,
    crypto_summary: str | None = None,
    output: str | None = None,
) -> dict:
    """LightGBM 모델들의 훈련 지표 및 백테스트 결과를 기반으로 실험 분석 리포트 마크다운 문서를 작성합니다."""
    stock_summary = str(stock_summary or default_summary_path("stock_v6_summary.json"))
    crypto_summary = str(crypto_summary or default_summary_path("crypto_v6_summary.json"))
    reports_dir = PROJECT_ROOT / "ml" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    if output is None:
        output_path = reports_dir / "latest_experiment_report.md"
    else:
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = PROJECT_ROOT / output_path

    timestamped_output_path = reports_dir / f"experiment_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"

    stock_selection = resolve_active_model_selection("stock", auth_header)
    crypto_selection = resolve_active_model_selection("crypto", auth_header)
    stock_serving = (stock_selection or {}).get("serving_version") or "-"
    crypto_serving = (crypto_selection or {}).get("serving_version") or "-"

    python_bin = str(PROJECT_ROOT / "ml" / ".venv" / "bin" / "python")
    if not Path(python_bin).exists():
        python_bin = sys.executable

    command = [
        python_bin,
        "ml/src/write_experiment_report.py",
        "--stock-summary",
        stock_summary,
        "--crypto-summary",
        crypto_summary,
        "--output",
        str(output_path),
        "--stock-serving",
        str(stock_serving),
        "--crypto-serving",
        str(crypto_serving),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or "실험 리포트 생성에 실패했습니다.")

    if output_path != timestamped_output_path:
        timestamped_command = command.copy()
        timestamped_command[timestamped_command.index(str(output_path))] = str(timestamped_output_path)
        timestamped_completed = subprocess.run(
            timestamped_command,
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if timestamped_completed.returncode != 0:
            raise RuntimeError(timestamped_completed.stderr or "타임스탬프 리포트 생성에 실패했습니다.")

    return {
        "output": str(output_path),
        "timestamped_output": str(timestamped_output_path),
        "stock_serving": stock_serving,
        "crypto_serving": crypto_serving,
    }

def build_model_result(asset_key: str, version: int) -> dict:
    """특정 자산과 버전번호를 기준으로 로컬 파일시스템에 적재된 학습 지표, 예측 리스트, 백테스트 내역을 빌드합니다."""
    up_metrics_path = PROJECT_ROOT / "ml" / "models" / f"lgbm_{asset_key}_signal_v{version}.metrics.json"
    risk_metrics_path = PROJECT_ROOT / "ml" / "models" / f"lgbm_{asset_key}_risk_v{version}.metrics.json"
    predictions_path = PROJECT_ROOT / "ml" / "data" / "processed" / f"{asset_key}_predictions_lgbm_v{version}.csv"
    backtest_up_only_path = PROJECT_ROOT / "ml" / "data" / "processed" / f"{asset_key}_backtest_up_only_v{version}.json"
    backtest_composite_path = PROJECT_ROOT / "ml" / "data" / "processed" / f"{asset_key}_backtest_composite_v{version}.json"

    up_metrics = read_json_file(up_metrics_path)
    risk_metrics = read_json_file(risk_metrics_path)
    predictions = [enrich_symbol(row) for row in read_csv_rows(predictions_path, limit=20)]

    return {
        "version": f"v{version}",
        "version_number": version,
        "asset_type": "STOCK" if asset_key == "stock" else "CRYPTO",
        "metrics": up_metrics,
        "risk_metrics": risk_metrics,
        "predictions": predictions,
        "metrics_path": str(up_metrics_path),
        "risk_metrics_path": str(risk_metrics_path),
        "predictions_path": str(predictions_path),
        "backtests": {
            "up_only": read_model_artifact(backtest_up_only_path),
            "composite": read_model_artifact(backtest_composite_path),
        },
        "updated": bool(up_metrics or risk_metrics or predictions),
    }

def discover_model_versions(asset_key: str) -> list[dict]:
    """로컬 ml/configs 디렉토리에서 주어진 자산에 대한 모든 사용 가능한 설정 파일을 바탕으로 모델 정보들을 스캔합니다."""
    config_dir = PROJECT_ROOT / "ml" / "configs"
    config_paths = sorted(
        config_dir.glob(f"lgbm_{asset_key}_v*.yaml"),
        key=extract_version_number,
    )
    return [build_model_result(asset_key, extract_version_number(path)) for path in config_paths]

def pick_default_model_result(version_results: list[dict]) -> dict | None:
    """조회된 모델 결과 중 실제 가공 데이터 및 지표가 업데이트된 가장 최신 버전을 기본 서빙 대상 후보로 지정합니다."""
    if not version_results:
        return None
    updated_results = [result for result in version_results if result.get("updated")]
    if updated_results:
        return max(updated_results, key=lambda item: item.get("version_number", 0))
    return max(version_results, key=lambda item: item.get("version_number", 0))

def score_model_result(result: dict) -> tuple[float, float, float, float, int]:
    """모델 추천 순위를 매기기 위해 초과수익률 및 ROC AUC 점수를 조합한 점수 튜플을 생성합니다."""
    composite_data = result.get("backtests", {}).get("composite", {}).get("data", {}) or {}
    up_only_data = result.get("backtests", {}).get("up_only", {}).get("data", {}) or {}
    composite_excess = float(composite_data.get("excess_return_net") or composite_data.get("excess_return") or 0.0)
    up_only_excess = float(up_only_data.get("excess_return_net") or up_only_data.get("excess_return") or 0.0)
    up_roc_auc = float(
        result.get("metrics", {}).get("time_series_cv_average", {}).get("roc_auc")
        or result.get("metrics", {}).get("roc_auc")
        or 0.0
    )
    risk_roc_auc = float(
        result.get("risk_metrics", {}).get("time_series_cv_average", {}).get("roc_auc")
        or result.get("risk_metrics", {}).get("roc_auc")
        or 0.0
    )
    version_number = int(result.get("version_number") or 0)
    return (composite_excess, up_only_excess, up_roc_auc, risk_roc_auc, version_number)

def pick_recommended_model_result(version_results: list[dict]) -> dict | None:
    """백테스트 초과수익률 및 교차검증 평가지표가 가장 뛰어난 최적의 추천 모델 결과를 선정합니다."""
    updated_results = [result for result in version_results if result.get("updated")]
    if not updated_results:
        return pick_default_model_result(version_results)
    return max(updated_results, key=score_model_result)

def build_registry_fallback(asset_key: str) -> list[dict]:
    """DB에 연결할 수 없는 경우, 로컬 파일시스템의 정보들을 파싱하여 가상 레지스트리 상태 목록을 동적으로 구성합니다."""
    version_results = discover_model_versions(asset_key)
    latest_result = pick_default_model_result(version_results)
    recommended_result = pick_recommended_model_result(version_results)
    registry_map = {
        (str(row.get("asset_type", "")).upper(), str(row.get("model_version", ""))): row
        for row in list_model_registry("STOCK" if asset_key == "stock" else "CRYPTO")
    }
    rows = []
    for result in version_results:
        metrics = result.get("metrics") or {}
        asset_type = "STOCK" if asset_key == "stock" else "CRYPTO"
        model_version = metrics.get("model_version") or f"lgbm_{asset_key}_signal_{result['version']}"
        registry_row = registry_map.get((asset_type, model_version), {})
        rows.append(
            {
                "asset_type": asset_type,
                "model_version": model_version,
                "summary_path": "",
                "metrics_path": result.get("metrics_path"),
                "model_path": result.get("metrics_path", "").replace(".metrics.json", ".joblib"),
                "recommendation_reason": "file-based score comparison",
                "is_latest": bool(latest_result and latest_result.get("version") == result.get("version")),
                "is_recommended": bool(recommended_result and recommended_result.get("version") == result.get("version")),
                "is_serving": bool(registry_row.get("is_serving", False)),
                "approved_by": registry_row.get("approved_by"),
                "approved_at": registry_row.get("approved_at"),
                "updated": result.get("updated", False),
                "version": result.get("version"),
                "version_number": result.get("version_number"),
                "roc_auc": metrics.get("roc_auc"),
                "cv_roc_auc": (metrics.get("time_series_cv_average") or {}).get("roc_auc"),
                "cv_top10_precision": (metrics.get("time_series_cv_average") or {}).get("precision_at_top_10pct"),
            }
        )
    return rows

def load_registry_groups(auth_header: str | None) -> dict[str, list[dict]]:
    """Supabase DB 혹은 로컬 폴백을 통해 주식(STOCK) 및 가상자산(CRYPTO) 레지스트리 목록을 묶어 가져옵니다."""
    registry_rows = []
    if auth_header:
        registry_rows = safe_query_supabase(
            auth_header,
            "ml_model_registry",
            "GET",
            params={"order": "asset_type.asc,updated_at.desc"},
        ) or []

    if registry_rows:
        for row in registry_rows:
            row["version"] = row.get("model_version", "").split("_")[-1] if row.get("model_version") else ""
        stock_rows = [row for row in registry_rows if row.get("asset_type") == "STOCK"]
        crypto_rows = [row for row in registry_rows if row.get("asset_type") == "CRYPTO"]
        return {"stock": stock_rows, "crypto": crypto_rows}

    return {
        "stock": build_registry_fallback("stock"),
        "crypto": build_registry_fallback("crypto"),
    }

def resolve_active_model_selection(asset_key: str, auth_header: str | None) -> dict | None:
    """현재 서빙 중이거나, 없다면 추천 모델 또는 최신 버전을 선정한 후 서빙 현황 및 모델 버전 리스트를 통합하여 반환합니다."""
    registry_groups = load_registry_groups(auth_header)
    version_results = discover_model_versions(asset_key)
    if not version_results:
        return None

    latest_result = pick_default_model_result(version_results)
    recommended_result = pick_recommended_model_result(version_results)
    registry_rows = registry_groups.get(asset_key, [])
    registry_map = {
        str(row.get("model_version") or ""): row
        for row in registry_rows
    }
    serving_version = next((row.get("version") for row in registry_rows if row.get("is_serving")), None)
    latest_version = next(
        (row.get("version") for row in registry_rows if row.get("is_latest")),
        latest_result["version"] if latest_result else None,
    )
    recommended_version = next(
        (row.get("version") for row in registry_rows if row.get("is_recommended")),
        recommended_result["version"] if recommended_result else None,
    )

    decorated_versions = []
    for result in version_results:
        model_version = str((result.get("metrics") or {}).get("model_version") or "")
        registry_row = registry_map.get(model_version, {})
        decorated_versions.append(
            {
                **result,
                "is_serving": bool(registry_row.get("is_serving", False)),
                "is_latest": bool(registry_row.get("is_latest", latest_version == result["version"])),
                "is_recommended": bool(registry_row.get("is_recommended", recommended_version == result["version"])),
                "registry": registry_row,
            }
        )

    selected_version = serving_version or recommended_version or (recommended_result["version"] if recommended_result else None)
    active_result = next(
        (item for item in decorated_versions if item.get("version") == selected_version),
        decorated_versions[0] if decorated_versions else None,
    )
    if not active_result:
        return None

    return {
        "asset_key": asset_key,
        "active_result": active_result,
        "serving_version": serving_version,
        "latest_version": latest_version,
        "recommended_version": recommended_version,
        "versions": decorated_versions,
    }
