"""Pure parts of the owner-run dataset scripts."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from export_dataset import label_studio_task  # noqa: E402
from label_config import config_xml  # noqa: E402


def test_task_boxes_are_percent_of_image():
    task = label_studio_task("a.jpg", 1000, 500, [{"key": "eggs", "box": [100, 50, 300, 150], "score": 0.4}])
    value = task["predictions"][0]["result"][0]["value"]
    assert value == {"x": 10.0, "y": 10.0, "width": 20.0, "height": 20.0, "rectanglelabels": ["eggs"]}
    assert task["data"]["image"].endswith("images/a.jpg")


def test_label_config_lists_every_key():
    xml = config_xml(["eggs", "milk"])
    assert '<Label value="eggs"/>' in xml and '<Label value="milk"/>' in xml
    assert 'RectangleLabels name="label" toName="image"' in xml
