# plan_gen 현재 상태

## 요약
설계서(v2) 1~5단계 완료. API 키 없이 진행 가능한 부분은 전부 끝남.
6단계(AI 분류)부터는 실제 API 비용 발생 — 착수 전 사용자 확인 필요.

- 마스터 템플릿: `templates/master_template.md` (기준: 202605)
- 블록타입 분류(10개월): `templates/block_type_classification.md`
- 블록 엔진(5개 함수, A/E 통합): `tools/blocks/`
- 회귀 채점기: `tools/regression.py`
- 고정 필드 파서: `tools/parse_fixed_fields.py`
- 테스트: `tests/` — 40개 전체 통과 (`.venv/Scripts/python.exe -m pytest tests/`)

## 최근 5건
1. 5단계: 고정 필드 파서 완료, 10개월 전수 검증 통과 (등급표 내용 자체가 10개월 동일함 확인)
2. 4단계: 회귀 채점기(text/image match rate, overlap count) 구현
3. 3단계: 블록 엔진 5종 구현 — A/E는 사용자 결정으로 grid_block() 하나로 통합
4. 2단계: 10개월 샘플 블록타입 분류 (슬라이드 6이 고정 장식이었다는 1단계 오판정 정정)
5. 1단계: 202605 기준 마스터 템플릿 추출, "최종 산출물은 이미지 분리 후 전달" 발견

## 다음 단계 (사용자 확인 대기)
6단계: Haiku→Sonnet 에스컬레이션 AI 분류기 구현 — Anthropic API 키 필요.
