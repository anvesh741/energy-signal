"""Snapshot every API response the dashboard requests into JSON files:  python -m app.export_static OUT_DIR

Used by the GitHub Pages build, where there is no server. Each request path maps to one file
via static_name(); frontend/lib/api.ts applies the same mapping, so keep the two in sync.
"""

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.timeutil import utc_now

# keep in sync with RANGES in frontend/app/electricity/page.tsx
US48_DAYS = [7, 14, 30, 90]


def static_name(path: str) -> str:
    """/api/fuels/storage?region=x  ->  fuels/storage__region_x.json"""
    route, _, query = path.removeprefix("/api/").partition("?")
    if query:
        route += "__" + query.replace("&", "_").replace("=", "_")
    return route + ".json"


def request_paths(client: TestClient) -> list[str]:
    paths = [
        "/api/overview",
        "/api/fuels",
        "/api/electricity/global",
        "/api/forecasts/options",
        "/api/sources",
    ]
    paths += [f"/api/electricity/us48?days={d}" for d in US48_DAYS]
    storage = client.get("/api/fuels/storage").json()
    paths += [f"/api/fuels/storage?region={r['id']}" for r in storage["regions"]]
    for opt in client.get("/api/forecasts/options").json():
        q = f"series_id={opt['series_id']}&target_kind={opt['target_kind']}"
        paths.append(f"/api/forecasts?{q}")
        paths += [f"/api/forecasts/history?{q}&horizon={h}" for h in opt["steps"]]
    return paths


def export(out_dir: Path) -> int:
    client = TestClient(app)
    paths = request_paths(client)
    for path in paths:
        resp = client.get(path)
        resp.raise_for_status()
        target = out_dir / static_name(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(resp.text)
    (out_dir / "meta.json").write_text(json.dumps({"built_at": utc_now().isoformat()}))
    return len(paths)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "../frontend/public/data")
    print(f"exported {export(out)} responses to {out}")
