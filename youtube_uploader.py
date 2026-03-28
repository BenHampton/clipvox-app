"""Isolated YouTube upload class for ClipVox."""

import os
import shutil
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = ".youtube_token.json"


class YouTubeUploader:
    def __init__(self, config):
        self._config = config["youtube"]
        self._client_id = os.getenv("YOUTUBE_CLIENT_ID")
        self._client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")

        if not self._client_id or not self._client_secret:
            raise RuntimeError(
                "YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set in .env"
            )

        self._service = self._build_service()

    def _build_service(self):
        creds = None

        if Path(TOKEN_FILE).exists():
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                client_config = {
                    "installed": {
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
                    }
                }
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=0)

            Path(TOKEN_FILE).write_text(creds.to_json())

        return build("youtube", "v3", credentials=creds)

    def upload(self, video_path):
        """Upload a video to YouTube and return the video URL."""
        video_path = Path(video_path)
        cfg = self._config

        body = {
            "snippet": {
                "title": cfg.get("title", "ClipVox Short"),
                "description": cfg.get("description", ""),
                "tags": cfg.get("tags", []),
                "categoryId": str(cfg.get("categoryId", 22)),
            },
            "status": {
                "privacyStatus": cfg.get("privacyStatus", "private"),
            },
        }

        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)

        print(f"Uploading: {video_path.name}")
        request = self._service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  Upload progress: {int(status.progress() * 100)}%")

        media._fd.close()

        video_id = response["id"]
        url = f"https://www.youtube.com/shorts/{video_id}"
        print(f"Upload complete: {url}")

        uploaded_dir = video_path.parent / "uploaded"
        uploaded_dir.mkdir(exist_ok=True)
        shutil.move(str(video_path), str(uploaded_dir / video_path.name))
        print(f"Moved to: {uploaded_dir / video_path.name}")

        return url
