"""Condense master_template_raw.json into a short, readable design-token
summary (colors / fonts / top-level shape boxes) for the block-relevant
slides, so later steps never need to re-open the raw pptx dump.
"""
import json

EMU_PER_PT = 12700


def flatten(shapes, depth=0):
    for s in shapes:
        yield depth, s
        for child in flatten(s.get("children", []), depth + 1):
            yield child


def summarize(raw, target_slides):
    colors = {}
    fonts = {}
    slide_summaries = []

    for slide in raw["slides"]:
        if slide["slide_no"] not in target_slides:
            continue
        boxes = []
        for depth, shape in flatten(slide["shapes"]):
            if shape.get("fill_rgb"):
                colors[shape["fill_rgb"]] = colors.get(shape["fill_rgb"], 0) + 1
            for fnt in shape.get("fonts", []):
                key = (fnt.get("name"), fnt.get("size_pt"), fnt.get("bold"), fnt.get("color"))
                fonts[key] = fonts.get(key, 0) + 1
            if depth == 0:
                boxes.append({
                    "name": shape["name"],
                    "left_pt": round(shape["left_emu"] / EMU_PER_PT, 1) if shape["left_emu"] is not None else None,
                    "top_pt": round(shape["top_emu"] / EMU_PER_PT, 1) if shape["top_emu"] is not None else None,
                    "width_pt": round(shape["width_emu"] / EMU_PER_PT, 1) if shape["width_emu"] is not None else None,
                    "height_pt": round(shape["height_emu"] / EMU_PER_PT, 1) if shape["height_emu"] is not None else None,
                    "has_table": "table" in shape,
                })
        slide_summaries.append({"slide_no": slide["slide_no"], "top_level_shapes": boxes})

    color_list = sorted(colors.items(), key=lambda kv: -kv[1])
    font_list = sorted(fonts.items(), key=lambda kv: -kv[1])

    return {
        "slide_width_pt": round(raw["slide_width_emu"] / EMU_PER_PT, 1),
        "slide_height_pt": round(raw["slide_height_emu"] / EMU_PER_PT, 1),
        "colors": [{"rgb": c, "count": n} for c, n in color_list],
        "fonts": [
            {"name": k[0], "size_pt": k[1], "bold": k[2], "color": k[3], "count": n}
            for k, n in font_list
        ],
        "slides": slide_summaries,
    }


if __name__ == "__main__":
    with open("templates/master_template_raw.json", encoding="utf-8") as f:
        raw = json.load(f)
    # slides 6-9: the block-relevant "공지형" pages (화면구성안). 1-5/10 are
    # cover/revision/overview/concept/section-divider/ending boilerplate.
    summary = summarize(raw, target_slides={6, 7, 8, 9})
    with open("templates/master_template_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("wrote templates/master_template_summary.json")
    print(f"colors: {len(summary['colors'])}, fonts: {len(summary['fonts'])}")
