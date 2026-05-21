"""
Hever store checker — lightweight version (no Playwright, no login required).
Covers the חבר שלי - רשתות section (347 stores) via plain HTTP.

Note: Credit card discount section (כרטיס אשראי חבר) requires the full
      hever_check.py with Playwright login.

Usage:
    python hever_lite.py <store name>
    python hever_lite.py          # interactive prompt
"""

import sys
import io
import json
import difflib
import urllib.request
import urllib.parse
import ssl

# Force UTF-8 on Windows
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MCCCARD_URL = "https://www.mcc.co.il/bs2/datasets/mcccard.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.mcc.co.il/",
}


def fetch_stores() -> list[dict]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(MCCCARD_URL, headers=HEADERS)
    with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def similarity(query: str, title: str) -> float:
    q, t = query.lower().strip(), title.lower().strip()
    if q in t:
        return 1.0
    return difflib.SequenceMatcher(None, q, t).ratio()


def search(store_name: str, stores: list[dict]) -> tuple[list[dict], list[dict]]:
    query = store_name.lower().strip()
    exact, fuzzy = [], []

    for item in stores:
        searchable = " ".join([
            item.get("company", ""),
            item.get("company_desc", ""),
            item.get("search_words", ""),
        ]).lower()

        score = similarity(store_name, item.get("company", ""))

        if query in searchable:
            exact.append({**item, "score": score})
        elif score >= 0.5:
            fuzzy.append({**item, "score": score})

    exact.sort(key=lambda x: x["score"], reverse=True)
    fuzzy.sort(key=lambda x: x["score"], reverse=True)
    return exact, fuzzy


def print_result(store_name: str, exact: list[dict], fuzzy: list[dict]):
    print("\n" + "=" * 58)
    print(f"Store query : {store_name}")
    print("Source      : חבר שלי - רשתות (lightweight, no login)")

    if not exact and not fuzzy:
        print("Hever card  : NO  (not found in חבר שלי directory)")
        print("\nNote: credit card discounts not checked — use hever_check.py")
        print("=" * 58)
        return

    if exact:
        item = exact[0]
        limitations = item.get("limitations", "").replace("<br/>", "\n  ").strip()
        print(f"Hever card  : YES  (חבר שלי)")
        print(f"\n[חבר שלי - רשתות]")
        print(f"  Match    : {item.get('company', '').strip()}")
        print(f"  Category : {item.get('company_category', '').strip()}")
        if item.get("website"):
            print(f"  Website  : {item['website']}")
        if item.get("branch_qty"):
            print(f"  Branches : {item['branch_qty']}")
        if item.get("is_online") == "Y":
            print("  Online   : Yes")
        if limitations:
            print(f"  Terms    :\n  {limitations[:400]}")
        if len(exact) > 1:
            print(f"\nOther matches:")
            for m in exact[1:4]:
                print(f"  • {m.get('company', '').strip()}")
    else:
        print("Hever card  : NO  (not found in חבר שלי directory)")
        print("\nDid you mean one of these?")
        for m in fuzzy[:5]:
            pct = int(m["score"] * 100)
            print(f"  • {m.get('company', '').strip()}  ({pct}% match)")

    print("\nNote: credit card discounts not checked — use hever_check.py for full results")
    print("=" * 58)


def main():
    if len(sys.argv) > 1:
        store_name = " ".join(sys.argv[1:])
    else:
        store_name = input("Enter store name (Hebrew or English): ").strip()

    if not store_name:
        print("No store name provided.")
        sys.exit(1)

    print(f"Fetching Hever store list...")
    stores = fetch_stores()
    print(f"Searching {len(stores)} stores for: {store_name!r}")

    exact, fuzzy = search(store_name, stores)
    print_result(store_name, exact, fuzzy)


if __name__ == "__main__":
    main()
