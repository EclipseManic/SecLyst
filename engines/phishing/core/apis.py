"""
External API integrations — VirusTotal and urlscan.io.
"""

import base64
import copy
from datetime import datetime, timezone
import logging
import threading
import time
import urllib.parse

import requests

try:
    from seclyst.integration.client import EngineControlClient
except ImportError:
    EngineControlClient = None

from .config import VT_AVAILABLE, API_KEY, URL_SCAN_API_KEY, URLSCAN_AVAILABLE, SETTINGS, FREE_MAIL_PROVIDERS
from .utils import timestamp_to_iso, unique_list

logger = logging.getLogger(__name__)
_provider_control = EngineControlClient("phishing") if EngineControlClient else None

# ── In-memory caches for fast enrichment ──────────────────────────
_VT_CACHE = {}
_VT_CACHE_LOCK = threading.Lock()

_URLSCAN_CACHE = {}
_URLSCAN_CACHE_LOCK = threading.Lock()

# Trusted/benign schema & web specification hosts (never malware, skip VT query)
BENIGN_DOMAINS_SKIP_VT = {
    "w3.org", "www.w3.org",
    "schemas.openxmlformats.org",
    "schemas.microsoft.com",
    "xml.apache.org",
    "schema.org", "www.schema.org",
    "docs.oasis-open.org",
    "purl.org",
    "iana.org", "www.iana.org",
    "example.com", "example.net", "example.org",
}


__all__ = [
    'vt_fetch', 'vt_url_id', 'summarize_vt_response', 'scan_domain', 'scan_ip', 'scan_url', 'scan_file_hash',
    'vt_detection_count', 'vt_summary_text', 'enrich_with_virustotal',
    'urlscan_submit', 'urlscan_search', 'urlscan_search_or_submit', 'urlscan_get_dom',
    'urlscan_get_har', 'urlscan_summary_text', 'urlscan_detection_flagged',
]



# ═══════════════════════════════════════════════════════════════════
# VIRUSTOTAL
# ═══════════════════════════════════════════════════════════════════

def vt_fetch(path):
    if _provider_control and _provider_control.enabled:
        broker = _provider_control.provider_request(
            "virustotal",
            "lookup",
            "path",
            path.lstrip("/"),
            options={"path": path.lstrip("/")},
        )
        if broker is not None:
            state = broker.get("state")
            if state == "success":
                return {
                    "status": "ok",
                    "http_status": broker.get("http_status") or 200,
                    "json": broker.get("data"),
                    "cached": bool(broker.get("cached")),
                }
            if state == "not_found":
                return {"status": "not_found", "http_status": 404, "cached": bool(broker.get("cached"))}
            if state == "waiting_rate_limit":
                return {
                    "status": "rate_limited",
                    "http_status": 429,
                    "retry_after": broker.get("retry_after"),
                    "reason": "VirusTotal request is waiting for shared quota",
                }
            if state == "no_credential":
                return {"status": "skipped", "reason": "VirusTotal credential is not configured"}
            return {"status": "error", "http_status": broker.get("http_status"), "reason": broker.get("error") or state}
    if not VT_AVAILABLE:
        return {"status": "skipped", "reason": "VT_API_KEY is not set"}

    headers = {"x-apikey": API_KEY, "accept": "application/json"}
    url = f"https://www.virustotal.com/api/v3/{path.lstrip('/')}"
    try:
        response = requests.get(url, headers=headers, timeout=SETTINGS["vt_request_timeout_seconds"])
        if response.status_code == 429:
            return {"status": "rate_limited", "http_status": 429, "reason": "VirusTotal API rate limit exceeded"}
        if response.status_code == 404:
            return {"status": "not_found", "http_status": 404}
        if response.status_code != 200:
            return {"status": "error", "http_status": response.status_code, "reason": response.text[:300]}
        return {"status": "ok", "http_status": 200, "json": response.json()}
    except requests.exceptions.RequestException as exc:
        return {"status": "error", "reason": f"Request error: {exc}"}


def vt_url_id(url):
    return base64.urlsafe_b64encode(url.encode()).decode().strip("=")


