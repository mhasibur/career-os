"""Daily career brief: finds UK data/ML jobs, flags licensed sponsors,
writes jobs.json for the dashboard and sends a Telegram message.
Uses only the Python standard library. Secrets come from environment variables."""
import csv
import datetime
import io
import json
import os
import re
import urllib.parse
import urllib.request

TODAY = datetime.date.today()
VISA_END = datetime.date.fromisoformat(os.environ.get("VISA_END", "2028-11-04"))
ROLES = ["data analyst", "data scientist", "machine learning engineer", "ai engineer", "graduate data"]
SPONSOR_PAGE = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"


def http(url, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def norm(name):
    n = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    n = re.sub(r"\b(ltd|limited|plc|llp|llc|inc|uk|group|the)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def load_sponsors():
    """Return a set of normalised licensed-sponsor names, or None if it cannot be loaded."""
    try:
        page = http(SPONSOR_PAGE).decode("utf-8", "ignore")
        links = re.findall(r'https://assets\.publishing\.service\.gov\.uk/[^"\'<>\s]+\.csv', page)
        if not links:
            return None
        link = next((l for l in links if "worker" in l.lower()), links[0])
        raw = http(link, timeout=120).decode("utf-8-sig", "ignore")
        names = set()
        for row in csv.DictReader(io.StringIO(raw)):
            if "skilled worker" in (row.get("Route") or "").lower():
                names.add(norm(row.get("Organisation Name")))
        return names or None
    except Exception as e:
        print("Sponsor list failed:", type(e).__name__)
        return None


def _demo_jobs():
    """Sample job entries used when running in DEMO_MODE without real credentials."""
    return [
        {
            "title": "Data Scientist",
            "company": "Nexus AI Labs",
            "location": "London, UK",
            "url": "https://www.adzuna.co.uk/jobs/details/demo1",
            "salary_min": 65000,
            "salary_max": 85000,
            "created": TODAY.isoformat(),
        },
        {
            "title": "Machine Learning Engineer",
            "company": "Quantica Analytics",
            "location": "Manchester, Greater Manchester",
            "url": "https://www.adzuna.co.uk/jobs/details/demo2",
            "salary_min": 70000,
            "salary_max": 90000,
            "created": TODAY.isoformat(),
        },
        {
            "title": "Graduate Data Analyst",
            "company": "Bloom Health Tech",
            "location": "Edinburgh, Scotland",
            "url": "https://www.adzuna.co.uk/jobs/details/demo3",
            "salary_min": 30000,
            "salary_max": 38000,
            "created": TODAY.isoformat(),
        },
    ]


def fetch_jobs():
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    demo = os.environ.get("DEMO_MODE", "").lower() in {"1", "true", "yes"}
    if not app_id or not app_key:
        if demo:
            print("Adzuna credentials missing; running in demo mode with sample data.")
            return _demo_jobs()
        print("Adzuna API credentials missing (ADZUNA_APP_ID / ADZUNA_APP_KEY). Skipping fetch.")
        return []
    found = {}
    for query in ROLES:
        params = urllib.parse.urlencode({
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": 30,
            "what": query,
            "max_days_old": 7,
            "sort_by": "date",
        })
        try:
            data = json.loads(http("https://api.adzuna.com/v1/api/jobs/gb/search/1?" + params))
        except Exception as e:
            print("Adzuna failed for", query, type(e).__name__)
            continue
        for j in data.get("results", []):
            found[j["id"]] = {
                "title": j.get("title", "").replace("<strong>", "").replace("</strong>", ""),
                "company": (j.get("company") or {}).get("display_name", "Unknown"),
                "location": (j.get("location") or {}).get("display_name", ""),
                "url": j.get("redirect_url", ""),
                "salary_min": j.get("salary_min"),
                "salary_max": j.get("salary_max"),
                "created": (j.get("created") or "")[:10],
            }
    return list(found.values())


def salary(j):
    lo, hi = j.get("salary_min"), j.get("salary_max")
    if lo and hi:
        return f"£{int(lo):,}–£{int(hi):,}"
    if lo or hi:
        return f"£{int(lo or hi):,}"
    return "salary not listed"


def make_brief(jobs, days_left):
    key = os.environ.get("GEMINI_API_KEY")
    fallback = ("Today: 1.5 hours learning (SQL or Python), 30 minutes on a project, "
                "30 minutes applying or messaging people.")
    if not key:
        return fallback
    top = "\n".join(f"- {j['title']} at {j['company']} ({j['location']})" for j in jobs[:8]) or "- none found today"
    prompt = (
        "Write a short morning brief (under 120 words, plain text, no markdown) for Hasibur, "
        "an MSc AI and Data Science graduate in the UK on a Graduate visa who needs a sponsored job. "
        f"Days left on the visa: {days_left}. His project is traffic forecasting with graph neural networks. "
        "Give: one focus for learning today, one small project task, and one sentence on the job list below. "
        "Use only the data given. Be direct and encouraging.\n\nJobs found:\n" + top
    )
    model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    try:
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        out = json.loads(http(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
        ))
        return out["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print("Gemini failed:", type(e).__name__)
        return fallback


def send_telegram(text):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        print("Telegram credentials missing (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID). Skipping Telegram notification.")
        return
    body = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text[:4000],
        "disable_web_page_preview": "true",
    }).encode()
    try:
        http(f"https://api.telegram.org/bot{bot_token}/sendMessage", data=body)
        print("Telegram sent")
    except Exception as e:
        print("Telegram failed:", type(e).__name__)


def main():
    days_left = (VISA_END - TODAY).days
    sponsors = load_sponsors()
    jobs = fetch_jobs()

    if jobs:
        for j in jobs:
            j["sponsor"] = (norm(j["company"]) in sponsors) if sponsors else None
        jobs.sort(key=lambda j: (j["sponsor"] is not True, -int((j["created"] or "0").replace("-", "") or 0)))
        jobs = jobs[:40]

        with open("jobs.json", "w", encoding="utf-8") as f:
            json.dump({
                "updated": datetime.datetime.utcnow().isoformat() + "Z",
                "sponsor_list_loaded": sponsors is not None,
                "jobs": jobs,
            }, f, ensure_ascii=False, indent=1)
    else:
        # Load existing jobs if available
        try:
            with open("jobs.json", "r", encoding="utf-8") as f:
                jobs = json.load(f).get("jobs", [])
        except Exception:
            jobs = []

    shown = [j for j in jobs if j.get("sponsor")] or jobs
    lines = [f"Good morning, Hasibur. {days_left} days left on your visa.", "", make_brief(jobs, days_left), ""]
    label = "Licensed sponsors hiring" if any(j.get("sponsor") for j in jobs) else "New jobs (sponsor check unavailable)"
    lines.append(f"{label}:")
    for j in shown[:8]:
        lines.append(f"• {j['title']} - {j['company']}, {j['location']} ({salary(j)})\n{j['url']}")
    send_telegram("\n".join(lines))


if __name__ == "__main__":
    main()