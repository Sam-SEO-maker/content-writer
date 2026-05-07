"""
Backfill GSC metrics (impressions, clicks, indexed) for all Notion Publications entries.

Usage:
    python -m scripts.notion.backfill_gsc_metrics [--skip-indexation]
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path

import requests

# Force unbuffered output
print = partial(print, flush=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
DATA_SOURCE_ID = "36cf1b15-1385-46fd-86d0-f379cf6d2a71"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"

GOOGLE_SA_PATH = Path(
    os.environ.get("GOOGLE_SA_PATH", "~/.credentials/google/google-service-account.json")
).expanduser()

# Domain -> GSC property mapping
DOMAIN_TO_GSC = {
    "enseigna.fr": "https://enseigna.fr/",
    "superprof.fr": "https://www.superprof.fr/ressources/",
}


def notion_headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Step 1: Fetch all Notion entries
# ---------------------------------------------------------------------------

def fetch_all_notion_entries():
    """Fetch all pages from the Publications data source with pagination."""
    all_entries = []
    cursor = None

    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor

        resp = requests.post(
            f"{NOTION_API}/data_sources/{DATA_SOURCE_ID}/query",
            headers=notion_headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        all_entries.extend(results)
        print(f"  Fetched {len(all_entries)} entries so far...")

        if not data.get("has_more", False):
            break
        cursor = data.get("next_cursor")

    return all_entries


def parse_notion_entry(page):
    """Extract page_id, url, title, date from a Notion page."""
    props = page.get("properties", {})
    url_prop = props.get("URL", {})
    url = url_prop.get("url", "") or ""

    title_prop = props.get("Sujet", {})
    title_parts = title_prop.get("title", [])
    title = "".join(t.get("plain_text", "") for t in title_parts)

    date_prop = props.get("Date", {})
    date_obj = date_prop.get("date")
    pub_date = date_obj.get("start", "") if date_obj else ""

    indexed_prop = props.get("Indexed", {})
    indexed_sel = indexed_prop.get("select")
    existing_indexed = indexed_sel.get("name", "") if indexed_sel else ""

    return {
        "page_id": page.get("id", ""),
        "url": url,
        "title": title,
        "pub_date": pub_date,
        "existing_indexed": existing_indexed,
    }


def extract_domain(url):
    """Extract domain from URL."""
    if not url:
        return ""
    url = url.replace("https://", "").replace("http://", "")
    url = url.replace("www.", "")
    return url.split("/")[0]


# ---------------------------------------------------------------------------
# Step 2: Bulk GSC performance (per domain)
# ---------------------------------------------------------------------------

def init_gsc_service():
    """Initialize GSC API service."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            str(GOOGLE_SA_PATH),
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        return build("searchconsole", "v1", credentials=credentials)
    except Exception as e:
        print(f"[ERROR] Cannot init GSC API: {e}")
        return None


def _fetch_gsc_performance(gsc_service, gsc_property, start_date_str, end_date_str):
    """
    Low-level GSC performance query.
    Returns dict: url -> {clicks, impressions}
    """
    body = {
        "startDate": start_date_str,
        "endDate": end_date_str,
        "dimensions": ["page"],
        "rowLimit": 25000,
    }

    try:
        response = (
            gsc_service.searchanalytics()
            .query(siteUrl=gsc_property, body=body)
            .execute()
        )
    except Exception as e:
        print(f"  [ERROR] GSC query for {gsc_property}: {e}")
        return {}

    result = {}
    for row in response.get("rows", []):
        page_url = row["keys"][0]
        result[page_url] = {
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
        }

    return result


def fetch_bulk_performance(gsc_service, gsc_property, earliest_date=None):
    """
    Fetch performance data for ALL pages of a GSC property.
    Uses earliest_date as start (capped at 16 months, GSC max retention).
    Returns dict: url -> {clicks, impressions}
    """
    end_date = datetime.now() - timedelta(days=2)  # GSC data has 2-day lag
    max_start = end_date - timedelta(days=480)  # ~16 months GSC retention

    if earliest_date:
        try:
            start_date = datetime.strptime(earliest_date, "%Y-%m-%d")
            start_date = max(start_date, max_start)  # Cap at GSC retention
        except ValueError:
            start_date = max_start
    else:
        start_date = max_start

    return _fetch_gsc_performance(
        gsc_service, gsc_property,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )


def fetch_30d_performance(gsc_service, gsc_property):
    """
    Fetch performance data for the last 30 days.
    Returns dict: url -> {clicks, impressions}
    """
    end_date = datetime.now() - timedelta(days=2)  # GSC data has 2-day lag
    start_date = end_date - timedelta(days=30)

    print(f"    30d window: {start_date.strftime('%Y-%m-%d')} -> {end_date.strftime('%Y-%m-%d')}")

    return _fetch_gsc_performance(
        gsc_service, gsc_property,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )


