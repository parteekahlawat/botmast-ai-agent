import os
import json
import requests
import smtplib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request, jsonify
import re

from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai
gemini_api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=gemini_api_key)
# Flask app
app = Flask(__name__)

# VAPI API Key
VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_API_CALL = "https://api.vapi.ai/call"

# Google Sheets API Setup
SHEET_NAME = "Vapi Call Logs"
SHEET_CREDENTIALS = "credentials.json"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(SHEET_CREDENTIALS, scope)
client = gspread.authorize(creds)
SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1FxLA3JYdz_9V1IMgOUFTm0gUUZ_HqNRK3XL_5a64Jsk/edit?usp=sharing'

sheet = client.open_by_url(SPREADSHEET_URL).sheet1

# Email Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


model = genai.GenerativeModel("gemini-1.5-flash")
chat = model.start_chat(
    history=[
        {"role": "user", "parts": "Hello"},
        {"role": "model", "parts": "Great to meet you. What would you like to know?"},
    ]
)
def log_to_sheets(log_data, event):
    """Logs Vapi call data to Google Sheets."""
    sheet.append_row([log_data['Phone Number'],
                      ", ".join(log_data['User Messages']),  # Join multiple messages into a single string
                      ", ".join(log_data['Bot Messages']),  
                      log_data['Summary'],
                      event.get('Time'),
                      event.get('Date')])
    print("Added to sheet!")

def send_confirmation_email(email, appointment_time):
    """Sends confirmation email to the user."""
    subject = "Appointment Confirmation"
    body = f"Your appointment is confirmed for {appointment_time}.\n\nThank you!"
    message = f"Subject: {subject}\n\n{body}"
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)  
            server.sendmail(EMAIL_SENDER, email, message) 
        print(f"Email sent to {email}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print("There was an issue while sending the email. Please check the details and try again.")
        

def generate_data(msg):
    prompt = f"""
    Please give me the date, time, email, name in the json format from the message given
    Message - {msg}
    
    json format - 
        "Time": proper time,
        "Date": Date,
        "Email": email id,
        "Name": name,
    
    I only want json format and no other text, if no date or time found then write null in the json
    """
    result = model.generate_content(prompt)
    json_match = re.search(r"\{.*\}", result.text.strip(), re.DOTALL)

    event_data = json.loads(json_match.group()) 
    # print(event_data.get('Time'))
    return event_data


def fetch_vapi_data():
    """Fetches call data from Vapi API."""
    headers = {"Authorization": f"Bearer {VAPI_API_KEY}"}
    response = requests.get(VAPI_API_CALL, headers=headers)
    if response.status_code == 200:
        call_data = response.json()
        # print(type(call_data))
        for call in call_data:
            log_data = {
                'Phone Number': call.get('customer', {}).get('number', "NA"),
                'User Messages': [msg.get('message', '') for msg in call.get('messages', {}) if msg.get('role') == 'user'],
                'Bot Messages': [msg.get('message', '') for msg in call.get('messages', {}) if msg.get('role') == 'bot'],
                'Summary': call.get('summary', "NA"),
            }
            print("Data Added")
            event_info = generate_data(", ".join(log_data['User Messages']))
            print("Data Generated")
            log_to_sheets(log_data, event_info)
            print(event_info)
            email_get = event_info.get('Email')
            if email_get=="None" or email_get==None or email_get=="null":
                print("Email Not valid - ", email_get)
            else:
                send_confirmation_email(event_info.get('Email'), event_info.get('Time'))

    else:
        print("Failed to fetch data from Vapi API", response.status_code, response.text)

@app.route("/")
def apprun():
    fetch_vapi_data()
    return "Data Added"
    
if __name__ == "__main__":
    app.run(debug=True)
