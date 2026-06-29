import threading
import time

from backend.services.market_index_service import (
    collect_market_index_rows,
    is_korean_market_open,
    set_market_index_cache,
)


def start_market_index_scheduler(
    market_index_repository,
    enabled: bool,
    open_interval_seconds: int = 60,
    closed_interval_seconds: int = 600,
) -> None:
    if not enabled:
        return
    if not market_index_repository.is_configured:
        print("[MarketIndexScheduler] Supabase is not configured. Skipping index snapshots.")
        return

    def _loop() -> None:
        while True:
            interval = open_interval_seconds if is_korean_market_open() else closed_interval_seconds
            try:
                rows, errors = collect_market_index_rows()
                if rows:
                    # 새로 수집한 최신값을 메모리 캐시와 DB에 동시에 반영한다.
                    # 메모리는 즉시 응답용이고 DB는 재시작 후 복구용이라 둘 다 갱신해야 한다.
                    set_market_index_cache(rows)
                    market_index_repository.upsert_latest(rows)
                print(
                    "[MarketIndexScheduler] "
                    f"updated={len(rows)} errors={len(errors)} next={interval}s"
                )
            except Exception as error:
                print(f"[MarketIndexScheduler] update failed: {error}")

            time.sleep(interval)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
