# plan_gen 현재 상태

## 요약
설계서(v2) 1~8단계 완료. 전체 파이프라인이 실제로 연결되어 10개월 샘플에 돌아감.
9/10개월 정상 렌더링, 겹침 0건. 남은 건 9단계(신규 월 실사용 테스트)와
이미지 에셋 저장소 확인.

- 마스터 템플릿: `templates/master_template.md` (기준: 202605)
- 블록타입 분류(10개월): `templates/block_type_classification.md`
- 블록 엔진(5개 함수, A/E 통합): `tools/blocks/`
- 회귀 채점기: `tools/regression.py`
- 고정 필드 파서: `tools/parse_fixed_fields.py`
- 특별보상 원문 추출(셀+드로잉 텍스트박스+이미지유무): `tools/extract_special_reward.py`
- AI 분류기(Haiku→Sonnet 에스컬레이션): `tools/classify_month.py`, `tools/ai_client.py`
- 아이템 위치 역매칭 + 이미지 매칭: `tools/locate_items.py`, `tools/extract_images.py`, `tools/match_images.py`
- 외부 에셋 저장소 조회 인터페이스(스텁, 미구현): `tools/asset_repository.py`
- **전체 파이프라인 연결**: `tools/pipeline.py` (`process_month()`)
- 테스트: `tests/` — 66개 전체 통과 (`.venv/Scripts/python.exe -m pytest tests/`)

## 8단계 회귀 실행 결과 (10개월 전체, 실제 API)
9/10개월 정상 렌더링, **모든 페이지에서 겹침 0건**. 5개 블록타입 전부 실사용 데이터에서
동작 확인. 202602(설계서가 원래 버그 파일로 지목한 샘플)만 AI 응답 스키마 이상으로
NeedsHumanReview 발동 — 억지로 추측하지 않고 정상적으로 사람에게 넘김.
상세 로그: `out/regression_run_10months.txt` (gitignore 대상, 재실행으로 재생성 가능:
`tools/pipeline.py`의 `process_month()`를 월별로 호출).

이미지 매칭률은 0~94%로 월마다 편차가 큼 — 이건 버그가 아니라 7단계에서 발견한
"에셋 저장소 미확인" 문제 때문 (아래 항목 참고).

## ⚠️ 확인 필요 (여전히 미해결)
아이템 이름/ID로 조회 가능한 이미지 에셋 저장소가 실제로 있는지 팀 확인 필요.
`tools/asset_repository.py`가 조회 로직 없이 스텁 상태로 남아있음 — 확인되면
그 파일 안의 `lookup_image_by_name()`만 구현하면 나머지 파이프라인은 안 건드려도 됨.

## 최근 5건
1. 8단계: 파이프라인 전체 연결(`tools/pipeline.py`), 10개월 실사용 데이터로 회귀 실행.
   9/10 정상, 겹침 0건. 이 과정에서 `ai_client.py`의 실제 견고성 문제 2개 발견/수정
   (max_tokens 2048→4096 truncation 위험, 모델이 가끔 중첩 배열을 JSON 문자열로
   잘못 반환하는 문제에 대한 방어적 파싱 추가)
2. 7단계: 위치 기반 이미지 매칭 구현. 202605 종단 테스트에서 매칭률 0% 확인 →
   에셋 저장소 미확인 문제 실증. 사용자 지시로 저장소 없다고 가정하고 인터페이스
   스텁만 비워두는 구조로 마무리
3. 6단계: AI 분류기 구현, 실제 API 키로 검증. 202508 grid/text_list 오분류 발견 후
   "[이미지있음]" 마커 추가로 수정 (0.72→0.92 신뢰도 상승)
4. 5단계: 고정 필드 파서 완료, 10개월 전수 검증 통과
5. 4단계: 회귀 채점기(text/image match rate, overlap count) 구현

## 다음 단계
9단계: 신규 월 실사용 테스트 (design doc상 마지막 단계). 이미지 에셋 저장소 확인이
먼저 되면 이미지 커버리지가 크게 개선될 것으로 보임 — 확인 전에 9단계를 해도 되지만
이미지 부분은 대부분 text_only로 나올 것.