def summarize_vt_response(response, object_type):
    if response.get("status") != "ok":
        return response

    data = response.get("json", {}).get("data", {})
    attrs = data.get("attributes", {})
    stats = attrs.get("last_analysis_stats", {}) or {}
    results = attrs.get("last_analysis_results", {}) or {}
    engine_hits = []
    for engine, result in results.items():
        if result.get("category") in {"malicious", "suspicious"}:
            engine_hits.append({
                "engine": engine,
                "category": result.get("category"),
                "result": result.get("result"),
            })

    summary = {
        "status": "ok",
        "object_type": object_type,
        "id": data.get("id"),
        "last_analysis_stats": stats,
        "detections": int(stats.get("malicious", 0) or 0) + int(stats.get("suspicious", 0) or 0),
        "total_engines": sum(int(v or 0) for v in stats.values()),
        "reputation": attrs.get("reputation"),
        "tags": attrs.get("tags", [])[:20] if isinstance(attrs.get("tags"), list) else attrs.get("tags"),
        "categories": unique_list(list((attrs.get("categories") or {}).values()))[:20],
        "engine_hits": engine_hits[:30],
        "first_submission_date": timestamp_to_iso(attrs.get("first_submission_date")),
        "last_submission_date": timestamp_to_iso(attrs.get("last_submission_date")),
        "last_analysis_date": timestamp_to_iso(attrs.get("last_analysis_date")),
    }

    if object_type == "url":
        summary.update({
            "last_final_url": attrs.get("last_final_url"),
            "redirection_chain": attrs.get("redirection_chain", [])[:20],
            "last_http_response_code": attrs.get("last_http_response_code"),
            "title": attrs.get("title"),
            "targeted_brand": attrs.get("targeted_brand"),
            "outgoing_links": attrs.get("outgoing_links", [])[:20],
        })
    elif object_type == "domain":
        dns_records = attrs.get("last_dns_records", []) or []
        summary.update({
            "registrar": attrs.get("registrar"),
            "creation_date": timestamp_to_iso(attrs.get("creation_date")),
            "last_dns_records": [{"type": r.get("type"), "value": r.get("value")} for r in dns_records[:20]],
            "popularity_ranks": attrs.get("popularity_ranks", {}),
        })
    elif object_type == "ip":
        summary.update({
            "asn": attrs.get("asn"),
            "as_owner": attrs.get("as_owner"),
            "country": attrs.get("country"),
            "network": attrs.get("network"),
        })
    elif object_type == "file":
        threat = attrs.get("popular_threat_classification") or {}
        summary.update({
            "md5": attrs.get("md5"), "sha1": attrs.get("sha1"), "sha256": attrs.get("sha256"),
            "meaningful_name": attrs.get("meaningful_name"),
            "type_description": attrs.get("type_description"),
            "magic": attrs.get("magic"), "type_tag": attrs.get("type_tag"),
            "names": attrs.get("names", [])[:20],
            "popular_threat_classification": threat,
            "crowdsourced_yara_results": attrs.get("crowdsourced_yara_results", [])[:10],
        })
    return summary


def scan_domain(domain):
    norm = (domain or "").strip().lower()
    if not norm:
        return {"status": "skipped", "reason": "empty domain"}
    if norm in BENIGN_DOMAINS_SKIP_VT or norm.endswith((".w3.org", ".openxmlformats.org", ".iana.org")):
        return {"status": "skipped", "reason": "trusted internet standard/schema domain"}
    with _VT_CACHE_LOCK:
        cached = _VT_CACHE.get(("domain", norm))
        if cached is not None:
            res = copy.deepcopy(cached)
            res["_from_cache"] = True
            return res
    res = summarize_vt_response(vt_fetch(f"domains/{urllib.parse.quote(norm, safe='')}"), "domain")
    if res.get("status") in {"ok", "not_found"}:
        with _VT_CACHE_LOCK:
            if len(_VT_CACHE) > 500:
                _VT_CACHE.pop(next(iter(_VT_CACHE)))
            _VT_CACHE[("domain", norm)] = copy.deepcopy(res)
    return res


def scan_ip(ip_value):
    norm = (ip_value or "").strip()
    if not norm:
        return {"status": "skipped", "reason": "empty IP"}
    with _VT_CACHE_LOCK:
        cached = _VT_CACHE.get(("ip", norm))
        if cached is not None:
            res = copy.deepcopy(cached)
            res["_from_cache"] = True
            return res
    res = summarize_vt_response(vt_fetch(f"ip_addresses/{urllib.parse.quote(norm, safe='')}"), "ip")
    if res.get("status") in {"ok", "not_found"}:
        with _VT_CACHE_LOCK:
            if len(_VT_CACHE) > 500:
                _VT_CACHE.pop(next(iter(_VT_CACHE)))
            _VT_CACHE[("ip", norm)] = copy.deepcopy(res)
    return res


