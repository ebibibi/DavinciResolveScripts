"""Upload out/final.mp4 of a job as a PRIVATE YouTube video with its title, description, captions
and thumbnail. Idempotent: out/youtube_upload.json prevents a second upload."""
import json
import os
import shutil
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

TOKEN = Path(os.path.expanduser(os.environ.get("YT_TOKEN", "~/obsidian/scripts/token.json")))
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CATEGORY_SCIENCE_TECH = "28"
# Post-upload metadata automation reads this to keep the editor's thumbnail instead of generating one.
HANDOFF_DIR = Path(os.path.expanduser(os.environ.get("EDIT_HANDOFF_DIR", "~/video-jobs/handoff")))


def write_handoff(video_id: str, out: Path) -> None:
    """Leave the editor's thumbnail and metadata where the post-upload automation looks for them."""
    target = HANDOFF_DIR / video_id
    target.mkdir(parents=True, exist_ok=True)
    for name in ("thumbnail.png", "youtube.json"):
        if (out / name).exists():
            shutil.copy2(out / name, target / name)
    print(f"handoff written: {target}")


def client():
    if not TOKEN.exists():
        sys.exit(f"YouTube token not found: {TOKEN}")
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        creds.refresh(Request())  # the token file is shared, so it is not written back
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def main(job: Path) -> None:
    out = job / "out"
    record = out / "youtube_upload.json"
    if record.exists():
        print(f"already uploaded: {json.loads(record.read_text())['url']}")
        return
    meta = json.loads((out / "youtube.json").read_text(encoding="utf-8"))
    yt = client()
    body = {
        "snippet": {"title": meta["title"][:100], "description": meta["description"][:5000],
                    "tags": meta.get("tags", [])[:30], "categoryId": CATEGORY_SCIENCE_TECH,
                    "defaultLanguage": "ja", "defaultAudioLanguage": "ja"},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(out / "final.mp4"), chunksize=16 * 1024 * 1024,
                                                        resumable=True))
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"upload {int(status.progress() * 100)}%", flush=True)
    done = {"video_id": resp["id"], "url": f"https://youtu.be/{resp['id']}", "privacy": "private"}
    record.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"uploaded (private): {done['url']}")
    write_handoff(done["video_id"], out)

    for name, action in (("captions.srt", "captions"), ("thumbnail.png", "thumbnail")):
        path = out / name
        if not path.exists():
            continue
        try:
            if action == "captions":
                yt.captions().insert(part="snippet",
                                     body={"snippet": {"videoId": done["video_id"], "language": "ja", "name": "日本語"}},
                                     media_body=MediaFileUpload(str(path), mimetype="application/octet-stream")).execute()
            else:
                yt.thumbnails().set(videoId=done["video_id"], media_body=MediaFileUpload(str(path))).execute()
            done[action] = "ok"
        except Exception as e:  # noqa: BLE001 - the video is already up; report and continue
            done[action] = f"failed: {e}"
            print(f"{action} failed (video is uploaded): {e}")
        record.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
