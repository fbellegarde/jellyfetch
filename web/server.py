import os
import sys
import shutil
import threading
import logging
import re
import uuid
import json
import urllib.request
import platform
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file, Response
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# INITIALIZATION & ENVIRONMENT
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("JellyFetchServer")

app = Flask(__name__, static_folder='.')

START_TIME = time.time()
PORT = int(os.getenv("PORT", 5547))
HOST = os.getenv("HOST", "0.0.0.0")
APP_NAME = os.getenv("APP_NAME", "JellyFetch")
MAX_ITEMS = int(os.getenv("MAX_GRID_ITEMS", 500))

JELLYFIN_URL = os.getenv("JELLYFIN_URL", "http://127.0.0.1:8096").rstrip("/")
JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY", "")
NAVIDROME_URL = os.getenv("NAVIDROME_URL", "Not Configured").rstrip("/")

PATHS = {
    "movies": os.getenv("PATH_MOVIES"),
    "tv": os.getenv("PATH_TV"),
    "music": os.getenv("PATH_MUSIC"),
    "social": os.getenv("PATH_SOCIAL"),
}

active_downloads = {}
download_lock = threading.Lock()

# Import yt-dlp natively
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from yt_dlp import YoutubeDL
import yt_dlp.version
from jellyfetch.fetcher import determine_save_path

# ---------------------------------------------------------------------------
# UTILITIES & STREAMING SUPPORT
# ---------------------------------------------------------------------------
def get_dir_size(path: str) -> float:
    total_size = 0
    p = Path(path)
    if p.exists():
        for f in p.rglob('*'):
            if f.is_file():
                try:
                    total_size += f.stat().st_size
                except OSError:
                    pass
    return round(total_size / (1024 * 1024), 2)

def find_thumbnail(directory: Path, base_name: str) -> str:
    for ext in ['.webp', '.jpg', '.jpeg', '.png']:
        thumb_path = directory / f"{base_name}{ext}"
        if thumb_path.exists():
            return thumb_path.name
    return None

def partial_response(path, start, end=None):
    file_size = os.path.getsize(path)
    if end is None:
        end = file_size - 1
    end = min(end, file_size - 1)
    length = end - start + 1

    with open(path, 'rb') as f:
        f.seek(start)
        data = f.read(length)

    ext = Path(path).suffix.lower()
    mime_types = {
        '.mp4': 'video/mp4', '.mkv': 'video/x-matroska', '.webm': 'video/webm',
        '.mp3': 'audio/mpeg', '.flac': 'audio/flac', '.wav': 'audio/wav',
        '.m4a': 'audio/mp4', '.opus': 'audio/opus', '.aac': 'audio/aac'
    }
    content_type = mime_types.get(ext, 'application/octet-stream')

    rv = Response(data, 206, mimetype=content_type, direct_passthrough=True)
    rv.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
    rv.headers.add('Accept-Ranges', 'bytes')
    rv.headers.add('Content-Length', str(length))
    return rv

# ---------------------------------------------------------------------------
# REAL YT-DLP EXECUTION WITH PROGRESS HOOK
# ---------------------------------------------------------------------------
def run_monitored_download(task_id: str, url: str, req_format: str):
    def progress_hook(d):
        with download_lock:
            if task_id not in active_downloads:
                return
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed', 0) or 0
                eta = d.get('eta', 0) or 0
                percent = round((downloaded / total * 100), 1) if total > 0 else 0
                
                active_downloads[task_id].update({
                    "status": "downloading",
                    "percent": percent,
                    "downloaded_mb": round(downloaded / (1024*1024), 2),
                    "total_mb": round(total / (1024*1024), 2),
                    "speed_mb": round(speed / (1024*1024), 2),
                    "eta": eta
                })
            elif d['status'] == 'finished':
                active_downloads[task_id].update({
                    "status": "processing",
                    "percent": 99.0
                })

    try:
        with YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            
        target_dir = determine_save_path(url, info)
        
        ydl_opts = {
            'paths': {'home': target_dir},
            'postprocessors': [{'key': 'FFmpegMetadata'}, {'key': 'EmbedThumbnail'}],
            'writethumbnail': True,
            'writeinfojson': True,
            'clean_infojson': True,
            'progress_hooks': [progress_hook],
        }

        if req_format in ['mp3', 'flac', 'wav', 'm4a', 'opus', 'aac']:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'].insert(0, {'key': 'FFmpegExtractAudio', 'preferredcodec': req_format})
            if "Music" in target_dir:
                ydl_opts['outtmpl'] = '%(artist|Unknown Artist)s/%(album|Unknown Album)s/%(title)s [%(id)s].%(ext)s'
            else:
                ydl_opts['outtmpl'] = '%(title)s [%(id)s].%(ext)s'
        elif req_format in ['mp4', 'mkv', 'webm', 'mov']:
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
            ydl_opts['merge_output_format'] = req_format
            ydl_opts['outtmpl'] = '%(title)s [%(id)s].%(ext)s'
        elif req_format == "all":
            ydl_opts['format'] = 'all'
            ydl_opts['outtmpl'] = '%(title)s.f%(format_id)s.%(ext)s'
        else:
            if "Music" in target_dir:
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'].insert(0, {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'})
                ydl_opts['outtmpl'] = '%(artist|Unknown Artist)s/%(album|Unknown Album)s/%(title)s [%(id)s].%(ext)s'
            else:
                ydl_opts['format'] = 'bestvideo+bestaudio/best'
                ydl_opts['outtmpl'] = '%(title)s [%(id)s].%(ext)s'

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        with download_lock:
            active_downloads[task_id]["status"] = "completed"
            active_downloads[task_id]["percent"] = 100.0

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        with download_lock:
            active_downloads[task_id]["status"] = "failed"
            active_downloads[task_id]["error"] = str(e)