def scan_url(url):
    norm = (url or "").strip()
    if not norm:
        return {"status": "skipped", "reason": "empty URL"}
    try:
        parsed_h = urllib.parse.urlsplit(norm).hostname or ""
        if parsed_h.lower() in BENIGN_DOMAINS_SKIP_VT or parsed_h.lower().endswith((".w3.org", ".openxmlformats.org", ".iana.org")):
            return {"status": "skipped", "reason": "trusted internet standard/schema host"}
    except Exception:
        pass
    with _VT_CACHE_LOCK:
        cached = _VT_CACHE.get(("url", norm))
        if cached is not None:
            res = copy.deepcopy(cached)
            res["_from_cache"] = True
            return res
    res = summarize_vt_response(vt_fetch(f"urls/{vt_url_id(norm)}"), "url")
    if res.get("status") in {"ok", "not_found"}:
        with _VT_CACHE_LOCK:
            if len(_VT_CACHE) > 500:
                _VT_CACHE.pop(next(iter(_VT_CACHE)))
            _VT_CACHE[("url", norm)] = copy.deepcopy(res)
    return res


def scan_file_hash(file_hash):
    norm = (file_hash or "").strip().lower()
    if not norm:
        return {"status": "skipped", "reason": "empty hash"}
    with _VT_CACHE_LOCK:
        cached = _VT_CACHE.get(("file", norm))
        if cached is not None:
            res = copy.deepcopy(cached)
            res["_from_cache"] = True
            return res
    res = summarize_vt_response(vt_fetch(f"files/{norm}"), "file")
    if res.get("status") in {"ok", "not_found"}:
        with _VT_CACHE_LOCK:
            if len(_VT_CACHE) > 500:
                _VT_CACHE.pop(next(iter(_VT_CACHE)))
            _VT_CACHE[("file", norm)] = copy.deepcopy(res)
    return res


def vt_detection_count(vt_result):
    if not vt_result or vt_result.get("status") != "ok":
        return 0
    return int(vt_result.get("detections") or 0)


def vt_summary_text(vt_result):
    if not vt_result:
        return "not scanned"
    status = vt_result.get("status")
    if status == "ok":
        return f"{vt_result.get('detections', 0)} of {vt_result.get('total_engines', 0)} engines flagged"
    if status == "skipped":
        return f"skipped: {vt_result.get('reason')}"
    if status == "not_found":
        return "not found in VirusTotal"
    if status == "rate_limited":
        return "API rate limit exceeded"
    return f"{status}: {vt_result.get('reason') or vt_result.get('http_status')}"


