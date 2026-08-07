# plan_gen 현재 상태

## 요약
설계서(v2) 1~8단계 + .pptx 렌더러 + 실사용 버그 수정 라운드 완료.
request.xlsx → 진짜 스타일 적용된 .pptx까지 전체 파이프라인 동작, `run.py`로
한 줄 실행 가능. 202512 실사용 검증에서 실제 버그 2건 발견/수정함.

- 마스터 템플릿(색상/폰트/헤더바/카드 실제 값 포함): `templates/master_template.md`
- 블록타입 분류(10개월): `templates/block_type_classification.md`
- 블록 엔진(4개 함수 — grid/text_list/few_preview/paired_columns, new_highlight는 grid로 통합됨): `tools/blocks/`
- 회귀 채점기: `tools/regression.py` + 202512 정식 회귀 케이스: `tests/test_regression_202512.py`
- 고정 필드 파서: `tools/parse_fixed_fields.py`
- 특별보상 원문 추출(셀+드로잉 텍스트박스+이미지유무): `tools/extract_special_reward.py`
- AI 분류기(Haiku→Sonnet 에스컬레이션, 같은 등급 내 재시도 포함): `tools/classify_month.py`, `tools/ai_client.py`
- 아이템 위치 역매칭 + 이미지 매칭(최적 이분 매칭): `tools/locate_items.py`, `tools/extract_images.py`, `tools/match_images.py`
- 전체 파이프라인 연결: `tools/pipeline.py`
- .pptx 렌더러(실제 스타일 적용): `tools/render_pptx.py`
- **실행 진입점**: `run.py` — `python run.py samples/xxx_request.xlsx` 한 줄로 끝까지 실행
- 테스트: `tests/` — 74개 전체 통과

## 202512 실사용 검증에서 발견/수정한 버그 (사용자 스크린샷 비교로 발견)
1. **new_highlight 블록 렌더링 방식이 잘못됨**: NEW 항목을 거대한 별도 카드로 빼고
   나머지는 이미지 없는 텍스트 목록으로 처리하도록 설계했었는데, 실제로는 NEW
   항목도 다른 항목과 같은 그리드 칸에 들어가고 배지만 붙는 구조였음 (202605
   샘플 하나만 보고 일반화한 게 틀림). → new_highlight를 grid_block에 통합,
   badge + "이미지 추후 전달 예정" placeholder로 표현
2. **NEW 마커가 독립된 행으로 있을 때 엉뚱한 항목에 귀속됨**: "NEW!"가 이름 옆이
   아니라 별도 줄로 있으면 그 다음(아래) 같은 열의 항목을 가리키는 건데 AI가
   이전 항목에 붙임 → 프롬프트에 귀속 규칙 명시, few-shot 예시 교체
3. **이미지 매칭이 탐욕적(greedy)이라 최적이 아닌 경우 놓침**: 항목 3개가
   이미지 2개를 두고 경쟁할 때 먼저 처리된 항목이 최적이 아닌 선택을 해서
   실제로는 매칭 가능한 다른 항목이 못 받는 문제 → 최적 이분 매칭(Kuhn's
   algorithm)으로 교체, 202512에서 6/8 → 7/8로 확인
4. (부수적) Sonnet이 가끔 스키마를 이중 중첩된 형태로 반환하는 문제 발견 →
   같은 모델 등급 내 재시도(최대 2회) 추가

## 결정된 사항
- 이미지 소스는 요청서 첨부 이미지 하나뿐, 별도 에셋 저장소 없음 — 확인 완료
- 이미지 화질: 원본 그대로, 카드 크기에 맞춰 리사이즈만
- 렌더러 스타일: 실제 슬라이드 XML에서 역산한 값 적용 (카드 흰배경+연회색
  테두리, 헤더바 진회색+흰글씨, 캡션 262626, NEW는 배지 도형 아니고 빨간
  회전 텍스트) — `master_template.md`에 표로 기록됨
- Claude Sonnet 5는 `temperature` 파라미터 미지원 (deprecated, 400 에러) —
  API 응답 편차는 같은 등급 재시도로 흡수

## 최근 5건
1. 이미지 매칭 최적화(Kuhn's algorithm) + 202512 정식 회귀 테스트 추가
2. new_highlight→grid 통합, NEW 마커 귀속 규칙 프롬프트 추가, 같은 등급 재시도 로직
3. 렌더러에 마스터 템플릿 실제 스타일(색상/폰트/헤더바/카드) 적용
4. run.py 실행 진입점 추가 (UTF-8 콘솔 출력 강제)
5. .pptx 렌더러 최초 구현

## 다음 단계
설계서 9단계(신규 월 실사용 테스트)는 실제 다음 달 request.xlsx가 와야
의미 있게 검증됨. 그 전까지는 사용자 피드백 기반으로 실사용 버그를
찾아 고치는 이번 라운드 같은 작업이 이어질 것으로 예상.
