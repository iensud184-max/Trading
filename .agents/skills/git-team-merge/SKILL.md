---
name: git-team-merge
description: >-
  GitHub PR list check, dry-run merge, conflict pinpoint extraction, code compilation verify, and sequential release merge orchestration.
---

# git-team-merge

## Overview
이 스킬은 여러 명의 팀원이 각자 작성한 GitHub Pull Request(PR)들을 검토하고, 병합(Merge)하기 전에 로컬 환경에서 충돌 여부를 사전에 검증하여 안전하게 배포하기 위한 자동화 스킬입니다.
에이전트가 헬퍼 스크립트를 사용하여 PR 목록 조회, 모의 병합, 충돌 마커 영역 추출, 컴파일 유효성 검사를 수행한 뒤, 사용자에게 하나씩 컨펌을 받아 안전하게 머지 및 통합 릴리즈를 수행하도록 규정합니다.

**[PR 상세 분석 보고 지침]**
에이전트는 각 PR의 의도를 분석하여 보고할 때, **어떤 파일들이 수정되었는지 목록(Modified File List)을 명시**하고, 각 파일별로 **구체적으로 어떤 코드 구조나 로직이 변경되었는지를 대조 설명**해야 합니다. 단순 요약에 그치지 않고 구체적인 수식이나 기능 변경 단위를 명확하게 짚어내야 합니다.

**[자동 충돌 해결 규칙 (Auto-Resolution Policy)]**
다음과 같은 유형의 정형화된 코드 충돌이 감지되는 경우, 에이전트는 사용자의 승인 대기를 생략하고 **로컬에서 자동으로 코드를 결합(Merge)한 뒤 즉시 빌드 검증 단계로 직행**합니다.
1. **React useEffect 의존성 배열(`deps`) 충돌**: 두 브랜치에서 각각 추가한 의존성 감시 변수들을 중복 없이 하나로 합칩니다. (예: `[A, B]` vs `[A, C]` ➜ `[A, B, C]`)
2. **React useEffect 내부 함수 호출부 충돌**: 두 브랜치가 추가한 호출 함수들을 모두 유지하여 순차적으로 기동하도록 합성합니다. (예: `func1()` vs `func2()` ➜ 둘 다 순차 실행)
이 규칙을 적용하여 충돌을 해소하고 결과를 사용자에게 사후 공유합니다.

## Dependencies
* **GitHub CLI (gh)**: GitHub API 연동 및 PR 조회/머지 트리거를 위해 필요합니다.
* **Git**: 로컬 브랜치 생성, 머지 드라이런 및 스태시 처리를 위해 필요합니다.

## Quick Start
1. 현재 열려 있는 PR 목록을 확인하여 범위를 선정합니다:
   ```bash
   uv run .agents/skills/git-team-merge/scripts/helper.py list-prs
   ```
2. 병합 대상 PR(실시간 조회된 최신 PR 번호)이 현재 `develop` 브랜치에 충돌 없이 병합되는지 사전에 검사합니다:
   ```bash
   uv run .agents/skills/git-team-merge/scripts/helper.py test-merge --pr <PR_NO> --base develop
   ```
3. 프로젝트 빌드 및 컴파일에 이상이 없는지 확인합니다:
   ```bash
   uv run .agents/skills/git-team-merge/scripts/helper.py verify-build
   ```

## Utility Scripts
스킬 내부의 `scripts/helper.py` 파일은 다음의 서브커맨드들을 지원합니다.

* `list-prs`: 열려 있는 모든 PR의 번호, 제목, 작성자, 브랜치 정보를 JSON 형태로 출력합니다.
* `test-merge --pr <PR_NO> [--base <BASE>]`:
  * `<BASE>` 브랜치(기본값: `develop`)에서 분기된 임시 테스트 브랜치를 생성합니다.
  * 대상 PR의 원격 변경 사항을 머지 드라이런합니다.
  * 충돌이 발생하면 `conflict_report.md` 파일에 충돌 영역의 코드 단편을 라인 번호와 함께 리포트합니다.
  * 진단 후 모든 로컬 상태를 이전 브랜치와 stash 상태로 안전하게 롤백합니다.
* `verify-build`: 백엔드 파일들(`trade.py` 등)의 파이썬 컴파일 상태 및 프론트엔드 `npm run build` 결과의 성공 여부를 검증합니다.
* `merge-pr --pr <PR_NO> [--base <BASE>]`: 해당 PR을 GitHub 상에서 머지 처리하고, 로컬의 대상 브랜치를 풀(Pull) 받아 최신화합니다.
* `release-main [--base <BASE>] [--main <MAIN>]`:
  * `<BASE>` 브랜치에서 `<MAIN>` 브랜치(기본값: `main`)로 PR을 생성합니다.
  * 생성된 PR을 GitHub 상에서 공식 병합 완료(Merge) 처리합니다.

## Rate Limiting
* GitHub CLI(`gh`) 및 GitHub API 호출 시, API 호출 횟수 한도가 있으므로 루프를 돌며 지속적으로 API를 호출하는 폴링(Polling) 행위는 엄격히 제한됩니다. 
* 상태가 변경될 때에만 단발성으로 호출을 수행하십시오.

## Common Mistakes
1. **임시 브랜치 작업 흔적 방치**: `test-merge` 실행 도중 에러가 나거나 강제 종료되어 임시 브랜치(`test-merge-PR-*`)가 삭제되지 않고 남아 있는 경우, 수동으로 `git checkout develop && git branch -D test-merge-PR-{number}` 명령을 수행해 주어야 합니다.
2. **로컬 작업 미보관 분실**: `test-merge`가 시작될 때 로컬의 미커밋 변경 사항이 저장(`git stash`)되나, 간혹 프로세스가 중단되어 원래대로 pop 되지 않은 경우 `git stash pop`을 수동으로 입력해 원복해 주어야 합니다.
3. **충돌 자동 병합 실패**: 충돌이 발생했을 때 에이전트가 임의로 해결하지 말고, `conflict_report.md`에 추출된 충돌 블록을 사용자에게 제시하고 명시적 병합 승인 컨펌을 얻은 뒤 수동 해결해야 합니다.
