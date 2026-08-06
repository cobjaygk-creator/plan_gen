# plan_gen 현재 상태

## 요약
설계서(v2) 1~8단계 + .pptx 렌더러까지 완료. **request.xlsx를 넣으면 진짜 .pptx가
나오는 전체 파이프라인이 처음부터 끝까지 동작함** (202605로 실증: 4슬라이드,
23개 아이템 전부 포함, NEW 배지 정상). 남은 건 9단계(신규 월 실사용 테스트)뿐.

- 마스터 템플릿: `templates/master_template.md` (기준: 202605)
- 블록타입 분류(10개월): `templates/block_type_classification.md`
- 블록 엔진(5개 함수, A/E 통합): `tools/blocks/`
- 회귀 채점기: `tools/regression.py`
- 고정 필드 파서: `tools/parse_fixed_fields.py`
- 특별보상 원문 추출(셀+드로잉 텍스트박스+이미지유무): `tools/extract_special_reward.py`
- AI 분류기(Haiku→Sonnet 에스컬레이션): `tools/classify_month.py`, `tools/ai_client.py`
- 아이템 위치 역매칭 + 이미지 매칭(요청서 내 위치 매칭만): `tools/locate_items.py`, `tools/extract_images.py`, `tools/match_images.py`
- 전체 파이프라인 연결: `tools/pipeline.py` (`process_month()`)
- **.pptx 렌더러**: `tools/render_pptx.py` (`render_pptx()`) — 처음으로 진짜 산출물 생성
- 테스트: `tests/` — 67개 전체 통과 (`.venv/Scripts/python.exe -m pytest tests/`)

## 8단계 회귀 실행 결과 (10개월 전체, 실제 API)
9/10개월 정상 렌더링, **모든 페이지에서 겹침 0건**. 5개 블록타입 전부 실사용 데이터에서
동작 확인. 202602(설계서가 원래 버그 파일로 지목한 샘플)만 AI 응답 스키마 이상으로
NeedsHumanReview 발동 — 억지로 추측하지 않고 정상적으로 사람에게 넘김.

이미지 매칭률은 0~94%로 월마다 편차가 큼 — 사업팀이 요청서에 이미지를 얼마나
첨부했는지에 따른 자연스러운 편차로 확정됨. 매칭 안 되는 항목은 텍스트만 있는
placeholder 박스로 렌더링됨 (빈 화면 아님, 이름은 항상 보임).

## 결정된 사항
- **이미지 소스는 요청서 첨부 이미지 하나뿐.** 별도 에셋 저장소 없음 — 확인 완료.
- 이미지 화질: 원본 그대로, 카드 크기에 맞춰 리사이즈만. 화질 검증/업스케일링 없음.
- 렌더러는 마스터 템플릿의 정확한 XML 스타일(테마 색상, 테두리 등)까지 재현하지
  않음 — 회귀 채점이 실제로 보는 건 텍스트/이미지 유무·겹침이지 픽셀 일치가 아님.

## 최근 5건
1. .pptx 렌더러 구현 — Placement 좌표를 실제 슬라이드로 변환하는 마지막 단계.
   202605로 실증: 4슬라이드(표지/그리드/NEW강조리스트/유의사항), 23개 아이템 전부,
   NEW 배지 정상 표시. 이미지 없는 항목은 이름이 보이는 placeholder 박스로 처리
2. 에셋 저장소 스텁 제거 — 이미지 소스가 요청서 첨부뿐이라는 게 확정됨
3. 8단계: 파이프라인 전체 연결, 10개월 실사용 데이터로 회귀 실행. 9/10 정상, 겹침 0건.
   `ai_client.py` 견고성 문제 2개 발견/수정
4. 7단계: 위치 기반 이미지 매칭 구현
5. 6단계: AI 분류기 구현, 실제 API 키로 검증

## 다음 단계
9단계(신규 월 실사용 테스트) — 다음 달 실제 request.xlsx가 오면 그걸로 전체
파이프라인(`tools/pipeline.py` + `tools/render_pptx.py`)을 돌려서 실사용 검증.
그 전까지는 기존 10개 샘플로 회귀 테스트를 반복 실행하며 다듬는 정도가 남음.
