import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.wireframe.edits import PatchError, validate_patch

PATH = "body>div:nth-child(1)"


def video(src):
    return validate_patch({"op": "insert", "path": PATH, "kind": "video", "src": src})


@pytest.mark.parametrize(
    "src",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://vimeo.com/123456",
        "https://cdn.example.com/a/clip.mp4",
        "https://cdn.example.com/clip.webm?token=abc",
    ],
)
def test_supported_video_sources_are_accepted(src):
    assert video(src)["src"] == src


@pytest.mark.parametrize(
    "src",
    [
        "http://cdn.example.com/clip.mp4",
        "javascript:alert(1)",
        "https://example.com/page.html",
        'https://example.com/clip.mp4"onloadstart="alert(1)',
        "https://evil.com/watch?v=dQw4w9WgXcQ",
        "",
        None,
    ],
)
def test_other_video_sources_are_rejected(src):
    with pytest.raises(PatchError):
        video(src)
