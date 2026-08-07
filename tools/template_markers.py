"""Detect and remove marker shapes in template.pptx.

Every marker is a plain rectangle: no fill, dashed line, and a solid
line color of either FF0000 (red = text substitution zone) or 00B0F0
(blue = reward content zone). No text inside — confirmed by inspecting
the raw XML of samples/template.pptx directly.

Detection reads shape._element (raw XML) rather than python-pptx's
high-level shape.line.color accessor on purpose: line/fill accessors on
shapes that don't already have an explicit <a:ln> can, in some pptx
states, cause python-pptx to materialize a new empty <a:ln> element as a
side effect of merely reading the property. Every non-marker shape in
the template would get walked by whatever loop finds the markers, so an
accessor with a write side effect risks leaving stray empty borders on
shapes nobody meant to touch. Reading raw XML has no such side effect.
"""
import re
from dataclasses import dataclass
from pptx.oxml.ns import qn

EMU_PER_PT = 12700
RED = "FF0000"
BLUE = "00B0F0"


@dataclass
class Marker:
    shape: object  # python-pptx shape, for removal via shape._element
    color: str     # "red" | "blue"
    left: float    # pt
    top: float
    width: float
    height: float


def _marker_color(shape) -> str | None:
    ln = shape._element.find(qn("p:spPr") + "/" + qn("a:ln"))
    if ln is None:
        return None
    dash = ln.find(qn("a:prstDash"))
    if dash is None or dash.get("val") != "dash":
        return None
    srgb = ln.find(".//" + qn("a:srgbClr"))
    if srgb is None:
        return None
    val = (srgb.get("val") or "").upper()
    if val == RED:
        return "red"
    if val == BLUE:
        return "blue"
    return None


def find_markers(slide) -> list[Marker]:
    markers = []
    for shape in slide.shapes:
        color = _marker_color(shape)
        if color is None:
            continue
        if shape.left is None:
            continue
        markers.append(Marker(
            shape=shape, color=color,
            left=shape.left / EMU_PER_PT, top=shape.top / EMU_PER_PT,
            width=shape.width / EMU_PER_PT, height=shape.height / EMU_PER_PT,
        ))
    return markers


def remove_marker(marker: Marker) -> None:
    """Deletes the marker shape's XML element entirely — it was never
    meant to appear in the output, only to mark where content goes."""
    el = marker.shape._element
    el.getparent().remove(el)
