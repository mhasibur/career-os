import os
import json
import requests
import google.generativeai as genai
from datetime import datetime

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DEMO_MODE = os.getenv("DEMO_MODE", "").lower() in {"1", "true", "yes"}

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def _demo_jobs():
    """Sample job entries used when running in DEMO_MODE without real credentials."""
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        {
            "title": "Data Scientist",
            "company": {"display_name": "Nexus AI Labs"},
            "location": {"display_name": "London, UK"},
            "redirect_url": "https://www.adzuna.co.uk/jobs/details/demo1",
            "salary_min": 65000,
            "salary_max": 85000,
            "created": today,
        },
        {
            "title": "Machine Learning Engineer",
            "company": {"display_name": "Quantica Analytics"},
            "location": {"display_name": "Manchester, Greater Manchester"},
            "redirect_url": "https://www.adzuna.co.uk/jobs/details/demo2",
            "salary_min": 70000,
            "salary_max": 90000,
            "created": today,
        },
        {
            "title": "Graduate Data Analyst",
            "company": {"display_name": "Bloom Health Tech"},
            "location": {"display_name": "Edinburgh, Scotland"},
            "redirect_url": "https://www.adzuna.co.uk/jobs/details/demo3",
            "salary_min": 30000,
            "salary_max": 38000,
            "created": today,
        },
    ]

def fetch_jobs():
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        if DEMO_MODE:
            print("Adzuna credentials missing; running in demo mode with sample data.")
            return _demo_jobs()
        print("Adzuna API credentials missing (ADZUNA_APP_ID / ADZUNA_APP_KEY). Skipping fetch.")
        return []

    try:
        url = f"https://api.adzuna.com/v1/api/jobs/gb/search/1?app_id={ADZUNA_APP_ID}&app_key={ADZUNA_APP_KEY}&results_per_page=10&what=data%20analyst%20OR%20data%20scientist%20OR%20machine%20learning"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json().get("results", [])
        else:
            print(f"Adzuna API error: {response.status_code}")
            if DEMO_MODE:
                return _demo_jobs()
            return []
    except Exception as e:
        print(f"Adzuna fetch failed: {type(e).__name__}: {e}")
        if DEMO_MODE:
            return _demo_jobs()
        return []

def generate_ai_brief(jobs):
    job_summary_input = "\n".join([
        f"- {j.get('title')} at {j.get('company', {}).get('display_name')} (Location: {j.get('location', {}).get('display_name')}) - Link: {j.get('redirect_url')}"
        for j in jobs[:5]
    ]) or "- No jobs found today"

    prompt = f"""
    You are a UK Career Advisor. Analyze these recent UK job openings for Data & AI roles:
    {job_summary_input}
    
    Create a concise, encouraging daily brief in Banglish/English mix.
    Format cleanly for Telegram and Dashboard UI:
    1. 🎯 Market Overview
    2. 💡 Key Skills Needed
    3. 🚀 Featured Job Opportunities with direct links
    """

    if not GEMINI_API_KEY:
        return _fallback_brief(jobs)

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini failed: {type(e).__name__}: {e}")
        return _fallback_brief(jobs)


def _fallback_brief(jobs):
    """Generate a basic brief without AI when API is unavailable."""
    today = datetime.now().strftime("%A, %B %d")
    job_lines = "\n".join([
        f"• {j.get('title')} at {j.get('company', {}).get('display_name')} ({j.get('location', {}).get('display_name')})"
        for j in jobs[:3]
    ]) or "• No new listings today"

    return f"""📅 **Daily Career Brief — {today}**

🎯 **Market Overview**
UK data & AI market remains active with roles across London, Manchester, and remote-first companies. Focus on showcasing your GNN traffic forecasting project — it's a strong differentiator for ML roles.

💡 **Key Skills Needed**
• Python (PyTorch/TensorFlow) for Graph Neural Networks
• SQL & data pipelines for production ML
• Cloud (AWS/GCP) & MLOps basics

🚀 **Featured Opportunities**
{job_lines}

💪 *Keep building, keep applying. Your sponsored role is out there.*"""

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID). Skipping Telegram notification.")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message[:4000],
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        requests.post(url, json=payload, timeout=20)
        print("Telegram sent")
    except Exception as e:
        print(f"Telegram failed: {type(e).__name__}: {e}")

def main():
    jobs = fetch_jobs()
    brief_text = generate_ai_brief(jobs)

    send_telegram_message(brief_text)

    dashboard_data = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "brief": brief_text,
        "jobs": jobs[:5]
    }
    try:
        with open("jobs.json", "w", encoding="utf-8") as f:
            json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
        print("Dashboard data written to jobs.json")
    except Exception as e:
        print(f"Failed to write jobs.json: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()