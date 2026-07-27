import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import ReactGA from "react-ga4";

const RouteTracker = () => {
  const location = useLocation();
  const [initialized, setInitialized] = useState(false);

  // 1. GA4 초기화 (최초 1회 실행)
  useEffect(() => {
    const gaId = import.meta.env.VITE_GA_TRACKING_ID;
    
    // 개발 모드(npm run dev)이거나 localhost 환경일 경우 GA 수집 제외
    const isDev = import.meta.env.DEV || window.location.hostname === "localhost";

    if (gaId && !isDev) {
      ReactGA.initialize(gaId);
      setInitialized(true);
    }
  }, []);

  // 2. 페이지 URL 변경 감지 및 GA 페이지뷰 전송
  useEffect(() => {
    if (initialized) {
      ReactGA.send({
        hitType: "pageview",
        page: location.pathname + location.search,
      });
    }
  }, [initialized, location]);

  return null;
};

export default RouteTracker;