def enrich_with_virustotal(observables, url_records, attachment_results, delay_seconds, max_items, no_vt):
    if no_vt or not VT_AVAILABLE:
        skipped = {
            "status": "skipped",
            "reason": "disabled by --no-vt" if no_vt else "VT_API_KEY is not set",
        }
        counts = {"domain_count": 0, "ip_count": 0, "url_count": 0, "file_count": 0}
        for observable in observables:
            if observable["type"] in {"domain", "ip", "url", "sha256"}:
                observable["vt"] = skipped
        for url_record in url_records:
            url_record["vt"] = skipped
        for attachment in attachment_results:
            attachment["vt"] = skipped
        return {"scanned": 0, "skipped_reason": skipped["reason"], **counts}

    scanned = 0
    counts = {"domain_count": 0, "ip_count": 0, "url_count": 0, "file_count": 0}
    max_items = max_items or SETTINGS.get("default_max_vt_items", 10)

    # 1. Attachment hashes (highest priority: attachments can be malware)
    sha_items = []
    for attachment in attachment_results:
        sha256 = (attachment.get("hashes") or {}).get("sha256")
        if sha256:
            sha_items.append((sha256, attachment))

    # 2. Actionable URLs sorted by risk priority
    def _calc_url_priority(rec):
        prio = 0
        if rec.get("deceptive_display"):
            prio += 5
        feats = rec.get("features") or []
        for f in feats:
            fl = f.lower()
            if "shortener" in fl or "punycode" in fl or "non-standard port" in fl or "ip literal" in fl:
                prio += 4
            elif "jwt" in fl or "brand" in fl or "redirect" in fl:
                prio += 3
        if not rec.get("is_tracking_pixel"):
            prio += 2
        return prio

    url_items = []
    for r in sorted(url_records, key=_calc_url_priority, reverse=True):
        u = r.get("normalized_url") or r.get("url")
        if u:
            h = (r.get("host") or "").lower()
            if h in BENIGN_DOMAINS_SKIP_VT or h.endswith((".w3.org", ".openxmlformats.org", ".iana.org")):
                r["vt"] = {"status": "skipped", "reason": "trusted internet standard/schema host"}
                continue
            url_items.append((u, r))

    # 3. Domains (prioritize sender domain & Reply-To, filter out free providers)
    domain_items = []
    free_set = {p.lower() for p in FREE_MAIL_PROVIDERS}
    domain_obs = [obs for obs in observables if obs.get("type") == "domain"]

    def _domain_priority(obs):
        roles = obs.get("roles") or []
        if "from_domain" in roles or "sender_domain" in roles:
            return 3
        if "reply_to_domain" in roles:
            return 2
        return 1

    for obs in sorted(domain_obs, key=_domain_priority, reverse=True):
        d = (obs.get("value") or "").lower()
        if not d:
            continue
        if d in free_set:
            obs["vt"] = {"status": "skipped", "reason": "Free email provider domain"}
            continue
        if d in BENIGN_DOMAINS_SKIP_VT or d.endswith((".w3.org", ".openxmlformats.org", ".iana.org")):
            obs["vt"] = {"status": "skipped", "reason": "trusted internet standard/schema domain"}
            continue
        domain_items.append((d, obs))

    # 4. Public IPs (sender IP first)
    ip_items = []
    ip_obs = [obs for obs in observables if obs.get("type") == "ip" and obs.get("is_public")]
    def _ip_priority(obs):
        roles = obs.get("roles") or []
        if "sender_ip" in roles:
            return 3
        if "received_public_ip" in roles:
            return 2
        return 1

    for obs in sorted(ip_obs, key=_ip_priority, reverse=True):
        ip_val = obs.get("value")
        if ip_val:
            ip_items.append((ip_val, obs))

    queues = [
        ("file", sha_items, scan_file_hash),
        ("url", url_items, scan_url),
        ("domain", domain_items, scan_domain),
        ("ip", ip_items, scan_ip),
    ]

    rate_limited = False

    for object_type, items, scanner in queues:
        if not items or rate_limited:
            continue
        logger.info("VIRUSTOTAL %s SCANNING (%d candidates, limit %d)", object_type.upper(), len(items), max_items)
        for value, target in items:
            if target.get("vt") is not None:
                continue
            if scanned >= max_items:
                skipped = {"status": "skipped", "reason": f"max VT item limit reached ({max_items})"}
                target["vt"] = skipped
                logger.info("Skipping remaining VT items: max limit reached.")
                break

            result = scanner(value)
            is_from_cache = result.pop("_from_cache", False)
            target["vt"] = result
            if object_type == "url":
                target["final_url"] = result.get("last_final_url") if result.get("status") == "ok" else None
                target["redirect_chain"] = result.get("redirection_chain", []) if result.get("status") == "ok" else []

            counts[f"{object_type}_count"] += 1
            scanned += 1
            logger.debug("%s: %s -> %s (cached=%s)", object_type.capitalize(), value, vt_summary_text(result), is_from_cache)

            if result.get("status") == "rate_limited":
                logger.warning("VirusTotal rate limit (429) hit. Stopping further VT requests to preserve quota.")
                rate_limited = True
                break

            # Only sleep if network call was made and more items remain
            if not is_from_cache and delay_seconds > 0 and scanned < max_items:
                time.sleep(delay_seconds)

        if scanned >= max_items or rate_limited:
            break

    # If rate limited, mark any unscanned items
    if rate_limited:
        for obs in observables:
            if obs.get("vt") is None and obs.get("type") in {"domain", "ip", "url", "sha256"}:
                obs["vt"] = {"status": "rate_limited", "reason": "VirusTotal API rate limit exceeded"}
        for r in url_records:
            if r.get("vt") is None:
                r["vt"] = {"status": "rate_limited", "reason": "VirusTotal API rate limit exceeded"}
        for a in attachment_results:
            if a.get("vt") is None:
                a["vt"] = {"status": "rate_limited", "reason": "VirusTotal API rate limit exceeded"}

    # Copy VT results onto matching observables
    url_vt_by_value = {r["normalized_url"]: r.get("vt") for r in url_records if r.get("normalized_url")}
    file_vt_by_sha = {(a.get("hashes") or {}).get("sha256"): a.get("vt") for a in attachment_results if (a.get("hashes") or {}).get("sha256")}
    for observable in observables:
        if observable["type"] == "url" and observable["value"] in url_vt_by_value:
            observable["vt"] = url_vt_by_value[observable["value"]]
        elif observable["type"] == "sha256" and observable["value"] in file_vt_by_sha:
            observable["vt"] = file_vt_by_sha[observable["value"]]

    return {"scanned": scanned, "skipped_reason": "rate_limited" if rate_limited else None, **counts}


