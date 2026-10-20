"""ONNX output decoding and the quality check, on synthetic inputs."""

import numpy as np

from pantry.detection.images import letterbox, open_image
from pantry.detection.onnx_detector import decode
from pantry.detection.quality import check_quality
from tests.images import jpeg

CLASSES = ["eggs", "milk"]


def output_with(boxes):
    """boxes: list of (cx, cy, w, h, class_index, score) in letterbox pixels."""
    out = np.zeros((1, 4 + len(CLASSES), 8), dtype=np.float32)
    for a, (cx, cy, w, h, c, s) in enumerate(boxes):
        out[0, :4, a] = (cx, cy, w, h)
        out[0, 4 + c, a] = s
    return out


def test_decode_maps_back_to_original_pixels():
    # 1280x960 photo letterboxed to 640: scale 0.5, vertical pad 80
    out = output_with([(100, 180, 40, 40, 0, 0.9)])
    [d] = decode(out, CLASSES, scale=0.5, pad=(0, 80), size=(1280, 960), min_score=0.1)
    assert d.key == "eggs" and d.box == (160.0, 160.0, 240.0, 240.0)


def test_decode_drops_low_scores_and_suppresses_overlaps_per_class():
    out = output_with(
        [
            (100, 100, 40, 40, 0, 0.9),
            (102, 100, 40, 40, 0, 0.8),  # overlaps the first egg: suppressed
            (102, 100, 40, 40, 1, 0.7),  # same place, other class: kept
            (300, 300, 40, 40, 0, 0.05),  # below min score
        ]
    )
    found = decode(out, CLASSES, 1.0, (0, 0), (640, 640), min_score=0.1)
    assert [(d.key, round(d.score, 2)) for d in found] == [("eggs", 0.9), ("milk", 0.7)]


def test_letterbox_keeps_aspect_and_centers():
    pixels, scale, pad = letterbox(open_image(jpeg(1, size=(1280, 960))), 640)
    assert pixels.shape == (640, 640, 3) and scale == 0.5 and pad == (0, 80)


def test_quality_flags_dark_and_blurry_and_passes_noise():
    assert check_quality(open_image(jpeg(dark=True)), 40, 60).reason == "dark"
    assert check_quality(open_image(jpeg(flat=True)), 40, 60).reason == "blurry"
    assert check_quality(open_image(jpeg(3)), 40, 60).ok


def test_agnostic_nms_keeps_one_label_per_object():
    out = output_with(
        [
            (100, 100, 40, 40, 0, 0.9),
            (102, 100, 40, 40, 1, 0.7),  # same object, other label: dropped
            (300, 300, 40, 40, 1, 0.6),  # separate object: kept
        ]
    )
    found = decode(out, CLASSES, 1.0, (0, 0), (640, 640), min_score=0.1, agnostic_iou=0.5)
    assert [(d.key, round(d.score, 1)) for d in found] == [("eggs", 0.9), ("milk", 0.6)]
