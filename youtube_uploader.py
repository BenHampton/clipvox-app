"""Isolated YouTube upload class for ClipVox."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from clip_registry import mark_uploaded

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

    def _check_token_expiry(self):
        """Reads the expiry field from the token file and logs whether it is still valid."""
        token_path = Path(TOKEN_FILE)
        if not token_path.exists():
            return
        try:
            data = json.loads(token_path.read_text())
            expiry_str = data.get("expiry")
            if not expiry_str:
                return
            expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if now >= expiry:
                print(f"YouTube token expired at {expiry.strftime('%Y-%m-%d %H:%M:%S UTC')} — refreshing...")
            else:
                remaining = int((expiry - now).total_seconds() / 60)
                print(f"YouTube token valid for ~{remaining} more minute(s).")
        except Exception:
            pass

    def _build_service(self):
        self._check_token_expiry()

        creds = None

        if Path(TOKEN_FILE).exists():
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                print("YouTube token refreshed.")
            else:
                print("No valid YouTube token found — starting browser authentication...")
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
            print(f"YouTube token saved to {TOKEN_FILE}.")

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

        mark_uploaded(video_path.name, video_id, url)

        video_path.unlink()
        print(f"Deleted: {video_path.name}")

        return url
