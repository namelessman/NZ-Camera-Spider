import requests
import json
import os
from datetime import datetime
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from requests.exceptions import RequestException
import time

credentials_path = "google_service_account.json"
if not os.path.exists(credentials_path):
    raise FileNotFoundError("Google credentials file not found. Place 'google_service_account.json' in the project root.")
with open(credentials_path) as f:
    service_account_info = json.load(f)
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build('drive', 'v3', credentials=credentials)

base_url = "https://trafficnz.info"
api_url = "https://trafficnz.info/service/traffic/rest/4/cameras/all"
google_drive_folder_id = "1YNiyHl3zsmsqJtzt0ECqP-rR-1fY3rF6"

now = datetime.now()
output_dir = "manual_test_images"
os.makedirs(output_dir, exist_ok=True)

log_file = "manual_test_log.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s"
)

def fetch_camera_data():
    response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=10)
    response.raise_for_status()
    return response.json()

def download_image(camera):
    image_url = base_url + camera.get('imageUrl', '')
    image_path = os.path.join(output_dir, f"{camera.get('id', 'unknown')}.jpg")
    if not os.path.exists(image_path):
        response = requests.get(image_url, stream=True, timeout=15)
        if response.status_code == 200:
            with open(image_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

def upload_to_google_drive(file_path, folder_id):
    file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/jpeg')
    drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

def main():
    data = fetch_camera_data()
    for camera in data.get('response', {}).get('camera', [])[:5]:
        download_image(camera)
    for image_file in os.listdir(output_dir):
        if image_file.endswith('.jpg'):
            upload_to_google_drive(os.path.join(output_dir, image_file), google_drive_folder_id)

if __name__ == "__main__":
    main()
