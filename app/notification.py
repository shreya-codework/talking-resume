import os
from dotenv import load_dotenv
import requests

load_dotenv(override = True)

def push_notification(message):
    url = "https://api.pushover.net/1/messages.json"
    token = os.getenv("PUSHOVER_TOKEN")
    user = os.getenv("PUSHOVER_USER")
    payload={
        "token": token, 
        "user": user, 
        "message": message
    }
    response = requests.post(url, data = payload)
    print(response.status_code)