# ---------------------------------------------------------------------------
# Step 3: URL Inspection (indexation)
# ---------------------------------------------------------------------------

def check_indexation(gsc_service, url, gsc_property, retries=3):
    """Check if a URL is indexed via URL Inspection API."""
    for attempt in range(retries):
        try:
            result = (
                gsc_service.urlInspection()
                .index()
                .inspect(
                    body={
                        "inspectionUrl": url,
                        "siteUrl": gsc_property,
                    }
                )
                .execute()
            )
            verdict = (
                result.get("inspectionResult", {})
                .get("indexStatusResult", {})
                .get("verdict", "UNKNOWN")
            )
            return "YES" if verdict == "PASS" else "NO"
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rateLimitExceeded" in error_str:
                print(f"    [RATE LIMIT] Waiting 10s...")
                time.sleep(10)
                continue
            if attempt < retries - 1:
                print(f"    [RETRY {attempt+1}] {url[:50]}: {e}")
                time.sleep(5)
                # Reinit GSC service on connection errors
                if "10054" in error_str or "ConnectionReset" in error_str:
                    try:
                        gsc_service._http.close()
                    except Exception:
                        pass
                continue
            print(f"    [ERROR] Inspection {url[:60]}: {e}")
            return ""
    return ""


# ---------------------------------------------------------------------------
# Step 4: Update Notion entry
# ---------------------------------------------------------------------------

