"""A normal HTTP client process. It imports no lab code and controls its own retries."""

import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

mode = sys.argv[1] if len(sys.argv) > 1 else "fixed"
run_id = os.environ["HRL_RUN_ID"]
opener = build_opener(ProxyHandler({}))
request_timeout = float(os.environ.get("HRL_EXAMPLE_TIMEOUT_S", "3"))
for intent in ("order-a", "order-b"):
    for attempt in range(3):
        key = f"{run_id}:{intent}"
        if mode == "broken":
            key = uuid4().hex
        if mode == "over-dedup":
            key = run_id
        request = Request(
            os.environ["HRL_PROXY_URL"] + "/orders",
            data=json.dumps({"run_id": run_id, "sku": "book", "units": 1}).encode(),
            headers={"Content-Type": "application/json", "Idempotency-Key": key},
        )
        try:
            with opener.open(request, timeout=request_timeout) as response:
                json.load(response)
            break
        except HTTPError as exc:
            if exc.code not in (429, 503):
                raise SystemExit(1)
        except TimeoutError:
            continue
    else:
        raise SystemExit(1)
