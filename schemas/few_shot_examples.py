"""Compressed few-shot examples for the classifier prompt — per design doc
principle 2 (token budget), these are name-lists-only, no images, 1-2 per
confirmed block type. Pulled from templates/block_type_classification.md's
확정(confirmed) rows only; text_list has no confirmed real sample yet
(none of the 10 months landed on plain B), so that one example is
synthetic and labeled as such rather than presented as real data.

Example 2 (new_highlight) was rewritten from real 202512 data after the
original 202605-based example led the model to misattribute a standalone
"NEW!"/"이미지 추후 전달 예정" marker row to the wrong (preceding) item —
the correct rule is that a standalone marker row refers to the NEXT
same-column item, and the resulting layout is just a grid with a badge,
not a separate oversized card (see tools/blocks/grid.py).
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

예시 2 (new_highlight/grid — 202512 "배틀패스 FX 타이틀 교환권", 독립 줄 NEW 마커 예시):
입력:
D33: 배틀패스 FX 타이틀 교환권 [이미지있음]
C35: 아래 FX 타이틀 중 택 1 (거래 불가)
EDC41: RETRO FX 타이틀 습득서 (영구제) | 수묵화 FX 타이틀 습득서(영구제) | 아에루라 FX 타이틀 습득서(영구제) [이미지있음]
EDC46: LEFICA 타이틀 습득서 (영구제) | DEVIL FX 타이틀 습득서 (영구제) | 멍멍 멍멍멍 FX 타이틀 습득서(영구제)
D49: NEW!
D50: 이미지 추후 전달 예정
CD52: 서핑 푸리링 타이틀 습득서(영구제) | 따끈따근 프리링 타이틀 습득서(영구제)
출력: {"section_title": "배틀패스 FX 타이틀 교환권", "block_type": "grid", "items": [
  {"name": "RETRO FX 타이틀 습득서 (영구제)", "is_new": false},
  {"name": "수묵화 FX 타이틀 습득서(영구제)", "is_new": false},
  {"name": "아에루라 FX 타이틀 습득서(영구제)", "is_new": false},
  {"name": "LEFICA 타이틀 습득서 (영구제)", "is_new": false},
  {"name": "DEVIL FX 타이틀 습득서 (영구제)", "is_new": false},
  {"name": "멍멍 멍멍멍 FX 타이틀 습득서(영구제)", "is_new": false},
  {"name": "서핑 푸리링 타이틀 습득서(영구제)", "is_new": false},
  {"name": "따끈따근 프리링 타이틀 습득서(영구제)", "is_new": true}
], "footnote": "아래 FX 타이틀 중 택 1 (거래 불가)", "confidence": 0.85}
(판단 근거: "NEW!"/"이미지 추후 전달 예정"이 D49/D50에 독립된 줄로 있고, 그 다음(D52)에
나온 "따끈따근 프리링 타이틀 습득서"가 D열의 다음 항목이므로 그게 신규 항목이다 —
D46의 "멍멍 멍멍멍"(그 앞 항목)이 아니다. 8개 항목이 전부 같은 그리드 칸에 들어가고
신규 항목만 배지가 붙으므로 block_type은 grid — new_highlight로 표기해도 렌더링은
동일하게 처리된다.)

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

예시 3b (paired_columns + pair_group — 202606 "배틀패스 신규 의상", 세트별 하위 목록 + 의도적 중복 행):
입력:
B17: 배틀패스 신규 의상
C18: 20th 파티 자켓 세트 / 20th 파티 치마 세트
BD20: 20th 파티 연미복 | 20th 파티 흰꽃 머리띠 [이미지있음]
BD21: 20th 파티 크라바트 자켓 | 20th 파티 오프숄더 블라우스 [이미지있음]
BD22: 20th 파티 줄무늬 바지 | 20th 파티 미니 드레스 [이미지있음]
BD23: 20th 파티 옥스퍼드 화 | 20th 파티 리본 힐 [이미지있음]
BD24: 20th 파티 흰 보석 장갑 | 20th 파티 초롱 눈빛 [이미지있음]
BD25: 20th 파티 분홍 장미꽃 | 20th 파티 초롱 눈빛 [이미지있음]
B26: 20th 파티 분홍 장미꽃 [이미지있음]
B28: * 자켓 세트는 연미복(한벌옷)과 자켓/바지(상하의)로 나뉘어져 있으며 3종이 전부 지급됩니다.
* 분홍 장미꽃과 초롱 눈빛은 착용 파츠가 다른 2종이 지급됩니다. (얼굴장식/안경)
출력: {"section_title": "배틀패스 신규 의상", "block_type": "paired_columns", "items": [
  {"name": "20th 파티 자켓 세트", "is_new": false, "pair_group": null},
  {"name": "20th 파티 치마 세트", "is_new": false, "pair_group": null},
  {"name": "20th 파티 연미복", "is_new": false, "pair_group": 0},
  {"name": "20th 파티 흰꽃 머리띠", "is_new": false, "pair_group": 1},
  {"name": "20th 파티 크라바트 자켓", "is_new": false, "pair_group": 0},
  {"name": "20th 파티 오프숄더 블라우스", "is_new": false, "pair_group": 1},
  {"name": "20th 파티 줄무늬 바지", "is_new": false, "pair_group": 0},
  {"name": "20th 파티 미니 드레스", "is_new": false, "pair_group": 1},
  {"name": "20th 파티 옥스퍼드 화", "is_new": false, "pair_group": 0},
  {"name": "20th 파티 리본 힐", "is_new": false, "pair_group": 1},
  {"name": "20th 파티 흰 보석 장갑", "is_new": false, "pair_group": 0},
  {"name": "20th 파티 초롱 눈빛", "is_new": false, "pair_group": 1},
  {"name": "20th 파티 분홍 장미꽃", "is_new": false, "pair_group": 0},
  {"name": "20th 파티 초롱 눈빛", "is_new": false, "pair_group": 1},
  {"name": "20th 파티 분홍 장미꽃", "is_new": false, "pair_group": 0}
], "footnote": "* 자켓 세트는 연미복(한벌옷)과 자켓/바지(상하의)로 나뉘어져 있으며 3종이 전부 지급됩니다.\n* 분홍 장미꽃과 초롱 눈빛은 착용 파츠가 다른 2종이 지급됩니다. (얼굴장식/안경)", "confidence": 0.85}
(판단 근거: C18에 "자켓 세트 / 치마 세트"로 두 세트가 나란히 병기되고, 그 아래 B열/D열에
각 세트의 하위 구성품이 여러 행에 걸쳐 나열됨 — "택 1" 각주가 없어도 paired_columns다.
세트 이름 2개는 pair_group=null(= pair_items), B열 하위 구성품은 pair_group=0, D열은
pair_group=1. **"20th 파티 분홍 장미꽃"이 BD25와 B26 두 행에, "20th 파티 초롱 눈빛"이
BD24와 BD25 두 행에 각각 나온다 — 이름이 같다고 하나로 합치면 안 된다. 각주가
"착용 파츠가 다른 2종이 지급됩니다"라고 명시하므로 원문 행 개수 그대로 각각 별도
항목으로 넣어야 한다 (자켓 세트 하위 7개, 치마 세트 하위 6개, 총 15개).** 이걸 flat
grid로 뽑거나 중복을 하나로 합치면 안 된다 — 세트별 목록과 실제 수량 구조를 잃는다.)

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
