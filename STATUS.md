# plan_gen 현재 상태

## 요약
설계서(v2) 1~7단계 완료 (7단계는 확인 대기 항목 있음 — 아래 참고).
8단계(전체 파이프라인 연결)로 넘어갈 준비 됨, 단 이미지 커버리지는 제한적.

- 마스터 템플릿: `templates/master_template.md` (기준: 202605)
- 블록타입 분류(10개월): `templates/block_type_classification.md`
- 블록 엔진(5개 함수, A/E 통합): `tools/blocks/`
- 회귀 채점기: `tools/regression.py`
- 고정 필드 파서: `tools/parse_fixed_fields.py`
- 특별보상 원문 추출(셀+드로잉 텍스트박스+이미지유무): `tools/extract_special_reward.py`
- AI 분류기(Haiku→Sonnet 에스컬레이션): `tools/classify_month.py`, `tools/ai_client.py`
- 아이템 위치 역매칭 + 이미지 매칭: `tools/locate_items.py`, `tools/extract_images.py`, `tools/match_images.py`
- 외부 에셋 저장소 조회 인터페이스(스텁, 미구현): `tools/asset_repository.py`
- 테스트: `tests/` — 63개 전체 통과 (`.venv/Scripts/python.exe -m pytest tests/`)

## ⚠️ 확인 필요 (설계서 9장 #1과 동일 사안, 이제 실증됨)
202605 샘플로 종단 테스트한 결과 **위치 기반 매칭만으로는 대부분의 항목에 이미지를
못 채운다.** 202605는 요청서에 이미지가 2장뿐인데 항목은 29개 — 그 2장도 아이템명이
있는 B/C/D열이 아니라 E열(29~38행 근처)에 따로 있어서 이 항목들과 무관함.
샘플 10개월 중 8개월이 이미지 2~6장 vs 항목 20~30개 수준 (202502/202508/202512만
이미지가 많음, 13~25장).

→ **아이템 이름/ID로 조회 가능한 이미지 에셋 저장소가 실제로 있는지 팀에 확인 필요.**
사용자 지시에 따라 "저장소 없다"고 가정하고 구조부터 잡음: `match_images()`가
위치매칭 → `asset_repository.lookup_image_by_name()` 순서로 시도하고, 후자는
지금 항상 `None`을 반환하는 스텁. 저장소 존재가 확인되면 `asset_repository.py`
안의 조회 로직만 채우면 되고, 다른 코드는 손댈 필요 없음. 그 전까지 이미지 없는
항목은 정상적으로 "text_only"로 남음 (에러 아님).

## 최근 5건
1. 7단계: 위치 기반 이미지 매칭 구현. 202605 종단 테스트에서 매칭률 0% 확인 →
   에셋 저장소 미확인 문제 실증. 사용자 지시로 저장소 없다고 가정하고 인터페이스
   스텁(`asset_repository.py`)만 비워두는 구조로 마무리
2. 6단계: AI 분류기 구현, 실제 API 키로 검증. 202605는 사람 분류와 정확히 일치, 202602(버그 파일)는
   Sonnet까지 올라가고도 낮은 확신도로 NeedsHumanReview 정상 발생. 202508 grid/text_list 오분류
   발견 후 "[이미지있음]" 마커 추가로 수정 (0.72→0.92 신뢰도 상승)
3. 5단계: 고정 필드 파서 완료, 10개월 전수 검증 통과 (등급표 내용 자체가 10개월 동일함 확인)
4. 4단계: 회귀 채점기(text/image match rate, overlap count) 구현
5. 3단계: 블록 엔진 5종 구현 — A/E는 사용자 결정으로 grid_block() 하나로 통합

## 다음 단계
8단계: 전체 파이프라인 연결 + 1년치 회귀 실행. 이미지 매칭률이 낮게 나올 수 있는데,
이건 파이프라인 버그가 아니라 위 "확인 필요" 항목이 미해결이라 그런 것 — 회귀
채점 결과 해석할 때 감안할 것.
