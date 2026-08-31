import os
import argparse
from yt_dlp import YoutubeDL

def determine_save_path(url, info):
    """Dynamically routes downloads based on metadata and environment variables."""
    movies_dir = os.getenv("PATH_MOVIES", "/mnt/e/Media/Jellyfin/Movies")
    tv_dir = os.getenv("PATH_TV", "/mnt/e/Media/Jellyfin/TV Shows")
    music_dir = os.getenv("PATH_MUSIC", "/mnt/e/Media/Music")
    social_dir = os.getenv("PATH_SOCIAL", "/mnt/e/Media/Jellyfin/YouTubeClips")
    
    url_lower = url.lower()
    
    # 1. Music Routing
    if "music.youtube.com" in url_lower or "soundcloud.com" in url_lower or info.get('artist'):
        return music_dir
    # 2. TV Series / Playlist Routing
    if info.get('series') or info.get('playlist'):
        return tv_dir
    # 3. Social Media & Clips
    if any(domain in url_lower for domain in ["tiktok.com", "twitter.com", "x.com", "instagram.com", "youtube.com", "youtu.be"]):
        return social_dir
    # 4. Movies Default Fallback
    return movies_dir

def get_media(url, requested_format="auto"):
    print(f"[JellyFetch] Inspecting metadata for {url}...")
    with YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        
    target_dir = determine_save_path(url, info)
    print(f"[JellyFetch] Routing to: {target_dir}")
    
    ydl_opts = {
        'paths': {'home': target_dir},
        'postprocessors': [{'key': 'FFmpegMetadata'}, {'key': 'EmbedThumbnail'}],
        'writethumbnail': True,
        'writeinfojson': True,
        'clean_infojson': True,
    }
    
    if requested_format in ['mp3', 'flac', 'wav', 'm4a', 'opus', 'aac']:
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'].insert(0, {'key': 'FFmpegExtractAudio', 'preferredcodec': requested_format})
        if "Music" in target_dir or target_dir == os.getenv("PATH_MUSIC"):
            ydl_opts['outtmpl'] = '%(artist|Unknown Artist)s/%(album|Unknown Album)s/%(title)s [%(id)s].%(ext)s'
        else:
            ydl_opts['outtmpl'] = '%(title)s [%(id)s].%(ext)s'
            
    elif requested_format in ['mp4', 'mkv', 'webm', 'mov']:
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
        ydl_opts['merge_output_format'] = requested_format
        ydl_opts['outtmpl'] = '%(title)s [%(id)s].%(ext)s'
        
    elif requested_format == "all":
        ydl_opts['format'] = 'all'
        ydl_opts['outtmpl'] = '%(title)s.f%(format_id)s.%(ext)s'
        
    else:
        if "Music" in target_dir or target_dir == os.getenv("PATH_MUSIC"):
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'].insert(0, {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'})
            ydl_opts['outtmpl'] = '%(artist|Unknown Artist)s/%(album|Unknown Album)s/%(title)s [%(id)s].%(ext)s'
        else:
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
            ydl_opts['outtmpl'] = '%(title)s [%(id)s].%(ext)s'

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def main():
    parser = argparse.ArgumentParser(description="JellyFetch Media Downloader")
    parser.add_argument("args", nargs="+", help="[format] URL or just URL")
    args = parser.parse_args().args
    
    if len(args) == 2:
        req_fmt = args[0].lower()
        url = args[1]
    elif len(args) == 1:
        req_fmt = "auto"
        url = args[0]
    else:
        print("Usage: download [format] <url>")
        return
        
    get_media(url, req_fmt)

if __name__ == "__main__":
    main()