# ═══════════════════════════════════════════════════════════════════
# URLSCAN.IO — Full Free Tier API Integration
# ═══════════════════════════════════════════════════════════════════

URLSCAN_BASE_URL = "https://urlscan.io/api/v1"


def _urlscan_headers():
    """Return standard headers for urlscan.io API calls."""
    return {
        "API-Key": URL_SCAN_API_KEY,
        "Content-Type": "application/json",
    }


def _urlscan_get(path, params=None):
    """Generic GET request to urlscan.io API."""
    if not URLSCAN_AVAILABLE:
        return {"status": "skipped", "reason": "URL_SCAN_API_KEY is not set"}
    cache_key = ("get", path, tuple(sorted(params.items())) if params else ())
    with _URLSCAN_CACHE_LOCK:
        cached = _URLSCAN_CACHE.get(cache_key)
        if cached is not None:
            return copy.deepcopy(cached)
    try:
        url = f"{URLSCAN_BASE_URL}{path}"
        response = requests.get(url, headers=_urlscan_headers(), params=params,
                                timeout=SETTINGS["urlscan_poll_timeout_seconds"])
        if response.status_code == 429:
            return {"status": "rate_limited", "reason": "urlscan.io rate limit exceeded"}
        if response.status_code == 404:
            return {"status": "not_found", "http_status": 404}
        if response.status_code != 200:
            return {"status": "error", "http_status": response.status_code, "reason": response.text[:300]}
        res = {"status": "ok", "json": response.json()}
        with _URLSCAN_CACHE_LOCK:
            if len(_URLSCAN_CACHE) > 500:
                _URLSCAN_CACHE.pop(next(iter(_URLSCAN_CACHE)))
            _URLSCAN_CACHE[cache_key] = copy.deepcopy(res)
        return res
    except requests.exceptions.RequestException as exc:
        return {"status": "error", "reason": f"Request error: {exc}"}


def _urlscan_request_count(stats):
    """Extract a request count from urlscan stats across schema variants."""
    if isinstance(stats, dict):
        requests = stats.get("requests")
        if isinstance(requests, dict):
            return int(requests.get("total", 0) or 0)
        if isinstance(requests, (int, float)):
            return int(requests)
        return int(stats.get("total", 0) or 0)
    if isinstance(stats, (int, float)):
        return int(stats)
    return 0


def _urlscan_resource_types(stats):
    """Extract per-resource request counts when urlscan returns a breakdown map."""
    if not isinstance(stats, dict):
        return {}
    requests = stats.get("requests")
    if not isinstance(requests, dict):
        return {}
    return {k: v for k, v in requests.items() if k != "total"}


# ── Submit a URL for scanning ────────────────────────────────────

