"""Print the Label Studio labelling config with every item key: python scripts/label_config.py > config.xml"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pantry.domain.items import load_item_types  # noqa: E402


def config_xml(keys: list[str]) -> str:
    labels = "\n".join(f'    <Label value="{k}"/>' for k in keys)
    return (
        "<View>\n"
        '  <Image name="image" value="$image" zoom="true"/>\n'
        '  <RectangleLabels name="label" toName="image">\n'
        f"{labels}\n"
        "  </RectangleLabels>\n"
        "</View>"
    )


if __name__ == "__main__":
    print(config_xml([i.key for i in load_item_types(ROOT / "config/items.yaml")]))
