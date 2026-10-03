"""Score models on tests/cases.json:

    python scripts/evaluate.py qwen2.5:3b llama3.2:3b gemma3:4b

Prints per-case PASS/FAIL, a per-category breakdown, and a Markdown table you can paste
straight into your write-up. Use the failures too: they are the honest part of the story.
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from promise_keeper import config  # noqa: E402
from promise_keeper.extractor import extract_promises  # noqa: E402

CASES = json.loads((Path(__file__).resolve().parent.parent / "tests" / "cases.json").read_text())


def run(model: str) -> dict:
    print(f"\n=== {model} ===")
    by_cat = defaultdict(lambda: [0, 0])      # category -> [passed, total]
    ok_count = ok_deadline = answered = 0
    total_time = 0.0
    for case in CASES:
        cat = case.get("category", "core")
        by_cat[cat][1] += 1
        start = time.time()
        try:
            found = extract_promises(case["message"], chat_partner=case["partner"], model=model)
        except Exception as exc:
            print(f"ERROR  {case['message']!r}: {exc}")
            continue
        total_time += time.time() - start
        answered += 1
        count_ok = len(found) == case["count"]
        deadline_ok = (not case["count"]) or (any(p["deadline"] for p in found) == case["has_deadline"])
        ok_count += count_ok
        ok_deadline += deadline_ok
        passed = count_ok and deadline_ok
        by_cat[cat][0] += passed
        print(f"{'PASS' if passed else 'FAIL'}  [{cat}] {case['message']!r}")
        if not passed:
            print(f"      expected {case['count']} promise(s), got: "
                  f"{[(p['commitment'], p['deadline_text']) for p in found]}")
    n = len(CASES)
    avg = total_time / answered if answered else float("nan")
    print(f"-> right number of promises: {ok_count}/{n} | deadlines: {ok_deadline}/{n} | avg {avg:.1f}s per message")
    print("   " + " | ".join(f"{c}: {p}/{t}" for c, (p, t) in by_cat.items()))
    return {"model": model, "count": ok_count, "deadline": ok_deadline, "n": n, "avg": avg,
            "cats": dict(by_cat)}


def markdown_table(results: list[dict]) -> str:
    cats = sorted({c for r in results for c in r["cats"]})
    head = "| Model | Right # of promises | Deadlines | " + " | ".join(cats) + " | Avg s/msg |"
    sep = "|" + "---|" * (4 + len(cats))
    rows = [f"| `{r['model']}` | {r['count']}/{r['n']} | {r['deadline']}/{r['n']} | "
            + " | ".join(f"{r['cats'].get(c, [0, 0])[0]}/{r['cats'].get(c, [0, 0])[1]}" for c in cats)
            + f" | {r['avg']:.1f} |" for r in results]
    return "\n".join([head, sep, *rows])


if __name__ == "__main__":
    results = [run(m) for m in (sys.argv[1:] or [config.MODEL])]
    print("\nPaste into your post:\n")
    print(markdown_table(results))
