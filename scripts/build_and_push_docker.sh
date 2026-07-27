#!/usr/bin/env bash
# scripts/build_and_push_docker.sh
set -euo pipefail

# 1. 변수 기본값 설정
DEFAULT_DOCKER_USER="khsung00"
DEFAULT_FRONTEND_TAG="1.0.1"
DEFAULT_BACKEND_TAG="1.0.0"
DEFAULT_PLATFORMS="linux/amd64,linux/arm64"

read -p "Docker Hub 사용자명 입력 (기본값: $DEFAULT_DOCKER_USER): " DOCKER_USER
DOCKER_USER="${DOCKER_USER:-$DEFAULT_DOCKER_USER}"

read -p "프론트엔드 이미지 태그 입력 (기본값: $DEFAULT_FRONTEND_TAG): " FRONTEND_TAG
FRONTEND_TAG="${FRONTEND_TAG:-$DEFAULT_FRONTEND_TAG}"

read -p "백엔드 이미지 태그 입력 (기본값: $DEFAULT_BACKEND_TAG): " BACKEND_TAG
BACKEND_TAG="${BACKEND_TAG:-$DEFAULT_BACKEND_TAG}"

read -p "빌드 플랫폼 입력 (기본값: $DEFAULT_PLATFORMS): " PLATFORMS
PLATFORMS="${PLATFORMS:-$DEFAULT_PLATFORMS}"

export DOCKER_USER
export FRONTEND_TAG
export BACKEND_TAG
export PLATFORMS

echo ""
echo "=== Docker Hub 빌드 및 푸시 설정 ==="
echo "Docker Hub 계정   : $DOCKER_USER"
echo "프론트엔드 태그   : $FRONTEND_TAG"
echo "백엔드 태그       : $BACKEND_TAG"
echo "빌드 플랫폼       : $PLATFORMS"
echo "대상 이미지       : "
echo "  - $DOCKER_USER/trading-frontend:$FRONTEND_TAG"
echo "  - $DOCKER_USER/trading-backend:$BACKEND_TAG"
echo "====================================="
echo ""

# 2. Docker Login 점검
echo "Docker Hub 로그인 상태를 점검합니다..."
if ! docker info >/dev/null 2>&1; then
  echo "[에러] Docker 데몬이 실행 중이지 않습니다. Docker를 실행해주세요." >&2
  exit 1
fi

# 도커허브 로그인 확인 시도
if ! docker system info 2>/dev/null | grep -q "Username"; then
  echo "Docker Hub에 로그인되어 있지 않습니다. 로그인을 시도합니다..."
  docker login
fi

if ! docker buildx inspect >/dev/null 2>&1; then
  echo "[에러] Docker buildx builder를 사용할 수 없습니다." >&2
  exit 1
fi

if [ -f frontend/.env ]; then
  set -a
  # frontend/.env에는 VITE_ 공개 환경변수만 둡니다.
  # shellcheck disable=SC1091
  . frontend/.env
  set +a
fi

VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:8080}"
export VITE_API_BASE_URL

# 3. 멀티 플랫폼 이미지 빌드 및 푸시
echo "[1/2] 백엔드 멀티 플랫폼 이미지를 빌드하고 푸시합니다..."
docker buildx build \
  --platform "$PLATFORMS" \
  -t "$DOCKER_USER/trading-backend:$BACKEND_TAG" \
  -f Dockerfile \
  --push \
  .

echo "[2/2] 프론트엔드 멀티 플랫폼 이미지를 빌드하고 푸시합니다..."
docker buildx build \
  --platform "$PLATFORMS" \
  -t "$DOCKER_USER/trading-frontend:$FRONTEND_TAG" \
  -f frontend/Dockerfile \
  --build-arg VITE_SUPABASE_URL \
  --build-arg VITE_SUPABASE_ANON_KEY \
  --build-arg VITE_API_BASE_URL \
  --push \
  .

echo ""
echo "=========================================================="
echo " Docker Hub 멀티 플랫폼 업로드가 성공적으로 완료되었습니다!"
echo " - Frontend 이미지: $DOCKER_USER/trading-frontend:$FRONTEND_TAG"
echo " - Backend 이미지 : $DOCKER_USER/trading-backend:$BACKEND_TAG"
echo " - Platforms      : $PLATFORMS"
echo "=========================================================="
