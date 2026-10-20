"""Create a portable native DSH patch for the deliberate observer regression."""

from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[1]
output = root / ".lab" / "observer.patch.yml"
output.parent.mkdir(exist_ok=True)
output.write_text(
    yaml.safe_dump(
        [
            {
                "insert": [
                    {
                        "id": "broken-observer",
                        "name": (root / "examples" / "broken-observer.mjs").as_uri(),
                    }
                ]
            }
        ]
    ),
    encoding="utf-8",
)
print(output)