def urlscan_submit(url, tags=None, visibility="private"):
    """Submit a URL for scanning. Returns scan result dict.
    
    Args:
        url: The URL to scan
        tags: Optional list of tag strings (e.g., ["phishing", "case-123"])
        visibility: "public", "unlisted", or "private" (default)
    """
    if not URLSCAN_AVAILABLE:
        return {"status": "skipped", "reason": "URL_SCAN_API_KEY is not set"}

    payload = {
        "url": url,
        "visibility": visibility,
    }
    if tags:
        payload["tags"] = tags[:10]  # urlscan allows up to 10 tags

    try:
        response = requests.post(
            f"{URLSCAN_BASE_URL}/scan/",
            json=payload,
            headers=_urlscan_headers(),
            timeout=SETTINGS["urlscan_request_timeout_seconds"],
        )

        if response.status_code == 429:
            return {"status": "rate_limited", "reason": "urlscan.io rate limit exceeded"}
        if response.status_code == 401:
            return {"status": "error", "reason": "urlscan.io API key invalid"}
        if response.status_code not in {200, 201}:
            return {"status": "error", "http_status": response.status_code, "reason": response.text[:300]}

        data = response.json()
        uuid = data.get("uuid")
        if not uuid:
            return {"status": "error", "reason": "No UUID returned from urlscan.io"}

        result_url = f"{URLSCAN_BASE_URL}/result/{uuid}/"
        return _urlscan_poll_result(result_url)

    except requests.exceptions.RequestException as exc:
        return {"status": "error", "reason": f"Request error: {exc}"}


# ── Search existing scans ────────────────────────────────────────

def urlscan_search(query, size=10):
    """Search urlscan.io for existing scans by domain, IP, URL, or hash.
    
    Uses the /search/ endpoint. Returns results without consuming scan quota.
    
    Args:
        query: Search query (domain, IP, URL, hash, or urlscan query syntax)
        size: Number of results to return (max 100)
    
    Returns:
        dict with status, total, and results list
    """
    result = _urlscan_get("/search/", params={"q": query, "size": min(size, 100)})
    if result.get("status") != "ok":
        return result

    data = result["json"]
    results = []
    for item in data.get("results", []):
        task = item.get("task", {})
        page = item.get("page", {})
        stats = item.get("stats", {})
        verdicts = item.get("verdicts", {})
        overall = verdicts.get("overall", {})

        results.append({
            "scan_id": task.get("uuid"),
            "url": task.get("url"),
            "domain": page.get("domain"),
            "ip": page.get("ip"),
            "country": page.get("country"),
            "server": page.get("server"),
            "status_code": page.get("status"),
            "title": page.get("title"),
            "screenshot_url": task.get("screenshotURL"),
            "report_url": task.get("reportURL"),
            "malicious": overall.get("malicious", False),
            "score": overall.get("score", 0),
            "brands": overall.get("brands", []),
            "categories": overall.get("categories", []),
            "tags": overall.get("tags", []),
            "requests_count": _urlscan_request_count(stats),
            "time": task.get("time"),
            "indexed_at": item.get("indexedAt"),
        })

    return {
        "status": "ok",
        "total": data.get("total", 0),
        "results": results,
        "has_more": data.get("total", 0) > len(results),
    }


def urlscan_search_or_submit(url, tags=None, max_age_days=7):
    """Search for an existing scan first; if not found recently, submit a new one.
    
    Saves scan quota by reusing recent results.
    
    Args:
        url: The URL to search/scan
        tags: Optional tags for new scan
        max_age_days: Only consider scans younger than this
    """
    if not URLSCAN_AVAILABLE:
        return {"status": "skipped", "reason": "URL_SCAN_API_KEY is not set"}

    # Search for existing scan of this exact URL
    search_result = urlscan_search('url:"' + url + '"', size=5)
    if search_result.get("status") == "ok" and search_result.get("results"):
        # Find the most recent non-error result
        for existing in search_result["results"]:
            if existing.get("scan_id"):
                if not _urlscan_result_is_recent(existing.get("time"), max_age_days):
                    continue
                # Fetch full result for the existing scan
                full_result = urlscan_get_result(existing["scan_id"])
                if full_result.get("status") == "ok":
                    full_result["reused_scan"] = True
                    full_result["original_scan_time"] = existing.get("time")
                    logger.info("urlscan.io: reusing existing scan %s for %s", existing["scan_id"], url)
                    return full_result

    # No recent scan found — submit new one
    logger.info("urlscan.io: no recent scan found, submitting new scan for %s", url)
    return urlscan_submit(url, tags=tags)


