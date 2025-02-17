# NZ Camera Spider

This project is aimed to fetch real-time camera images and upload them to Google Drive.

The API is publicly offered by [NZTA](https://www.nzta.govt.nz/traffic-and-travel-information/use-our-data/about-the-apis/).

`main.py` is the entrance of the file. `local.py` is for debug at local.

To upload the images to Google Drive, you need to create a `Service accounts` and enable `Google Drvie API`.

If you want to run the script at local, you need to name the credential file as `google_service_account.json`.

If you want to run the script on Github Actions, you need to set the env `GDRIVE_SERVICE_ACCOUNT` as the credential file conent.
