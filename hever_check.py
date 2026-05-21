"""
Check if a store supports the חבר green card (כרטיס ירוק) on mcc.co.il.

Usage:
    python hever_check.py <store_name>
    python hever_check.py           # interactive prompt

For deal details (discount %), optionally set your Hever credentials:
    set HEVER_ID=<your_id_number>
    set HEVER_PASS=<your_password>
"""

import sys
import asyncio
import re
import io
import json
import os
import urllib.parse
import difflib

from playwright.async_api import async_playwright

# Force UTF-8 output on Windows
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_URL = "https://www.mcc.co.il"
SEARCH_API = BASE_URL + "/site/search"   # ?I=104&ac=1&N=20&word=<query>
CLUB_ID = 104                            # Hever club ID
MCCCARD_JSON = BASE_URL + "/bs2/datasets/mcccard.json"  # חבר שלי - רשתות dataset

# Load .env from the same folder as this script
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

HEVER_ID = os.environ.get("HEVER_ID", "")
HEVER_PASS = os.environ.get("HEVER_PASS", "")


async def login(page) -> bool:
    """Attempt Hever login. Returns True on success."""
    if not HEVER_ID or not HEVER_PASS:
        return False
    try:
        await page.goto(BASE_URL + "/signin.aspx", wait_until="networkidle", timeout=20000)
        await page.locator("input[name*='id'], input[type='text']").first.fill(HEVER_ID)
        await page.locator("input[type='password']").first.fill(HEVER_PASS)
        await page.locator("button:visible").first.click()
        await page.wait_for_load_state("networkidle", timeout=15000)
        # Check if we ended up on a non-login page
        logged_in = "signin" not in page.url
        if logged_in:
            print("  Logged in to Hever successfully.")
        return logged_in
    except Exception as e:
        print(f"  Login failed: {e}")
        return False


async def search_stores(store_name: str, page) -> list[dict]:
    """Call the search API and return a list of {id, title} matches."""
    encoded = urllib.parse.quote(store_name)
    url = f"{SEARCH_API}?I={CLUB_ID}&ac=1&N=20&word={encoded}"

    await page.goto(url, wait_until="networkidle", timeout=15000)
    raw = await page.content()

    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not json_match:
        return []
    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return []

    results = []
    for item in data.get("benefits_package_list", []):
        results.append({
            "id": item.get("id"),
            "title": item.get("title", "").strip(),
        })
    return results