def update_notion_entry(page_id, impressions, clicks, indexed,
                        impressions_30d=None, clicks_30d=None):
    """Update a Notion page with GSC metrics."""
    properties = {}
    if impressions is not None:
        properties["Impressions"] = {"number": impressions}
    if clicks is not None:
        properties["Clics"] = {"number": clicks}
    if indexed:
        properties["Indexed"] = {"select": {"name": indexed}}
    if impressions_30d is not None:
        properties["Impressions 30 days"] = {
            "rich_text": [{"text": {"content": str(impressions_30d)}}]
        }
    if clicks_30d is not None:
        properties["Clics 30 days"] = {
            "rich_text": [{"text": {"content": str(clicks_30d)}}]
        }

    if not properties:
        return

    resp = requests.patch(
        f"{NOTION_API}/pages/{page_id}",
        headers=notion_headers(),
        json={"properties": properties},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"    [ERROR] Update {page_id}: {resp.status_code} {resp.text[:200]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    skip_indexation = "--skip-indexation" in sys.argv
    resume_mode = "--resume" in sys.argv

    # Load .env
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
        global NOTION_TOKEN
        NOTION_TOKEN = os.environ.get("NOTION_TOKEN", NOTION_TOKEN)

    if not NOTION_TOKEN:
        print("[ERROR] NOTION_TOKEN not set")
        sys.exit(1)

    # Step 1: Fetch all Notion entries
    print("=" * 60)
    print("STEP 1: Fetching all Notion entries...")
    print("=" * 60)
    entries = fetch_all_notion_entries()
    parsed = [parse_notion_entry(e) for e in entries]
    parsed = [e for e in parsed if e["url"]]  # filter entries without URL
    print(f"Total entries with URL: {len(parsed)}")

    # Group by domain
    by_domain = {}
    for entry in parsed:
        domain = extract_domain(entry["url"])
        by_domain.setdefault(domain, []).append(entry)

    print("\nEntries per domain:")
    for domain, entries_list in sorted(by_domain.items()):
        print(f"  {domain}: {len(entries_list)}")

    # Step 2: Init GSC
    print("\n" + "=" * 60)
    print("STEP 2: Fetching GSC performance (bulk per domain)...")
    print("=" * 60)
    gsc_service = init_gsc_service()
    if not gsc_service:
        print("[ERROR] GSC service not available. Exiting.")
        sys.exit(1)

    # Bulk performance per domain (from earliest publication date + last 30 days)
    perf_data = {}  # url -> {clicks, impressions}
    perf_30d = {}   # url -> {clicks, impressions}
    for domain, gsc_prop in DOMAIN_TO_GSC.items():
        if domain not in by_domain:
            continue
        count = len(by_domain[domain])

        # Find earliest publication date for this domain
        dates = [e["pub_date"] for e in by_domain[domain] if e.get("pub_date")]
        earliest = min(dates) if dates else None

        print(f"\n  Querying GSC for {domain} ({count} entries, since {earliest or 'max'})...")
        domain_perf = fetch_bulk_performance(gsc_service, gsc_prop, earliest_date=earliest)
        perf_data.update(domain_perf)
        print(f"    -> {len(domain_perf)} URLs with data (cumul)")

        # 30-day window
        domain_30d = fetch_30d_performance(gsc_service, gsc_prop)
        perf_30d.update(domain_30d)
        print(f"    -> {len(domain_30d)} URLs with data (30j)")

    # Match performance to entries
    def _match_url(data_dict, url):
        """Try exact match, then with/without trailing slash."""
        perf = data_dict.get(url)
        if not perf and url.endswith("/"):
            perf = data_dict.get(url.rstrip("/"))
        if not perf and not url.endswith("/"):
            perf = data_dict.get(url + "/")
        return perf

    matched = 0
    matched_30d = 0
    for entry in parsed:
        url = entry["url"]
        # Cumulative (since pub date)
        perf = _match_url(perf_data, url)
        if perf:
            entry["clicks"] = perf["clicks"]
            entry["impressions"] = perf["impressions"]
            matched += 1
        else:
            entry["clicks"] = 0
            entry["impressions"] = 0

        # Last 30 days
        perf_recent = _match_url(perf_30d, url)
        if perf_recent:
            entry["clicks_30d"] = perf_recent["clicks"]
            entry["impressions_30d"] = perf_recent["impressions"]
            matched_30d += 1
        else:
            entry["clicks_30d"] = 0
            entry["impressions_30d"] = 0

    print(f"\nPerformance matched: {matched}/{len(parsed)} (cumul), {matched_30d}/{len(parsed)} (30j)")

    # Step 3: Indexation (optional)
    if skip_indexation:
        print("\n[SKIP] Indexation check skipped (--skip-indexation)")
        for entry in parsed:
            entry["indexed"] = ""
    else:
        # In resume mode, skip entries that already have Indexed value
        to_inspect = parsed
        if resume_mode:
            to_inspect = [e for e in parsed if not e.get("existing_indexed")]
            skipped = len(parsed) - len(to_inspect)
            print(f"\n[RESUME] Skipping {skipped} entries already indexed")

        print("\n" + "=" * 60)
        print("STEP 3: Checking indexation (URL Inspection API)...")
        print(f"  {len(to_inspect)} URLs to inspect (~2s each = ~{len(to_inspect)*2//60} min)")
        print("=" * 60)

        for i, entry in enumerate(to_inspect):
            domain = extract_domain(entry["url"])
            gsc_prop = DOMAIN_TO_GSC.get(domain, "")
            if not gsc_prop:
                entry["indexed"] = ""
                continue

            entry["indexed"] = check_indexation(gsc_service, entry["url"], gsc_prop)

            if (i + 1) % 50 == 0:
                yes_count = sum(1 for e in to_inspect[:i+1] if e.get("indexed") == "YES")
                print(f"  [{i+1}/{len(to_inspect)}] indexed={yes_count} YES so far")

            time.sleep(2)  # Rate limit protection

        # Preserve existing indexed values for resumed entries
        if resume_mode:
            for entry in parsed:
                if entry.get("existing_indexed") and not entry.get("indexed"):
                    entry["indexed"] = entry["existing_indexed"]

    # Step 4: Update Notion
    print("\n" + "=" * 60)
    print("STEP 4: Updating Notion entries...")
    print("=" * 60)
    updated = 0
    errors = 0
    for i, entry in enumerate(parsed):
        try:
            update_notion_entry(
                entry["page_id"],
                entry.get("impressions"),
                entry.get("clicks"),
                entry.get("indexed"),
                impressions_30d=entry.get("impressions_30d"),
                clicks_30d=entry.get("clicks_30d"),
            )
            updated += 1
        except Exception as e:
            print(f"  [ERROR] {entry['url'][:50]}: {e}")
            errors += 1

        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(parsed)}] updated={updated}, errors={errors}")

        # Notion rate limit: ~3 requests/sec
        time.sleep(0.35)

    # Summary
    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
    yes_count = sum(1 for e in parsed if e.get("indexed") == "YES")
    no_count = sum(1 for e in parsed if e.get("indexed") == "NO")
    total_clicks = sum(e.get("clicks", 0) for e in parsed)
    total_impressions = sum(e.get("impressions", 0) for e in parsed)
    total_clicks_30d = sum(e.get("clicks_30d", 0) for e in parsed)
    total_impressions_30d = sum(e.get("impressions_30d", 0) for e in parsed)
    print(f"  Entries processed: {len(parsed)}")
    print(f"  Notion updated: {updated} (errors: {errors})")
    print(f"  Total impressions (cumul): {total_impressions:,}")
    print(f"  Total clicks (cumul): {total_clicks:,}")
    print(f"  Total impressions (30j): {total_impressions_30d:,}")
    print(f"  Total clicks (30j): {total_clicks_30d:,}")
    if not skip_indexation:
        print(f"  Indexed: {yes_count} YES, {no_count} NO, {len(parsed)-yes_count-no_count} unknown")


if __name__ == "__main__":
    main()
