"""Compressed few-shot examples for the classifier prompt — per design doc
principle 2 (token budget), these are name-lists-only, no images, 1-2 per
confirmed block type. Pulled from templates/block_type_classification.md's
확정(confirmed) rows only; text_list has no confirmed real sample yet
(none of the 10 months landed on plain B), so that one example is
synthetic and labeled as such rather than presented as real data.
"""

FEW_SHOT_EXAMPLES = """\
줄 끝의 "[이미지있음]"은 원본 엑셀에 실제 그림이 삽입돼 있다는 표시다 (추측 아님).
이게 있으면 grid/few_preview/new_highlight/paired_columns 중 하나, 없으면 text_list다.

예시 1 (grid — 202605 "기간제 패키지"):
입력:
B17: 기간제 패키지
BCD19: [이벤트] 고대의 서 30일 상자 | [이벤트] 세레스의 가호 습득서 | 그림자 스킨(30일) 교환권 [이미지있음]
BCD20: 길드의 가호 습득서(기간제) | [이벤트] 피크닉 타이틀 습득서 (30일) | 헌터의 힘 스킬 습득서 (30일) [이미지있음]
출력: {"section_title": "기간제 패키지", "block_type": "grid", "items": [
  {"name": "[이벤트] 고대의 서 30일 상자", "is_new": false},
  {"name": "[이벤트] 세레스의 가호 습득서", "is_new": false},
  {"name": "그림자 스킨(30일) 교환권", "is_new": false},
  {"name": "길드의 가호 습득서(기간제)", "is_new": false},
  {"name": "[이벤트] 피크닉 타이틀 습득서 (30일)", "is_new": false},
  {"name": "헌터의 힘 스킬 습득서 (30일)", "is_new": false}
], "footnote": null, "confidence": 0.95}

예시 2 (new_highlight — 202605 "배틀패스 의상 교환권", 목록 길어서 일부 생략):
입력:
B21: 배틀패스 의상 교환권
C22: (교환 리스트 중 택1)
BCD23: 노네임 의상 세트 | 붉은 거인 의상 세트 | 블랙 하이틴 캐쥬얼 세트 I
...(중략, 다른 항목들)...
BCD29: 산뜻한 로망 세트 | 버니버니 의상 세트 I | 발레코어 소프트 의상 세트 I (new) [이미지있음]
CD30: 버니버니 의상 세트 II | 발레코어 소프트 의상 세트 II (new) [이미지있음]
출력: {"section_title": "배틀패스 의상 교환권", "block_type": "new_highlight", "items": [
  {"name": "노네임 의상 세트", "is_new": false},
  ...(중략)...,
  {"name": "발레코어 소프트 의상 세트 I", "is_new": true},
  {"name": "발레코어 소프트 의상 세트 II", "is_new": true}
], "footnote": "(교환 리스트 중 택1)", "confidence": 0.9}
(판단 근거: "(new)" 마커가 붙은 항목이 1~2개 있고 나머지는 평범한 이름 목록 → new_highlight)

예시 3 (paired_columns — 202509 "할로윈 뱀파이어 의상 선택권"):
입력:
B17: 할로윈 뱀파이어 의상 선택권
C19: 아래 패션 세트 중 택 1 (거래 불가)
CD28: 할로윈 뱀파이어 슈트 세트 ll | 할로윈 뱀파이어 원피스 세트 ll [이미지있음]
출력: {"section_title": "할로윈 뱀파이어 의상 선택권", "block_type": "paired_columns", "items": [
  {"name": "할로윈 뱀파이어 슈트 세트 ll", "is_new": false},
  {"name": "할로윈 뱀파이어 원피스 세트 ll", "is_new": false}
], "footnote": "아래 패션 세트 중 택 1 (거래 불가)", "confidence": 0.92}
(판단 근거: 정확히 2개 세트 비교 + "···중 택 1" 각주 → paired_columns)

예시 4 (few_preview — 202509 "할로윈 펌킨 버킷 등록권"):
입력:
CD50: 할로윈 펌킨 버킷 등록권 | 할로윈 잭 오 랜턴 등록권 [이미지있음]
출력: {"section_title": "할로윈 펌킨 버킷 등록권", "block_type": "few_preview", "items": [
  {"name": "할로윈 펌킨 버킷 등록권", "is_new": false},
  {"name": "할로윈 잭 오 랜턴 등록권", "is_new": false}
], "footnote": null, "confidence": 0.8}
(판단 근거: 항목 1~3개, 큰 이미지 프리뷰 성격 → few_preview)

예시 5 (text_list — 합성 예시, 확정된 실제 샘플 없음. 개념 설명용):
입력:
B10: 이번 시즌 코스튬 목록
BCD11: 코스튬 A | 코스튬 B | 코스튬 C
BCD12: 코스튬 D | 코스튬 E | 코스튬 F
출력: {"section_title": "이번 시즌 코스튬 목록", "block_type": "text_list", "items": [
  {"name": "코스튬 A", "is_new": false}, {"name": "코스튬 B", "is_new": false}, {"name": "코스튬 C", "is_new": false},
  {"name": "코스튬 D", "is_new": false}, {"name": "코스튬 E", "is_new": false}, {"name": "코스튬 F", "is_new": false}
], "footnote": null, "confidence": 0.6}
(이미지 없이 이름만 3열로 나열되고, NEW 마커도 없고, 세트 비교 구조도 아닐 때만 이 타입 사용)
"""