async def search_mcccard(store_name: str, page) -> list[dict]:
    """Search the חבר שלי - רשתות dataset (mcccard.json) for a store name."""
    resp = await page.request.get(MCCCARD_JSON)
    if resp.status != 200:
        return []
    try:
        data = json.loads(await resp.text())
    except json.JSONDecodeError:
        return []

    query = store_name.lower().strip()
    results = []
    for item in data:
        searchable = " ".join([
            item.get("company", ""),
            item.get("company_desc", ""),
            item.get("search_words", ""),
        ]).lower()
        score = _similarity(store_name, item.get("company", ""))
        if query in searchable or score >= 0.5:
            results.append({
                "id": item.get("sn"),
                "title": item.get("company", "").strip(),
                "category": item.get("company_category", "").strip(),
                "website": item.get("website", ""),
                "limitations": item.get("limitations", "").replace("<br/>", "\n  "),
                "is_online": item.get("is_online") == "Y",
                "branches": item.get("branch_qty", ""),
                "internal_link": item.get("internal_link", ""),
                "score": score,
                "source": "shely",
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


async def get_store_details(store_id: int, page) -> dict:
    """Load the store detail page and extract discount/deal info. Requires login."""
    url = f"{BASE_URL}/st_reshet.aspx?p1={store_id}"
    await page.goto(url, wait_until="networkidle", timeout=20000)
    await page.wait_for_timeout(1500)

    # If redirected to sign-in, details unavailable without login
    if "signin" in page.url:
        return {"url": url, "discounts": [], "detail_text": "", "requires_login": True}

    body = await page.locator("body").inner_text()
    discounts = re.findall(r"(\d+(?:\.\d+)?)\s*%", body)

    # Grab meaningful deal description text
    detail_text = ""
    for sel in [
        ".benefit-text", ".deal-desc", ".benefits-desc",
        ".reshet-detail", ".card-body", "p", "div.text",
    ]:
        els = await page.locator(sel).all()
        for el in els:
            if await el.is_visible():
                t = (await el.inner_text()).strip()
                if len(t) > 30:
                    detail_text = t[:500]
                    break
        if detail_text:
            break

    return {"url": url, "discounts": list(set(discounts)), "detail_text": detail_text,
            "requires_login": False}


def _similarity(query: str, title: str) -> float:
    """Return a 0–1 similarity score between query and store title."""
    q = query.lower().strip()
    t = title.lower().strip()
    # Exact substring match scores highest
    if q in t:
        return 1.0
    return difflib.SequenceMatcher(None, q, t).ratio()


async def fuzzy_search(store_name: str, page) -> list[dict]:
    """
    Try progressively shorter prefix queries to find similar store names.
    Returns matches scored by similarity, sorted best-first.
    """
    seen_ids: set = set()
    candidates: list[dict] = []

    queries = [store_name]
    # Add prefix variants: first 5, 4, 3 chars (avoids empty queries)
    for length in (5, 4, 3):
        if len(store_name) > length:
            queries.append(store_name[:length])

    for q in queries:
        for item in await search_stores(q, page):
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                score = _similarity(store_name, item["title"])
                candidates.append({**item, "score": score})

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


async def check_store(store_name: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        await page.goto(BASE_URL + "/st_reshet_public.aspx",
                        wait_until="networkidle", timeout=20000)

        logged_in = await login(page)

        print(f"Searching: {store_name!r}")

        # Search both sources in parallel
        matches, shely_matches = await asyncio.gather(
            search_stores(store_name, page),
            search_mcccard(store_name, page),
        )

        # ── Credit card section (st_reshet) ─────────────────────────────────
        query_lower = store_name.lower()
        exact = [m for m in matches if query_lower in m["title"].lower()]

        card_result = None
        if exact:
            top = exact[0]
            print(f"  -> Credit card match: {top['title']}")
            details = await get_store_details(top["id"], page)
            card_result = {
                "top_match": top["title"],
                "store_url": details["url"],
                "discounts": details["discounts"],
                "detail_text": details["detail_text"],
                "requires_login": details["requires_login"],
                "other_matches": exact[1:5],
            }

        # ── חבר שלי section (mcccard.json) ─────────────────────────────────
        shely_exact = [m for m in shely_matches if query_lower in m["title"].lower()]
        shely_result = shely_exact[0] if shely_exact else None
        if shely_result:
            print(f"  -> חבר שלי match: {shely_result['title']}")

        found = bool(card_result or shely_result)

        if found:
            await browser.close()
            return {
                "found": True,
                "store": store_name,
                "card_result": card_result,
                "shely_result": shely_result,
                "logged_in": logged_in,
            }

        # ── Nothing exact — try fuzzy across both sources ────────────────────
        print(f"  No exact match. Trying fuzzy search...")
        fuzzy_card = await fuzzy_search(store_name, page)
        fuzzy_card = [m for m in fuzzy_card if m["score"] >= 0.35]
        fuzzy_shely = [m for m in shely_matches if m["score"] >= 0.35]

        await browser.close()
        return {
            "found": False,
            "store": store_name,
            "fuzzy_matches": (fuzzy_card + fuzzy_shely)[:6],
        }


def print_result(result: dict):
    print("\n" + "=" * 58)
    print(f"Store query : {result['store']}")

    if not result["found"]:
        print("Hever card  : NO  (not found in Hever directory)")
        fuzzy = result.get("fuzzy_matches", [])
        if fuzzy:
            print("\nDid you mean one of these?")
            for m in fuzzy:
                pct = int(m["score"] * 100)
                print(f"  • {m['title']}  ({pct}% match)")
        print("=" * 58)
        return

    cr = result.get("card_result")
    sh = result.get("shely_result")
    cards = []
    if cr:
        cards.append("כרטיס אשראי חבר")
    if sh:
        cards.append("חבר שלי")
    print(f"Hever card  : YES  ({' + '.join(cards)})")

    # ── Credit card section ──────────────────────────────────────────────
    if cr:
        print(f"\n[כרטיס אשראי חבר - הנחה בחיוב]")
        print(f"  Match   : {cr['top_match']}")
        print(f"  Page    : {cr['store_url']}")
        if cr.get("requires_login") and not result.get("logged_in"):
            print("  Discount: (login required — set HEVER_ID and HEVER_PASS)")
        elif cr["discounts"]:
            print(f"  Discount: {', '.join(cr['discounts'])}%")
        else:
            print("  Discount: see store page")
        if cr.get("detail_text"):
            print(f"  Details : {cr['detail_text'][:200]}")

    # ── חבר שלי section ──────────────────────────────────────────────────
    if sh:
        print(f"\n[חבר שלי - רשתות]")
        print(f"  Match    : {sh['title']}")
        print(f"  Category : {sh['category']}")
        if sh["website"]:
            print(f"  Website  : {sh['website']}")
        if sh["branches"]:
            print(f"  Branches : {sh['branches']}")
        if sh["is_online"]:
            print("  Online   : Yes")
        if sh["limitations"]:
            print(f"  Terms    :\n  {sh['limitations'][:400]}")

    print("=" * 58)


async def main():
    if len(sys.argv) > 1:
        store_name = " ".join(sys.argv[1:])
    else:
        store_name = input("Enter store name (Hebrew or English): ").strip()

    if not store_name:
        print("No store name provided.")
        sys.exit(1)

    result = await check_store(store_name)
    print_result(result)


if __name__ == "__main__":
    asyncio.run(main())
