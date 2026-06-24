import os
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from backend.utils.file_helpers import sanitize_nan
from backend.services.auth_service import get_user_id_from_header
from backend.services.supabase_client import (
    sync_dataset_job_to_supabase,
    sync_training_job_to_supabase,
    sync_model_registry_to_supabase,
    safe_query_supabase
)
from backend.services.ml_job_service import create_job, list_jobs, run_ml_pipeline, update_job, run_ml_tuning
from backend.services.ml_automation_service import list_automation_presets, resolve_automation_preset
from backend.services.ml_registry_service import list_model_registry, set_serving_model
from backend.services.ml_model_service import (
    build_readiness_payload,
    list_experiment_reports,
    run_experiment_report,
    resolve_active_model_selection,
    load_registry_groups
)
from backend.scripts.export_training_candles import (
    DEFAULT_UNIVERSE_PATH,
    fetch_binance_klines,
    fetch_macro_indices,
    fetch_toss_candles,
    load_preset_symbols,
    write_rows
)

ml_bp = Blueprint("ml", __name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@ml_bp.route("/api/ml/export-candles", methods=["POST"])
def export_ml_candles():
    """관리자 페이지에서 학습용 캔들 CSV를 수동 또는 배치 형태로 생성합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    data = request.json or {}
    asset_type = str(data.get("asset_type", "")).upper()
    exchange = str(data.get("exchange", "")).upper()
    symbols = data.get("symbols") or []
    preset_name = str(data.get("preset") or "").strip() or None
    interval = data.get("interval")
    count = int(data.get("count") or 200)
    sleep_seconds = float(data.get("sleep_seconds") if data.get("sleep_seconds") is not None else 2.0)
    retry = int(data.get("retry") if data.get("retry") is not None else 3)
    retry_wait_seconds = float(data.get("retry_wait_seconds") if data.get("retry_wait_seconds") is not None else 60.0)
    append = bool(data.get("append", True))
    include_macro = bool(data.get("include_macro", False))
    chunk_size = int(data.get("chunk_size") or 0)
    chunk_index = int(data.get("chunk_index") or 1)

    if isinstance(symbols, str):
        symbols = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    else:
        symbols = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]

    if preset_name:
        preset_symbols = load_preset_symbols(preset_name, DEFAULT_UNIVERSE_PATH)
        symbols = list(dict.fromkeys([*symbols, *preset_symbols]))

    if chunk_size > 0:
        start = max(0, (max(1, chunk_index) - 1) * chunk_size)
        end = start + chunk_size
        symbols = symbols[start:end]

    if not symbols:
        return jsonify({"success": False, "message": "수집할 심볼 또는 preset을 입력해 주세요."}), 400

    if count < 1 or count > 1000:
        return jsonify({"success": False, "message": "count는 1 이상 1000 이하로 입력해 주세요."}), 400

    try:
        token = auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else auth_header
        dataset_job = create_job(
            "dataset_export",
            {
                "asset_type": asset_type,
                "exchange": exchange,
                "symbols": symbols,
                "preset_name": preset_name,
                "interval": interval or ("1d" if exchange == "TOSS" else "1h"),
                "count": count,
                "chunk_size": chunk_size or None,
                "chunk_index": chunk_index if chunk_size > 0 else None,
            },
        )

        project_root_path = current_app.config.get("PROJECT_ROOT_PATH", PROJECT_ROOT)

        if include_macro:
            macro_rows = fetch_macro_indices(count)
            macro_output = os.path.join(project_root_path, "ml", "data", "raw", "macro_indices.csv")
            write_rows(macro_output, macro_rows, append=append)

        if exchange == "TOSS" and asset_type == "STOCK":
            rows, failures = fetch_toss_candles(
                symbols,
                token,
                interval or "1d",
                count,
                sleep_seconds=sleep_seconds,
                retry=retry,
                retry_wait_seconds=retry_wait_seconds,
            )
            output = os.path.join(project_root_path, "ml", "data", "raw", "stock_candles.csv")
        elif exchange == "BINANCE" and asset_type == "CRYPTO":
            rows, failures = fetch_binance_klines(
                symbols,
                interval or "1h",
                count,
                sleep_seconds=sleep_seconds,
                retry=retry,
                retry_wait_seconds=retry_wait_seconds,
            )
            output = os.path.join(project_root_path, "ml", "data", "raw", "crypto_candles.csv")
        else:
            return jsonify({"success": False, "message": "지원하지 않는 asset_type/exchange 조합입니다."}), 400

        write_rows(output, rows, append=append)
        update_job(
            dataset_job["id"],
            {
                "status": "success",
                "finished_at": datetime.utcnow().isoformat() + "Z",
                "output": str(output),
                "row_count": len(rows),
                "failure_count": len(failures),
                "failures": failures[:50],
                "append": append,
                "preset_name": preset_name,
                "include_macro": include_macro,
                "chunk_size": chunk_size or None,
                "chunk_index": chunk_index if chunk_size > 0 else None,
            },
        )
        latest_dataset_job = next((job for job in list_jobs(limit=100) if job.get("id") == dataset_job["id"]), None)
        if latest_dataset_job:
            sync_dataset_job_to_supabase(auth_header, latest_dataset_job)

        return jsonify({
            "success": True,
            "message": "학습용 캔들 CSV 생성이 완료되었습니다.",
            "data": {
                "job_id": dataset_job["id"],
                "output": str(output),
                "row_count": len(rows),
                "failure_count": len(failures),
                "failures": failures[:20],
                "symbols": symbols,
                "preset_name": preset_name,
                "asset_type": asset_type,
                "exchange": exchange,
                "interval": interval or ("1d" if exchange == "TOSS" else "1h"),
                "count": count,
                "sleep_seconds": sleep_seconds,
                "retry": retry,
                "retry_wait_seconds": retry_wait_seconds,
                "append": append,
                "include_macro": include_macro,
                "chunk_size": chunk_size or None,
                "chunk_index": chunk_index if chunk_size > 0 else None,
            }
        })
    except Exception as e:
        if "dataset_job" in locals():
            failed_job = update_job(
                dataset_job["id"],
                {
                    "status": "failed",
                    "finished_at": datetime.utcnow().isoformat() + "Z",
                    "error": str(e),
                },
            )
            if failed_job:
                sync_dataset_job_to_supabase(auth_header, failed_job)
        return jsonify({
            "success": False,
            "message": f"학습용 캔들 CSV 생성 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/jobs", methods=["GET"])
def get_ml_jobs():
    """ML 배치 작업 상태 정보 및 이력을 조회합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        get_user_id_from_header(auth_header)
        limit = int(request.args.get("limit", 20))
        return jsonify({
            "success": True,
            "data": {
                "jobs": list_jobs(limit=limit),
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"작업 이력 조회 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/jobs/train", methods=["POST"])
def run_ml_training_job():
    """수동으로 ML 모델 학습 프로세스를 기동합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        get_user_id_from_header(auth_header)
        data = request.json or {}
        config = str(data.get("config") or "").strip()
        risk_config = str(data.get("risk_config") or "").strip() or None
        summary_output = str(data.get("summary_output") or "").strip() or None
        skip_build_features = bool(data.get("skip_build_features", False))
        label = str(data.get("label") or config or "ml-train").strip()

        if not config:
            return jsonify({"success": False, "message": "config 경로가 필요합니다."}), 400

        train_job = create_job(
            "training_run",
            {
                "label": label,
                "config": config,
                "risk_config": risk_config,
                "summary_output": summary_output,
                "skip_build_features": skip_build_features,
            },
        )

        result = run_ml_pipeline(
            config_path=config,
            risk_config_path=risk_config,
            skip_build_features=skip_build_features,
            summary_output=summary_output,
        )

        update_job(
            train_job["id"],
            {
                "status": "success" if result["success"] else "failed",
                "finished_at": datetime.utcnow().isoformat() + "Z",
                "command": result["command"],
                "returncode": result["returncode"],
                "stdout": result["stdout"][-12000:],
                "stderr": result["stderr"][-12000:],
            },
        )
        latest_training_job = next((job for job in list_jobs(limit=100) if job.get("id") == train_job["id"]), None)
        if latest_training_job:
            sync_training_job_to_supabase(auth_header, latest_training_job)
        sync_model_registry_to_supabase(auth_header, summary_output)
        auto_report = None
        if result["success"]:
            try:
                auto_report = run_experiment_report(auth_header=auth_header, output=None)
            except Exception:
                auto_report = None

        status_code = 200 if result["success"] else 500
        return jsonify({
            "success": result["success"],
            "message": "ML 학습 작업이 완료되었습니다." if result["success"] else "ML 학습 작업이 실패했습니다.",
            "data": {
                "job_id": train_job["id"],
                "report": auto_report,
                **result,
            }
        }), status_code
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"ML 학습 작업 실행 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/jobs/tune", methods=["POST"])
def run_ml_tuning_job():
    """Optuna HPO 튜닝 작업을 기동하여 최적의 하이퍼파라미터를 탐색합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        get_user_id_from_header(auth_header)
        data = request.json or {}
        config = str(data.get("config") or "").strip()
        trials = int(data.get("trials", 20))
        update_config = bool(data.get("update_config", False))
        label = f"hpo-tune-{config}"

        if not config:
            return jsonify({"success": False, "message": "config 경로가 필요합니다."}), 400

        tune_job = create_job(
            "hpo_tune",
            {
                "label": label,
                "config": config,
                "trials": trials,
                "update_config": update_config,
            },
        )

        result = run_ml_tuning(
            config_path=config,
            trials=trials,
            update_config=update_config,
        )

        update_job(
            tune_job["id"],
            {
                "status": "success" if result["success"] else "failed",
                "finished_at": datetime.utcnow().isoformat() + "Z",
                "command": result["command"],
                "returncode": result["returncode"],
                "stdout": result["stdout"][-12000:],
                "stderr": result["stderr"][-12000:],
            },
        )
        latest_tune_job = next((job for job in list_jobs(limit=100) if job.get("id") == tune_job["id"]), None)
        if latest_tune_job:
            sync_training_job_to_supabase(auth_header, latest_tune_job)

        status_code = 200 if result["success"] else 500
        return jsonify({
            "success": result["success"],
            "message": "ML 튜닝 작업이 완료되었습니다." if result["success"] else "ML 튜닝 작업이 실패했습니다.",
            "data": {
                "job_id": tune_job["id"],
                **result,
            }
        }), status_code
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"ML 튜닝 작업 실행 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/automation/presets", methods=["GET"])
def get_ml_automation_presets():
    """등록된 자동 수집 및 재학습 설정 프리셋 목록을 조회합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        get_user_id_from_header(auth_header)
        return jsonify({
            "success": True,
            "data": {
                "presets": list_automation_presets(),
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"자동화 프리셋 조회 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/jobs/full-run", methods=["POST"])
def run_ml_full_pipeline_job():
    """지정 프리셋을 기준으로 [데이터셋 추출 + 피처 생성 + 모델 훈련] 전 과정을 일괄 구동합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        get_user_id_from_header(auth_header)
        data = request.json or {}
        preset_key = str(data.get("preset_key") or "").strip()
        if not preset_key:
            return jsonify({"success": False, "message": "preset_key가 필요합니다."}), 400

        preset = resolve_automation_preset(preset_key)
        dataset_config = preset["dataset"]
        training_config = preset["training"]
        token = auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else auth_header

        dataset_job = create_job(
            "dataset_export",
            {
                "label": preset["label"],
                "asset_type": dataset_config["asset_type"],
                "exchange": dataset_config["exchange"],
                "symbols": dataset_config.get("symbols") or [],
                "preset_name": dataset_config.get("preset"),
                "interval": dataset_config["interval"],
                "count": dataset_config["count"],
                "chunk_size": dataset_config.get("chunk_size"),
                "chunk_index": dataset_config.get("chunk_index"),
            },
        )

        preset_symbols = []
        if dataset_config.get("preset"):
            preset_symbols = load_preset_symbols(dataset_config["preset"], DEFAULT_UNIVERSE_PATH)
        symbols = list(dict.fromkeys([*(dataset_config.get("symbols") or []), *preset_symbols]))
        chunk_size = int(dataset_config.get("chunk_size") or 0)
        chunk_index = int(dataset_config.get("chunk_index") or 1)
        if chunk_size > 0:
            start = max(0, (max(1, chunk_index) - 1) * chunk_size)
            end = start + chunk_size
            symbols = symbols[start:end]
        if not symbols:
            raise ValueError("자동화 프리셋에서 실제 수집 심볼이 비어 있습니다.")

        project_root_path = current_app.config.get("PROJECT_ROOT_PATH", PROJECT_ROOT)

        if dataset_config.get("include_macro"):
            macro_rows = fetch_macro_indices(int(dataset_config["count"]))
            macro_output = os.path.join(project_root_path, "ml", "data", "raw", "macro_indices.csv")
            write_rows(macro_output, macro_rows, append=bool(dataset_config.get("append", True)))

        if dataset_config["exchange"] == "TOSS" and dataset_config["asset_type"] == "STOCK":
            rows, failures = fetch_toss_candles(
                symbols,
                token,
                dataset_config["interval"],
                int(dataset_config["count"]),
                sleep_seconds=float(dataset_config.get("sleep_seconds", 2.0)),
                retry=int(dataset_config.get("retry", 3)),
                retry_wait_seconds=float(dataset_config.get("retry_wait_seconds", 60.0)),
            )
            output = os.path.join(project_root_path, "ml", "data", "raw", "stock_candles.csv")
        elif dataset_config["exchange"] == "BINANCE" and dataset_config["asset_type"] == "CRYPTO":
            rows, failures = fetch_binance_klines(
                symbols,
                dataset_config["interval"],
                int(dataset_config["count"]),
                sleep_seconds=float(dataset_config.get("sleep_seconds", 0.2)),
                retry=int(dataset_config.get("retry", 2)),
                retry_wait_seconds=float(dataset_config.get("retry_wait_seconds", 10.0)),
            )
            output = os.path.join(project_root_path, "ml", "data", "raw", "crypto_candles.csv")
        else:
            raise ValueError("지원하지 않는 자동화 dataset 조합입니다.")

        write_rows(output, rows, append=bool(dataset_config.get("append", True)))
        update_job(
            dataset_job["id"],
            {
                "status": "success",
                "finished_at": datetime.utcnow().isoformat() + "Z",
                "output": str(output),
                "row_count": len(rows),
                "failure_count": len(failures),
                "failures": failures[:50],
                "append": bool(dataset_config.get("append", True)),
                "symbols": symbols,
                "preset_name": dataset_config.get("preset"),
            },
        )
        latest_dataset_job = next((job for job in list_jobs(limit=100) if job.get("id") == dataset_job["id"]), None)
        if latest_dataset_job:
            sync_dataset_job_to_supabase(auth_header, latest_dataset_job)

        train_job = create_job(
            "training_run",
            {
                "label": preset["label"],
                "config": training_config["config"],
                "risk_config": training_config.get("risk_config"),
                "summary_output": training_config.get("summary_output"),
                "skip_build_features": bool(training_config.get("skip_build_features", False)),
                "dataset_job_id": dataset_job["id"],
            },
        )
        result = run_ml_pipeline(
            config_path=training_config["config"],
            risk_config_path=training_config.get("risk_config"),
            skip_build_features=bool(training_config.get("skip_build_features", False)),
            summary_output=training_config.get("summary_output"),
        )
        update_job(
            train_job["id"],
            {
                "status": "success" if result["success"] else "failed",
                "finished_at": datetime.utcnow().isoformat() + "Z",
                "command": result["command"],
                "returncode": result["returncode"],
                "stdout": result["stdout"][-12000:],
                "stderr": result["stderr"][-12000:],
            },
        )
        latest_training_job = next((job for job in list_jobs(limit=100) if job.get("id") == train_job["id"]), None)
        if latest_training_job:
            sync_training_job_to_supabase(auth_header, latest_training_job)
        sync_model_registry_to_supabase(auth_header, training_config.get("summary_output"))
        auto_report = None
        if result["success"]:
            try:
                auto_report = run_experiment_report(auth_header=auth_header, output=None)
            except Exception:
                auto_report = None

        status_code = 200 if result["success"] else 500
        return jsonify({
            "success": result["success"],
            "message": "자동 수집+학습 작업이 완료되었습니다." if result["success"] else "자동 수집+학습 작업이 실패했습니다.",
            "data": {
                "preset_key": preset_key,
                "label": preset["label"],
                "dataset_job_id": dataset_job["id"],
                "training_job_id": train_job["id"],
                "dataset_output": str(output),
                "dataset_rows": len(rows),
                "dataset_failures": failures[:20],
                "report": auto_report,
                **result,
            }
        }), status_code
    except Exception as e:
        if "dataset_job" in locals():
            failed_dataset_job = update_job(
                dataset_job["id"],
                {
                    "status": "failed",
                    "finished_at": datetime.utcnow().isoformat() + "Z",
                    "error": str(e),
                },
            )
            if failed_dataset_job:
                sync_dataset_job_to_supabase(auth_header, failed_dataset_job)
        if "train_job" in locals():
            failed_train_job = update_job(
                train_job["id"],
                {
                    "status": "failed",
                    "finished_at": datetime.utcnow().isoformat() + "Z",
                    "error": str(e),
                },
            )
            if failed_train_job:
                sync_training_job_to_supabase(auth_header, failed_train_job)
        return jsonify({
            "success": False,
            "message": f"자동 수집+학습 실행 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/model-results", methods=["GET"])
def get_ml_model_results():
    """훈련 지표 및 예측된 순위 정보를 반환합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        get_user_id_from_header(auth_header)
        results = {}
        for asset_key in ["stock", "crypto"]:
            selection = resolve_active_model_selection(asset_key, auth_header)
            if selection is None:
                continue

            results[asset_key] = {
                **selection["active_result"],
                "selected_version": selection["active_result"]["version"],
                "latest_version": selection["latest_version"],
                "recommended_version": selection["recommended_version"],
                "serving_version": selection["serving_version"],
                "versions": selection["versions"],
            }

        return jsonify({"success": True, "data": sanitize_nan(results)})
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"모델 결과 조회 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/registry", methods=["GET"])
def get_ml_registry():
    """모델 레지스트리에 보관된 리스트를 자산 종류별로 나누어 전달합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        get_user_id_from_header(auth_header)
        registry_groups = load_registry_groups(auth_header)
        stock_rows = registry_groups["stock"]
        crypto_rows = registry_groups["crypto"]

        return jsonify(
            {
                "success": True,
                "data": sanitize_nan({
                    "stock": stock_rows,
                    "crypto": crypto_rows,
                }),
            }
        )
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"모델 레지스트리 조회 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/registry/activate", methods=["POST"])
def activate_ml_registry_version():
    """특정 모델의 버전을 활성화하여 실시간 추론 시그널로 활용하도록 반영합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        user_id, _ = get_user_id_from_header(auth_header)
        data = request.json or {}
        asset_type = str(data.get("asset_type") or "").upper()
        model_version = str(data.get("model_version") or "").strip()

        if asset_type not in ("STOCK", "CRYPTO"):
            return jsonify({"success": False, "message": "asset_type은 STOCK 또는 CRYPTO여야 합니다."}), 400
        if not model_version:
            return jsonify({"success": False, "message": "model_version이 필요합니다."}), 400

        registry_rows = safe_query_supabase(
            auth_header,
            "ml_model_registry",
            "GET",
            params={
                "asset_type": f"eq.{asset_type}",
                "model_version": f"eq.{model_version}",
            },
        )
        file_target = set_serving_model(asset_type, model_version, approved_by=user_id)
        if not registry_rows:
            return jsonify({
                "success": True,
                "message": f"{asset_type} 서비스 반영 버전이 {model_version}으로 변경되었습니다. (file registry)",
                "data": {
                    "asset_type": asset_type,
                    "model_version": model_version,
                    "registry": file_target,
                }
            })

        safe_query_supabase(
            auth_header,
            f"ml_model_registry?asset_type=eq.{asset_type}",
            "PATCH",
            json_data={"is_serving": False},
        )
        safe_query_supabase(
            auth_header,
            f"ml_model_registry?asset_type=eq.{asset_type}&model_version=eq.{model_version}",
            "PATCH",
            json_data={
                "is_serving": True,
                "approved_by": user_id,
                "approved_at": datetime.utcnow().isoformat() + "Z",
            },
        )

        return jsonify({
            "success": True,
            "message": f"{asset_type} 서비스 반영 버전이 {model_version}으로 변경되었습니다.",
            "data": {
                "asset_type": asset_type,
                "model_version": model_version,
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"모델 서비스 반영 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/readiness", methods=["GET"])
def get_ml_readiness():
    """API 키 연동 정보 및 원시 데이터 적재 현황 등을 종합하여 ML 운영 가능 상태 여부를 점검합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        get_user_id_from_header(auth_header)
        return jsonify({
            "success": True,
            "data": build_readiness_payload(auth_header),
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"ML 운영 준비 상태 조회 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/active-model", methods=["GET"])
def get_ml_active_model():
    """현재 백엔드 실시간 감시 엔진이 시그널 추출에 활용 중인 활성 모델의 상세 백테스트 및 버전 정보를 조회합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        get_user_id_from_header(auth_header)
        asset_type = str(request.args.get("asset_type") or "").upper()
        if asset_type not in ("STOCK", "CRYPTO"):
            return jsonify({"success": False, "message": "asset_type은 STOCK 또는 CRYPTO여야 합니다."}), 400

        asset_key = "stock" if asset_type == "STOCK" else "crypto"
        selection = resolve_active_model_selection(asset_key, auth_header)
        if selection is None:
            return jsonify({"success": False, "message": "활성 모델 정보를 찾을 수 없습니다."}), 404

        active_result = selection["active_result"]
        return jsonify({
            "success": True,
            "data": sanitize_nan({
                "asset_type": asset_type,
                "selected_version": active_result.get("version"),
                "model_version": (active_result.get("metrics") or {}).get("model_version"),
                "serving_version": selection["serving_version"],
                "recommended_version": selection["recommended_version"],
                "latest_version": selection["latest_version"],
                "metrics_path": active_result.get("metrics_path"),
                "predictions_path": active_result.get("predictions_path"),
                "backtest_composite": active_result.get("backtests", {}).get("composite", {}).get("data"),
            })
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"활성 모델 조회 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/report", methods=["POST"])
def write_ml_report():
    """수동으로 ML 실험 리포트를 마크다운 문서로 내보냅니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        get_user_id_from_header(auth_header)
        data = request.json or {}
        report_result = run_experiment_report(
            auth_header=auth_header,
            stock_summary=data.get("stock_summary"),
            crypto_summary=data.get("crypto_summary"),
            output=data.get("output"),
        )

        return jsonify({
            "success": True,
            "message": "실험 리포트가 생성되었습니다.",
            "data": report_result,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"실험 리포트 생성 실패: {str(e)}"
        }), 500

@ml_bp.route("/api/ml/reports", methods=["GET"])
def list_ml_reports():
    """지금까지 생성된 모든 마크다운 실험 리포트 목록을 반환합니다."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401

    try:
        get_user_id_from_header(auth_header)
        limit = int(request.args.get("limit", 20))
        return jsonify({
            "success": True,
            "data": {
                "reports": list_experiment_reports(limit=max(1, min(limit, 100))),
            },
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"실험 리포트 목록 조회 실패: {str(e)}"
        }), 500
