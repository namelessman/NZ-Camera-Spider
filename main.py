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
from dotenv import load_dotenv

try:
    if os.getenv("GITHUB_ACTIONS"):
        service_account_info = json.loads(os.getenv("GDRIVE_SERVICE_ACCOUNT", "{}"))
    else:
        load_dotenv()
        credentials_path = os.getenv("GDRIVE_CREDENTIALS_PATH")
        if not credentials_path or not os.path.exists(credentials_path):
            raise FileNotFoundError("GDRIVE_CREDENTIALS_PATH is not set or file not found.")
        with open(credentials_path) as f:
            service_account_info = json.load(f)

    if not service_account_info or "client_email" not in service_account_info:
        raise ValueError("Invalid service account info: Missing 'client_email' field.")

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    drive_service = build('drive', 'v3', credentials=credentials)

except Exception as e:
    logging.exception("Google Drive authentication failed")
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
    except (RequestException, json.JSONDecodeError) as e:
        logging.error(f"API request failed: {e}")
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
    except RequestException as e:
        logging.error(f"Download error {camera.get('id')}: {e}")

def get_or_create_drive_folder(parent_id, folder_name):
    query = (
        f"name = '{folder_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )
    response = drive_service.files().list(q=query, fields='files(id, name)').execute()
    folders = response.get('files', [])
    if folders:
        return folders[0]['id']
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = drive_service.files().create(body=file_metadata, fields='id, name').execute()
    return folder['id']


def upload_to_google_drive(file_path, parent_id):
    root_dir = os.path.abspath("camera_images")  # Set root directory explicitly
    file_path_abs = os.path.abspath(file_path)

    if not file_path_abs.startswith(root_dir):
        logging.error(f"File path {file_path_abs} is not under root directory {root_dir}")
        print(f"File path {file_path_abs} is not under root directory {root_dir}")
        return

    relative_path = os.path.relpath(file_path_abs, root_dir)
    folder_path = os.path.dirname(relative_path).split(os.sep)

    print('root_dir:', root_dir)
    print('file_path:', file_path_abs)
    print('relative_path:', relative_path)
    print('folder_path:', folder_path)

    current_folder = parent_id
    for folder_name in folder_path:
        if folder_name:
            current_folder = get_or_create_drive_folder(current_folder, folder_name)
            print('current_folder:', current_folder)

    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [current_folder]
    }
    media = MediaFileUpload(file_path, mimetype='image/jpeg')
    drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()


def upload_images_in_folder(folder_path, parent_id):
    print('folder_path:', folder_path)
    for root, _, files in os.walk(folder_path):
        for image_file in files:
            print('image_file:', image_file)
            if image_file.endswith(('.jpg', '.png')):
                image_path = os.path.join(root, image_file)
                print('image_path:', image_path)
                upload_to_google_drive(image_path, parent_id)

def upload_log_file(log_file, folder_id=None):
    upload_to_google_drive(log_file, folder_id)

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
    # upload_log_file(log_file, google_drive_folder_id)

if __name__ == "__main__":
    main()