def _urlscan_result_is_recent(time_value, max_age_days):
    if not time_value:
        return False
    try:
        if isinstance(time_value, (int, float)):
            result_time = datetime.fromtimestamp(time_value, tz=timezone.utc)
        else:
            text = str(time_value).strip().replace("Z", "+00:00")
            result_time = datetime.fromisoformat(text)
            if result_time.tzinfo is None:
                result_time = result_time.replace(tzinfo=timezone.utc)
            else:
                result_time = result_time.astimezone(timezone.utc)
        age_days = (datetime.now(timezone.utc) - result_time).days
        return age_days <= max_age_days
    except Exception:
        return False


# ── Get full scan result ─────────────────────────────────────────

def urlscan_get_result(scan_id):
    """Get the full result of a urlscan.io scan by UUID."""
    result = _urlscan_get(f"/result/{scan_id}/")
    if result.get("status") != "ok":
        return result
    return _urlscan_parse_result(result["json"])


# ── Get DOM snapshot ─────────────────────────────────────────────

def urlscan_get_dom(scan_id):
    """Get the DOM snapshot of a completed scan.
    
    Returns the rendered page DOM as text/HTML.
    """
    if not URLSCAN_AVAILABLE:
        return {"status": "skipped", "reason": "URL_SCAN_API_KEY is not set"}
    try:
        url = f"{URLSCAN_BASE_URL}/result/{scan_id}/dom"
        response = requests.get(url, headers={"API-Key": URL_SCAN_API_KEY},
                                timeout=SETTINGS["urlscan_poll_timeout_seconds"])
        if response.status_code == 404:
            return {"status": "not_found", "reason": "DOM not available (scan may still be in progress)"}
        if response.status_code != 200:
            return {"status": "error", "http_status": response.status_code, "reason": response.text[:200]}
        return {
            "status": "ok",
            "dom": response.text[:50000],  # Truncate large DOMs
            "content_type": response.headers.get("Content-Type", ""),
            "size_bytes": len(response.content),
        }
    except requests.exceptions.RequestException as exc:
        return {"status": "error", "reason": f"Request error: {exc}"}


# ── Get HAR (HTTP Archive) ───────────────────────────────────────

def urlscan_get_har(scan_id):
    """Get the HAR (HTTP Archive) of a completed scan.
    
    Contains all network requests/responses made during the scan.
    Useful for detecting data exfiltration, tracking, and resource loading.
    """
    if not URLSCAN_AVAILABLE:
        return {"status": "skipped", "reason": "URL_SCAN_API_KEY is not set"}
    try:
        url = f"{URLSCAN_BASE_URL}/result/{scan_id}/har"
        response = requests.get(url, headers={"API-Key": URL_SCAN_API_KEY},
                                timeout=SETTINGS["urlscan_poll_timeout_seconds"])
        if response.status_code == 404:
            return {"status": "not_found", "reason": "HAR not available (scan may still be in progress)"}
        if response.status_code != 200:
            return {"status": "error", "http_status": response.status_code, "reason": response.text[:200]}

        har = response.json()
        entries = har.get("log", {}).get("entries", [])

        # Extract useful info from HAR
        requests_summary = []
        domains_seen = set()
        for entry in entries[:100]:  # Limit to first 100 entries
            req = entry.get("request", {})
            resp = entry.get("response", {})
            req_url = req.get("url", "")
            try:
                req_domain = urllib.parse.urlsplit(req_url).hostname or ""
                domains_seen.add(req_domain)
            except Exception:
                req_domain = ""

            requests_summary.append({
                "method": req.get("method"),
                "url": req_url[:500],
                "status": resp.get("status"),
                "content_type": resp.get("content", {}).get("mimeType", ""),
                "size": resp.get("content", {}).get("size", 0),
                "domain": req_domain,
            })

        return {
            "status": "ok",
            "total_entries": len(entries),
            "domains_contacted": sorted(domains_seen)[:50],
            "requests": requests_summary,
        }
    except requests.exceptions.RequestException as exc:
        return {"status": "error", "reason": f"Request error: {exc}"}
    except (ValueError, KeyError) as exc:
        return {"status": "error", "reason": f"HAR parse error: {exc}"}


# ── Polling and result parsing ───────────────────────────────────