# ---------------------------------------------------------------------------
# API ROUTES
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/system', methods=['GET'])
def system_health():
    base_drive = PATHS.get("movies", "/")
    try:
        total, used, free = shutil.disk_usage(base_drive)
    except FileNotFoundError:
        total, used, free = (0, 0, 0)

    library_sizes = {k: get_dir_size(v) if v else 0 for k, v in PATHS.items()}

    with download_lock:
        downloads_list = list(active_downloads.values())

    return jsonify({
        "app_name": APP_NAME,
        "port": PORT,
        "paths": PATHS,
        "storage": {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "usage_percent": round((used / total) * 100, 1) if total > 0 else 0
        },
        "library_sizes_mb": library_sizes,
        "active_downloads": downloads_list,
        "engine": {
            "yt_dlp_version": yt_dlp.version.__version__,
            "python_version": sys.version.split(' ')[0],
            "ffmpeg_installed": bool(shutil.which('ffmpeg')),
            "os": f"{platform.system()} {platform.release()}"
        },
        "integrations": {
            "jellyfin": JELLYFIN_URL,
            "navidrome": NAVIDROME_URL
        },
        "uptime_seconds": time.time() - START_TIME
    })

@app.route('/api/maintenance/clear-cache', methods=['POST'])
def clear_cache():
    """Flushes the yt-dlp local cache."""
    try:
        with YoutubeDL({'quiet': True}) as ydl:
            ydl.cache.remove()
        return jsonify({"status": "success", "message": "Extraction signature cache flushed."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/inspect', methods=['POST'])
def inspect_url():
    url = request.json.get('url')
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        with YoutubeDL({'quiet': True, 'skip_download': True, 'extract_flat': 'in_playlist'}) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if 'entries' in info:
                entries = list(info['entries'])
                return jsonify({
                    "title": info.get('title', 'Playlist'),
                    "uploader": info.get('uploader', 'Various'),
                    "duration": sum([e.get('duration', 0) for e in entries if e]),
                    "thumbnail": info.get('thumbnail', ''),
                    "view_count": 0,
                    "description": f"Playlist containing {len(entries)} items.",
                    "is_playlist": True,
                    "item_count": len(entries)
                })
                
            return jsonify({
                "title": info.get('title', 'Unknown Title'),
                "uploader": info.get('uploader') or info.get('artist') or 'Unknown Uploader',
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', ''),
                "view_count": info.get('view_count', 0),
                "description": (info.get('description') or '')[:200] + '...',
                "is_playlist": False
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/library/<category>', methods=['GET'])
def scan_library(category):
    if category not in PATHS or not PATHS[category]:
        return jsonify({"error": "Invalid category"}), 400
    
    dir_path = Path(PATHS[category])
    if not dir_path.exists():
        return jsonify([])

    media_extensions = {'.mp4', '.mkv', '.webm', '.mov', '.mp3', '.flac', '.wav', '.m4a', '.opus', '.aac'}
    files = []
    
    try:
        for f in dir_path.rglob('*'):
            if f.is_file() and f.suffix.lower() in media_extensions:
                stat = f.stat()
                thumb = find_thumbnail(f.parent, f.stem)
                rel_path = f.relative_to(dir_path).as_posix()
                
                info_json_path = f.parent / f"{f.stem}.info.json"
                metadata = {}
                if info_json_path.exists():
                    try:
                        with open(info_json_path, 'r', encoding='utf-8') as jf:
                            raw_meta = json.load(jf)
                            metadata['uploader'] = raw_meta.get('uploader') or raw_meta.get('artist')
                            metadata['view_count'] = raw_meta.get('view_count')
                            metadata['duration'] = raw_meta.get('duration')
                            metadata['description'] = raw_meta.get('description')
                    except Exception:
                        pass
                
                files.append({
                    "name": f.name,
                    "rel_path": rel_path,
                    "stem": f.stem,
                    "ext": f.suffix.lower(),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "timestamp": stat.st_mtime,
                    "has_thumbnail": bool(thumb),
                    "thumbnail_file": thumb,
                    "category": category,
                    "is_audio": f.suffix.lower() in {'.mp3', '.flac', '.wav', '.m4a', '.opus', '.aac'},
                    "metadata": metadata
                })
        
        files.sort(key=lambda x: x['timestamp'], reverse=True)
        return jsonify(files[:MAX_ITEMS])
    except Exception as e:
        logger.error(f"Scan error for {category}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stream/<category>/<path:filename>', methods=['GET'])
def stream_media(category, filename):
    if category not in PATHS or not PATHS[category]:
        return jsonify({"error": "Invalid category"}), 400
    
    file_path = (Path(PATHS[category]) / filename).resolve()
    if not file_path.exists() or not file_path.is_file():
        return jsonify({"error": "File not found"}), 404
        
    range_header = request.headers.get('Range', None)
    if not range_header:
        return send_file(file_path)

    size = os.path.getsize(file_path)
    byte1, byte2 = 0, None
    m = re.search(r'(\d+)-(\d*)', range_header)
    g = m.groups()
    if g[0]: byte1 = int(g[0])
    if g[1]: byte2 = int(g[1])
    return partial_response(file_path, byte1, byte2)

@app.route('/api/thumbnail/<category>/<filename>', methods=['GET'])
def serve_thumbnail(category, filename):
    if category not in PATHS or not PATHS[category]:
        return jsonify({"error": "Invalid category"}), 400
    safe_path = Path(PATHS[category]) / filename
    if safe_path.exists() and safe_path.is_file():
        return send_file(safe_path)
    return jsonify({"error": "Thumbnail not found"}), 404

@app.route('/api/download', methods=['POST'])
def trigger_download():
    data = request.json
    url = data.get('url')
    req_format = data.get('format', 'auto')
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    task_id = str(uuid.uuid4())[:8]
    with download_lock:
        active_downloads[task_id] = {
            "id": task_id,
            "url": url,
            "format": req_format,
            "status": "starting",
            "percent": 0.0,
            "downloaded_mb": 0,
            "total_mb": 0,
            "speed_mb": 0,
            "eta": 0,
            "error": None
        }

    thread = threading.Thread(target=run_monitored_download, args=(task_id, url, req_format))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "success", "task_id": task_id})

@app.route('/api/trigger-scan', methods=['POST'])
def trigger_jellyfin_scan():
    if not JELLYFIN_API_KEY:
        return jsonify({"error": "JELLYFIN_API_KEY not set in .env"}), 400
    try:
        req = urllib.request.Request(f"{JELLYFIN_URL}/Library/Refresh", method="POST")
        req.add_header("X-Emby-Token", JELLYFIN_API_KEY)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as res:
            return jsonify({"status": "success", "message": "Jellyfin library refresh triggered!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete', methods=['POST'])
def delete_media():
    data = request.json
    files_to_delete = data.get('files', [])
    
    if not files_to_delete:
        return jsonify({"error": "Invalid request"}), 400
        
    deleted_count = 0
    errors = []

    for item in files_to_delete:
        category = item.get('category')
        filename = item.get('filename')

        if not category or not filename or category not in PATHS:
            errors.append(f"Invalid category for {filename}")
            continue

        target_dir = Path(PATHS[category]).resolve()
        target_file = (target_dir / filename).resolve()
        
        if not target_file.is_relative_to(target_dir):
            errors.append(f"Path traversal prohibited for {filename}")
            continue
            
        if target_file.exists():
            try:
                target_file.unlink()
                thumb = find_thumbnail(target_file.parent, target_file.stem)
                if thumb: (target_file.parent / thumb).unlink()
                info_json = target_file.parent / f"{target_file.stem}.info.json"
                if info_json.exists(): info_json.unlink()
                
                deleted_count += 1
            except Exception as e:
                errors.append(str(e))
        else:
            errors.append(f"File not found: {filename}")

    if errors and deleted_count == 0:
        return jsonify({"error": " | ".join(errors)}), 500

    return jsonify({
        "status": "success", 
        "message": f"{deleted_count} file(s) deleted.", 
        "errors": errors
    })

if __name__ == '__main__':
    logger.info(f"Starting {APP_NAME} UI on port {PORT}")
    app.run(host=HOST, port=PORT, debug=(os.getenv("FLASK_DEBUG") == "True"))