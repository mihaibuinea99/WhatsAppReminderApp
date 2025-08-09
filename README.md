**WhatsApp Reminder App**
A lightweight Python app that reads today’s appointments from Google Calendar, matches patient names to a contacts list in Google Sheets, and sends WhatsApp reminders via Twilio (Messaging Service + approved template). It runs on a schedule, uses environment variables for configuration, and keeps all credentials out of Git.
Features: Google Calendar + Sheets integration, WhatsApp reminders via Twilio, daily scheduling, .env-based config
Tech: Python, Google APIs, Twilio, pandas, schedule, python-dotenv
Setup: Copy env.template to .env, fill values, keep credentials.json/token.json local, then run v3.py
