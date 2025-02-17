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

try:
    service_account_info = json.loads(os.getenv("GDRIVE_SERVICE_ACCOUNT", "{}"))
    if not service_account_info:
        raise ValueError("GDRIVE_SERVICE_ACCOUNT environment variable is not set or invalid")
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    drive_service = build('drive', 'v3', credentials=credentials)
except Exception as e:
    logging.error(f"Google Drive authentication failed: {e}")
    raise SystemExit(f"Google Drive authentication failed: {e}")

base_url = "https://trafficnz.info"
api_url = "https://trafficnz.info/service/traffic/rest/4/cameras/all"
google_drive_folder_id = "1YNiyHl3zsmsqJtzt0ECqP-rR-1fY3rF6"

now = datetime.now()
date_folder = now.strftime("%Y-%m-%d")
time_folder = now.strftime("%H-%M")

output_dir = os.path.join("camera_images", date_folder, time_folder)
os.makedirs(output_dir, exist_ok=True)

log_dir = os.path.join("camera_images", "logs")
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f"fetch_log_{date_folder}.log")

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def fetch_camera_data():
    try:
        response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=10)
        response.raise_for_status()
        return response.json()
    except RequestException as e:
        logging.error(f"API request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"API response format error: {e}")
        return None

def download_image(camera):
    image_url = base_url + camera.get('imageUrl', '')
    image_path = os.path.join(output_dir, f"{camera.get('id', 'unknown')}.jpg")

    if os.path.exists(image_path):
        logging.info(f"Image already exists, skipping: {image_path}")
        return

    try:
        response = requests.get(image_url, stream=True, timeout=15)
        if response.status_code == 200:
            with open(image_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            logging.info(f"Downloaded: {image_path}")
        else:
            logging.error(f"Download failed {image_url}, Status code: {response.status_code}")
    except RequestException as e:
        logging.error(f"Download error {camera.get('id')}: {e}")

def upload_to_google_drive(file_path, folder_id=None, retries=3):
    file_name = os.path.basename(file_path)
    file_metadata = {'name': file_name, 'parents': [folder_id] if folder_id else []}
    media = MediaFileUpload(file_path, mimetype='image/jpeg')

    for attempt in range(1, retries + 1):
        try:
            uploaded_file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            logging.info(f"Uploaded: {file_name}, File ID: {uploaded_file.get('id')}")
            return
        except Exception as e:
            logging.error(f"Upload failed (Attempt {attempt}): {file_name}, Error: {e}")
            time.sleep(2 ** attempt)
    logging.error(f"Upload failed: {file_name} after {retries} attempts")

def upload_images_in_folder(folder_path, folder_id=None):
    image_files = [f for f in os.listdir(folder_path) if f.endswith(('.jpg', '.png'))]
    if not image_files:
        logging.warning(f"No images found in directory {folder_path}")
        return
    for image_file in image_files:
        image_path = os.path.join(folder_path, image_file)
        upload_to_google_drive(image_path, folder_id)

def main():
    data = fetch_camera_data()
    if not data:
        logging.error("No camera data retrieved, exiting")
        return

    cameras = data.get('response', {}).get('camera', [])[:5]
    if not cameras:
        logging.warning("No cameras found in API response")
        return

    for camera in cameras:
        download_image(camera)

    upload_images_in_folder(output_dir, google_drive_folder_id)

if __name__ == "__main__":
    main()
