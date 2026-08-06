"""Detect overlapping shapes on each slide of a pptx file.

Used both to pick a bug-free master template sample (step 1) and later
as one of the regression scoring signals (step 4).
"""
from pptx import Presentation
from pptx.util import Emu


def shape_boxes(slide):
    boxes = []
    for shape in slide.shapes:
        if shape.left is None or shape.top is None:
            continue
        if shape.width is None or shape.height is None:
            continue
        boxes.append((shape.shape_id, shape.name, shape.left, shape.top,
                      shape.left + shape.width, shape.top + shape.height))
    return boxes


def overlap_area(a, b):
    _, _, ax0, ay0, ax1, ay1 = a
    _, _, bx0, by0, bx1, by1 = b
    ox = max(0, min(ax1, bx1) - max(ax0, bx0))
    oy = max(0, min(ay1, by1) - max(ay0, by0))
    return ox * oy


def find_overlaps(path, min_area_emu=914400 * 914400 // 400):
    """min_area_emu default threshold ~ a few square points, filters noise."""
    prs = Presentation(path)
    report = []
    for idx, slide in enumerate(prs.slides, start=1):
        boxes = shape_boxes(slide)
        pairs = []
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                area = overlap_area(boxes[i], boxes[j])
                if area > min_area_emu:
                    pairs.append((boxes[i][1], boxes[j][1], area))
        if pairs:
            report.append((idx, pairs))
    return report


if __name__ == "__main__":
    import sys
    for name in sys.argv[1:]:
        path = f"samples/{name}_result.pptx"
        report = find_overlaps(path)
        if not report:
            print(f"{name}: OK (no significant overlaps)")
        else:
            print(f"{name}: {len(report)} slide(s) with overlaps")
            for slide_no, pairs in report:
                for a, b, area in pairs:
                    pt2 = area / (914400 ** 2 / 100)
                    print(f"  slide {slide_no}: '{a}' x '{b}' overlap~{pt2:.1f}pt2")
