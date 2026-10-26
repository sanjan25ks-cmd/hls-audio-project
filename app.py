import os
import json
import uuid
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
STREAM_DIR = os.path.join(BASE_DIR, "streams")
ALLOWED = {"mp3", "wav", "m4a", "aac", "ogg", "flac"}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(STREAM_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB limit


def segment_audio(src_path, out_dir, seg_time):
    """Cut the audio into small .ts pieces and create index.m3u8"""
    cmd = [
        "ffmpeg", "-y", "-i", src_path,
        "-vn",                       # ignore any video/cover art
        "-c:a", "aac", "-b:a", "128k",
        "-f", "hls",
        "-hls_time", str(seg_time),  # length of each piece in seconds
        "-hls_playlist_type", "vod",
        "-hls_segment_filename", os.path.join(out_dir, "seg_%03d.ts"),
        os.path.join(out_dir, "index.m3u8"),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


@app.route("/")
def home():
    return app.send_static_file("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    file = request.files.get("audio")
    if not file or file.filename == "":
        return jsonify(error="No file selected"), 400

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return jsonify(error="Only mp3, wav, m4a, aac, ogg, flac allowed"), 400

    try:
        seg_time = int(request.form.get("segment_time", 10))
    except ValueError:
        seg_time = 10
    seg_time = max(2, min(seg_time, 30))

    track_id = uuid.uuid4().hex[:8]
    safe_name = secure_filename(file.filename)
    src_path = os.path.join(UPLOAD_DIR, f"{track_id}_{safe_name}")
    out_dir = os.path.join(STREAM_DIR, track_id)
    os.makedirs(out_dir, exist_ok=True)
    file.save(src_path)

    try:
        segment_audio(src_path, out_dir, seg_time)
    except FileNotFoundError:
        return jsonify(error="FFmpeg not found. Install it and restart VS Code."), 500
    except subprocess.CalledProcessError:
        return jsonify(error="FFmpeg could not process this file."), 500

    segments = len([f for f in os.listdir(out_dir) if f.endswith(".ts")])
    meta = {
        "id": track_id,
        "title": os.path.splitext(safe_name)[0],
        "segments": segments,
        "segment_time": seg_time,
        "url": f"/streams/{track_id}/index.m3u8",
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f)

    return jsonify(meta)


@app.route("/api/tracks")
def tracks():
    items = []
    for name in os.listdir(STREAM_DIR):
        meta_file = os.path.join(STREAM_DIR, name, "meta.json")
        if os.path.exists(meta_file):
            with open(meta_file) as f:
                items.append(json.load(f))
    return jsonify(items)


@app.route("/streams/<track_id>/<path:filename>")
def serve_stream(track_id, filename):
    return send_from_directory(os.path.join(STREAM_DIR, track_id), filename)


if __name__ == "__main__":
    app.run(debug=True, port=5000)