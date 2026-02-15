import json
import os
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

OUTPUT = Path(__file__).resolve().parent / "orchestrator_trace.json"


def query(sql: str) -> list[dict]:
    resp = httpx.post("https://api.lmnr.ai/v1/sql/query", timeout=30,
        headers={"Authorization": f"Bearer {os.environ['LMNR_PROJECT_API_KEY']}"},
        json={"query": sql})
    resp.raise_for_status()
    return resp.json()["data"]


# Find the most recent orchestrator trace
traces = query("""
    SELECT id, top_span_name, status, duration,
           total_cost, input_tokens, output_tokens,
           start_time, end_time
    FROM traces
    WHERE top_span_name = 'orchestrator'
      AND start_time > now() - INTERVAL 7 DAY
    ORDER BY start_time DESC
    LIMIT 1
""")

if not traces:
    print("No orchestrator trace found in the last 7 days")
    exit(1)

t = traces[0]
trace_id = t["id"]
print(f"Orchestrator trace: {trace_id}")
print(f"  duration: {t['duration']}s, tokens: in={t['input_tokens']} out={t['output_tokens']}, cost: ${t['total_cost']}")
print(f"  time: {t['start_time']} -> {t['end_time']}")

# Get all spans for this trace
spans = query(f"""
    SELECT span_id, name, span_type, status, duration,
           input_tokens, output_tokens, total_cost,
           request_model, provider, path,
           parent_span_id, input, output, attributes,
           start_time, end_time
    FROM spans
    WHERE trace_id = '{trace_id}'
      AND start_time > now() - INTERVAL 7 DAY
    ORDER BY start_time ASC
""")

print(f"Found {len(spans)} spans")
for s in spans:
    prefix = "  " if s["parent_span_id"] == "00000000-0000-0000-0000-000000000000" else "    "
    dur = f"{s['duration']:.2f}s"
    model = f" ({s['request_model']})" if s["request_model"] else ""
    print(f"{prefix}[{s['span_type']}] {s['name']}{model} {dur}")

OUTPUT.write_text(json.dumps({"trace_id": trace_id, "trace": t, "spans": spans}, indent=2))
print(f"\nSaved {len(spans)} spans to {OUTPUT}")
