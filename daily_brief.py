import os
import json
import requests
import google.generativeai as genai

# Load environment variables
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
VISA_END = os.getenv("VISA_END", "2028-11-04")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

def fetch_jobs():
    url = f"https://api.adzuna.com/v1/api/jobs/gb/search/1?app_id={ADZUNA_APP_ID}&app_key={ADZUNA_APP_KEY}&results_per_page=10&what=data%20analyst%20OR%20data%20scientist%20OR%20machine%20learning"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("results", [])
    return []

def generate_ai_brief(jobs):
    job_summary_input = "\n".join([f"- {j.get('title')} at {j.get('company', {}).get('display_name')} (Location: {j.get('location', {}).get('display_name')}) - Link: {j.get('redirect_url')}" for j in jobs[:5]])
    
    prompt = f"""
    You are a UK Career Advisor. Analyze these recent UK job openings for Data & AI roles:
    {job_summary_input}
    
    Create a concise, encouraging daily brief in Bengali/English mix (Banglish style or plain English with bullet points).
    Format the output cleanly for Telegram and Web Dashboard:
    1. 🎯 **Top UK Market Overview**: 1-2 sentence breakdown.
    2. 💡 **Key Skills in Demand**: Mention 3-4 top tech skills needed.
    3. 🚀 **Featured Opportunities**: List top 3 jobs with Company Name, Location, and a short note on why it fits. Include direct links.
    4. ⏳ **Visa Countdown Advice**: A quick 1-line action tip for postgraduate job seekers.
    Keep formatting clean using bolding and emojis.
    """
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response.text

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

def main():
    jobs = fetch_jobs()
    brief_text = generate_ai_brief(jobs)
    
    # Send formatted brief to Telegram
    send_telegram_message(brief_text)
    
    # Save formatted brief for Dashboard UI
    dashboard_data = {
        "last_updated": os.getenv("RUN_DATE", "Today"),
        "brief": brief_text,
        "jobs": jobs[:5]
    }
    with open("jobs.json", "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()