def _urlscan_poll_result(result_url, max_wait=25, interval=2):
    """Poll urlscan.io for scan results."""
    headers = {"API-Key": URL_SCAN_API_KEY}
    elapsed = 0

    while elapsed < max_wait:
        try:
            response = requests.get(result_url, headers=headers, timeout=SETTINGS["urlscan_poll_timeout_seconds"])
            if response.status_code == 200:
                return _urlscan_parse_result(response.json())
            if response.status_code == 404:
                time.sleep(interval)
                elapsed += interval
                continue
            return {"status": "error", "http_status": response.status_code, "reason": response.text[:200]}
        except requests.exceptions.RequestException:
            time.sleep(interval)
            elapsed += interval

    return {"status": "timeout", "reason": f"Scan results not ready after {max_wait}s"}


def _urlscan_parse_result(data):
    """Parse urlscan.io result into a clean summary."""
    verdicts = data.get("verdicts", {})
    overall = verdicts.get("overall", {})
    url_verdict = verdicts.get("urlscan", {})
    community = verdicts.get("community", {})

    stats = data.get("stats", {})
    task = data.get("task", {})
    page = data.get("page", {})
    lists = data.get("lists", {})

    summary = {
        "status": "ok",
        "scan_id": task.get("uuid"),
        "url": task.get("url"),
        "screenshot_url": task.get("screenshotURL"),
        "report_url": task.get("reportURL"),
        "dom_url": f"{URLSCAN_BASE_URL}/result/{task.get('uuid')}/dom" if task.get('uuid') else None,
        "har_url": f"{URLSCAN_BASE_URL}/result/{task.get('uuid')}/har" if task.get('uuid') else None,

        # Verdicts
        "malicious": overall.get("malicious", False),
        "score": overall.get("score", 0),
        "categories": overall.get("categories", []),
        "brands": overall.get("brands", []),
        "tags": overall.get("tags", []),

        # urlscan-specific verdicts
        "urlscan_malicious": url_verdict.get("malicious", False),
        "urlscan_score": url_verdict.get("score", 0),
        "urlscan_categories": url_verdict.get("categories", []),
        "urlscan_brands": url_verdict.get("brands", []),

        # Community verdicts
        "community_votes": community.get("votesTotal", 0),
        "community_malicious": community.get("votesMalicious", 0),
        "community_harmless": community.get("votesHarmless", 0),

        # Page info
        "domain": page.get("domain"),
        "ip": page.get("ip"),
        "asn": page.get("asn"),
        "asnname": page.get("asnname"),
        "country": page.get("country"),
        "server": page.get("server"),
        "status_code": page.get("status"),
        "title": page.get("title"),
        "tls_issuer": (page.get("tls") or {}).get("issuer"),
        "tls_valid_from": (page.get("tls") or {}).get("validFrom"),
        "tls_valid_to": (page.get("tls") or {}).get("validTo"),

        # Request stats
        "requests_count": _urlscan_request_count(stats),
        "resource_types": _urlscan_resource_types(stats),
        "unique_countries": stats.get("uniqCountries", 0) if isinstance(stats, dict) else 0,
        "ip_stats": stats.get("ipStats", []) if isinstance(stats, dict) else [],

        # Links found
        "links": lists.get("links", [])[:30],
        "domains": lists.get("domains", [])[:30],
        "certificates": lists.get("certificates", [])[:10],
        "emails": lists.get("emails", [])[:20],
        "hashes": lists.get("hashes", [])[:20],
    }

    return summary


def urlscan_summary_text(result):
    """Generate a human-readable summary of urlscan results."""
    if not result:
        return "not scanned"
    status = result.get("status")
    if status == "skipped":
        return f"skipped: {result.get('reason')}"
    if status == "error":
        return f"error: {result.get('reason')}"
    if status == "timeout":
        return "scan timed out"
    if status == "rate_limited":
        return "API rate limit exceeded"
    if status == "not_found":
        return "not found"
    if status == "ok":
        malicious = result.get("malicious", False)
        score = result.get("score", 0)
        brands = result.get("brands", [])
        reused = " (cached)" if result.get("reused_scan") else ""
        if malicious:
            brand_str = f" ({', '.join(brands)})" if brands else ""
            return f"malicious (score: {score}){brand_str}{reused}"
        if score > 0:
            return f"suspicious (score: {score}){reused}"
        return f"clean{reused}"
    return str(status)


def urlscan_detection_flagged(result):
    """Check if urlscan flagged the URL as malicious or suspicious."""
    if not result or result.get("status") != "ok":
        return False
    return result.get("malicious", False) or result.get("score", 0) > 0
