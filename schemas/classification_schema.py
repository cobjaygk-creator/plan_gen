"""JSON schema (pydantic) for the AI classification step. One request.xlsx
"특별 보상" raw text block can contain multiple sub-sections (e.g. 202605 has
both "기간제 패키지" and "배틀패스 의상 교환권") — each gets classified
independently into one of the 5 confirmed block types.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field

BlockType = Literal["grid", "text_list", "new_highlight", "few_preview", "paired_columns", "icon_only"]


class Item(BaseModel):
    name: str = Field(description="아이템/세트 이름, 원문 그대로 (괄호 안 '(new)' 등 마커는 is_new로 분리)")
    is_new: bool = Field(default=False, description="이름에 (new)/(new!) 마커가 붙어 있었는지")
    pair_group: Optional[int] = Field(
        default=None,
        description=(
            "paired_columns 블록에서만 사용. 이 항목이 두 세트 중 어느 쪽 하위 구성품인지 "
            "(0=첫 번째 세트, 1=두 번째 세트). 세트 자체의 이름(예: '자켓 세트', '치마 세트')인 "
            "항목은 null로 둔다 — 그게 pair_items가 된다. 다른 블록타입에서는 항상 null."
        ),
    )


class Section(BaseModel):
    section_title: str = Field(description="이 구간의 제목 원문, 예: '기간제 패키지', '배틀패스 의상 교환권'")
    block_type: BlockType
    items: list[Item]
    footnote: Optional[str] = Field(
        default=None, description="'아래 패션 세트 중 택 1' 같은 안내 문구, 없으면 null"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="이 section 분류에 대한 확신도 (0~1)")


class ClassificationOutput(BaseModel):
    sections: list[Section]
