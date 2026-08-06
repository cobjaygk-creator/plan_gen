# plan_gen 현재 상태

## 요약
설계서(v2) 1~6단계 완료. API 키 검증 및 실사용 테스트까지 끝남.
7단계(위치 기반 이미지 매칭)부터 이어가면 됨.

- 마스터 템플릿: `templates/master_template.md` (기준: 202605)
- 블록타입 분류(10개월): `templates/block_type_classification.md`
- 블록 엔진(5개 함수, A/E 통합): `tools/blocks/`
- 회귀 채점기: `tools/regression.py`
- 고정 필드 파서: `tools/parse_fixed_fields.py`
- 특별보상 원문 추출(셀+드로잉 텍스트박스+이미지유무): `tools/extract_special_reward.py`
- AI 분류기(Haiku→Sonnet 에스컬레이션): `tools/classify_month.py`, `tools/ai_client.py`
- 테스트: `tests/` — 51개 전체 통과 (`.venv/Scripts/python.exe -m pytest tests/`)

## 최근 5건
1. 6단계: AI 분류기 구현, 실제 API 키로 검증. 202605는 사람 분류와 정확히 일치, 202602(버그 파일)는
   Sonnet까지 올라가고도 낮은 확신도로 NeedsHumanReview 정상 발생. 202508 grid/text_list 오분류
   발견 후 "[이미지있음]" 마커 추가로 수정 (0.72→0.92 신뢰도 상승)
2. 5단계: 고정 필드 파서 완료, 10개월 전수 검증 통과 (등급표 내용 자체가 10개월 동일함 확인)
3. 4단계: 회귀 채점기(text/image match rate, overlap count) 구현
4. 3단계: 블록 엔진 5종 구현 — A/E는 사용자 결정으로 grid_block() 하나로 통합
5. 2단계: 10개월 샘플 블록타입 분류 (슬라이드 6이 고정 장식이었다는 1단계 오판정 정정)

## 다음 단계
7단계: 위치 기반 이미지 매칭 (요청서 내 행/열 오프셋으로 이미지-아이템명 매칭,
실패분만 예외적으로 AI 비전). 이미지 존재 여부 감지 로직은 6단계에서 이미 일부
구현됨(`extract_drawing_picture_rows`) — 7단계는 "어느 이미지가 어느 항목인지"
매칭까지 완성하는 단계.
