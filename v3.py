import os
import datetime
import re
import unicodedata
import json
import time
import schedule
import webbrowser
import pandas as pd
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from twilio.rest import Client

# --------------------
# 🔹 1. Încărcare variabile din .env
# --------------------
load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
TWILIO_CONTENT_SID = os.getenv("TWILIO_CONTENT_SID")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE = os.getenv("TOKEN_FILE", "token.json")

# --------------------
# 🔹 2. Configurare Twilio
# --------------------
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# --------------------
# 🔹 3. Setări Google API
# --------------------
SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly'
]
BASIL_COLOR_ID = "8"

class LynxBrowser(webbrowser.BaseBrowser):
    def open(self, url, new=0, autoraise=True):
        os.system(f"lynx {url}")
webbrowser.register('lynx', None, LynxBrowser())

# --------------------
# 🔹 4. Autentificare Google
# --------------------
def autentificare_google_calendar():
    creds = None
    
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                print("Token invalid. Reautentificare necesară.")
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return creds

creds = autentificare_google_calendar()
service = build('calendar', 'v3', credentials=creds)

# --------------------
# 🔹 5. Citire contacte din Google Sheets
# --------------------
def read_google_sheet(spreadsheet_id, range_name):
    try:
        sheets_service = build('sheets', 'v4', credentials=creds)
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        values = result.get('values', [])
        
        if not values:
            print('Nu există date în Google Sheet.')
            return None
            
        headers = values[0]
        data = values[1:]
        return pd.DataFrame(data, columns=headers)
    except Exception as e:
        print(f'Eroare citire Google Sheet: {e}')
        return None

RANGE_NAME = 'Foaie1!A:G'
df = read_google_sheet(SPREADSHEET_ID, RANGE_NAME)

# --------------------
# 🔹 6. Funcții utilitare
# --------------------
def elimina_diacritice(text):
    return unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')

def extrage_nume_din_titlu(titlu_eveniment):
    titlu_normalizat = elimina_diacritice(titlu_eveniment)
    pattern = r"([A-Z][a-z]+(?:-[A-Z][a-z]+)*)(?: [A-Z][a-z]+(?:-[A-Z][a-z]+)*)?"
    match = re.search(pattern, titlu_normalizat, re.IGNORECASE)
    return match.group(0).upper() if match else None

def verifica_potrivire_nume(nume_partial, nume_complet):
    nume_complet_normalizat = elimina_diacritice(nume_complet)
    return all(part in nume_complet_normalizat.split() for part in nume_partial.split())

# --------------------
# 🔹 7. Debug: listare calendare
# --------------------
def listare_calendare():
    calendar_list = service.calendarList().list().execute()
    print("Calendarele disponibile:")
    for calendar_entry in calendar_list['items']:
        print(f"{calendar_entry['summary']} - ID: {calendar_entry['id']}")

# --------------------
# 🔹 8. Funcția principală - trimitere reminderuri
# --------------------
def trimite_reminderuri():
    try:
        now = datetime.datetime.now()
        start_of_day = datetime.datetime.combine(now.date(), datetime.time.min).replace(tzinfo=now.astimezone().tzinfo)
        end_of_day = datetime.datetime.combine(now.date(), datetime.time.max).replace(tzinfo=now.astimezone().tzinfo)

        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            print('Nu există evenimente astăzi.')
            return

        for event in events:
            event_time = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in event_time:
                event_time = datetime.datetime.fromisoformat(event_time).strftime('%H:%M')
            else:
                event_time = 'N/A'

            event_name = event['summary']

            if 'colorId' not in event or event['colorId'] == BASIL_COLOR_ID:
                nume_partial = extrage_nume_din_titlu(event_name)
                if not nume_partial:
                    print(f"Nu s-a găsit un nume în '{event_name}'.")
                    continue

                pacient_gasit = False
                for _, row in df.iterrows():
                    if verifica_potrivire_nume(nume_partial, row['Nume']):
                        pacient_gasit = True
                        try:
                            client.messages.create(
                                messaging_service_sid=TWILIO_MESSAGING_SERVICE_SID,
                                content_sid=TWILIO_CONTENT_SID,
                                to=f"whatsapp:{row['Telefon']}",
                                content_variables=json.dumps({"1": event_time}),
                            )
                            print(f"Mesaj trimis către {row['Nume']} - {row['Telefon']}")
                        except Exception as e:
                            print(f"Eroare la trimitere: {e}")
                        break

                if not pacient_gasit:
                    print(f"Pacientul '{nume_partial}' nu a fost găsit în listă.")

    except Exception as e:
        print(f'Eroare: {e}')

# --------------------
# 🔹 9. Programarea task-urilor
# --------------------
listare_calendare()
schedule.every().day.at("07:50").do(trimite_reminderuri)
schedule.every(360).minutes.do(lambda: autentificare_google_calendar())

if __name__ == '__main__':
    print("📅 Programul de autentificare Google Calendar a început.")
    trimite_reminderuri()
    while True:
        schedule.run_pending()
        time.sleep(1)
