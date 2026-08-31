### JellyFetch 0.1.0
A feature-rich command-line media downloader and web dashboard
`docker compose up -d` Copy Docker instructions

* [Description](#description)
* [Dependencies](#dependencies)
* [Installation](#installation)
* [Usage and Dashboard](#usage-and-dashboard)
* [Configuration](#configuration)
* [Extracted Metadata](#extracted-metadata)
* [Examples](#examples)
* [Maintenance and Cache](#maintenance-and-cache)

Official repository: https://github.com/fbellegarde/jellyfetch

JellyFetch is a feature-rich, full-stack media acquisition platform. Built as a custom wrapper around yt-dlp—a feature-rich command-line audio/video downloader with support for thousands of sites—it provides a highly robust terminal CLI alongside a premium, single-page web dashboard. It automatically routes downloaded media (Movies, TV, Music, Social Clips) into your host file system and triggers library syncs across Jellyfin and Navidrome.

**Important**: Any user experiencing an issue with downloads or signature extraction should flush the system cache via the Web UI before submitting a bug report.

---

### DEPENDENCIES
Python versions 3.10+ (CPython) are supported. While some dependencies are optional for basic yt-dlp usage, the following are heavily utilized by the JellyFetch Docker container:

#### Strongly recommended
* **ffmpeg and ffprobe** - Required for merging separate video and audio files, as well as for various post-processing tasks.
* **yt-dlp-ejs** - Required for full YouTube support. Licensed under Unlicense, bundles MIT and ISC components.
* **deno** - A JavaScript runtime/engine recommended to run yt-dlp-ejs.

---

### INSTALLATION

**Docker Deployment (Recommended)**
JellyFetch is designed to run in an isolated container while securely mounting your host media drives.
```bash
git clone [https://github.com/fbellegarde/jellyfetch.git](https://github.com/fbellegarde/jellyfetch.git) && cd jellyfetch
cp web/.env.example web/.env
docker compose up --build -d
Local Development (WSL/Linux)Bashsource venv/bin/activate
pip install -e .
python web/server.py
USAGE AND DASHBOARDWeb Interface OptionsThe JellyFetch web dashboard is accessible by default at http://127.0.0.1:5547 and operates as a fully dynamic Single Page Application (SPA).Universal Drag-and-Drop: Drag any URL from your browser directly onto the UI window to instantly trigger the Metadata Inspector.Metadata Inspector: Previews the thumbnail, uploader, exact duration, and description parsed from the internal extraction dictionary before downloading.Hardware Audio Visualizer: The media player features a real-time HTML5 Canvas waveform visualizer that reacts to streaming media frequencies.Play Queue & Multi-Select: Add media to your queue for automatic transitions, or use Shift+Click in Table View for bulk queueing and deletion.Picture-in-Picture (PiP): Float the video player on top of your OS desktop using the native browser PiP API.CLI OptionsJellyFetch exposes the download command globally to your terminal, allowing you to pass explicit formats.Plaintext-h, --help                      Print this help text and exit
auto                            (Default) Analyzes the URL and metadata to automatically 
                                route files to the correct host directory.
mp3                             Convert video files to audio-only files[cite: 5].
                                Forces 192kbps audio extraction.
mkv                             Remux the video into another container[cite: 5].
                                Forces merging the best video and audio into an MKV container.
all                             Archives all available formats.
CONFIGURATIONConfigure JellyFetch by modifying the .env file in the /web directory. If you alter your configuration or core files, run docker compose up --build -d to rebuild the container.VariableCategoryDefault ValueDescriptionHOSTServer0.0.0.0The binding address.PORTServer5547The port the Flask API and Web UI run on.FLASK_DEBUGServerFalseSet to True for hot-reloading during development.APP_NAMEBrandingJellyFetchAlters the text in the top-left sidebar.THEME_PRIMARYBranding#a855f7Hex code for the primary accent color.MAX_GRID_ITEMSBranding500Limits the maximum files parsed per directory to prevent DOM lag.PATH_MOVIESMounts/mnt/e/.../MoviesThe internal path where your host movie drive is mounted.PATH_TVMounts/mnt/e/.../TV ShowsThe internal path where your host TV drive is mounted.PATH_MUSICMounts/mnt/e/.../MusicThe internal path where your host music drive is mounted.PATH_SOCIALMounts/mnt/e/.../ClipsThe internal path where your host social clips drive is mounted.JELLYFIN_URLIntegrationshttp://...Your local Jellyfin instance address.JELLYFIN_API_KEYIntegrationsNoneGenerate this in Jellyfin to sync via the Web UI.NAVIDROME_URLIntegrationshttp://...Your local Navidrome instance address.EXTRACTED METADATAJellyFetch extracts metadata and saves it as .info.json files. The UI parses these files to display detailed information. The following fields are actively extracted and utilized:is_live (boolean): Whether this video is a live stream or a fixed-length video[cite: 5].duration (numeric): Length of the video[cite: 5].extractor (string): Name of the extractor[cite: 5].playlist_id (string): Identifier of the playlist that contains the video[cite: 5].playlist_title (string): Name of the playlist that contains the video[cite: 5].playlist_count (numeric): Total number of items in the playlist. May not be known if entire playlist is not extracted[cite: 5].EXAMPLESBash# Boot the isolated JellyFetch container in detached mode
$ docker compose up --build -d

# Download and route a standard video via CLI
$ download [https://www.youtube.com/watch?v=](https://www.youtube.com/watch?v=)...

# Download the best format that contains video,
# and if it doesn't already have an audio stream, merge it with best audio-only format[cite: 5].
$ download mkv [https://www.youtube.com/watch?v=](https://www.youtube.com/watch?v=)...

# Download best video available via direct link over HTTP/HTTPS protocol,
# or the best video available via any protocol if there is no such video[cite: 5].
$ download auto [https://www.youtube.com/watch?v=](https://www.youtube.com/watch?v=)...
MAINTENANCE AND CACHERebuilding: If you modify server.py, index.html, or alter your .env configuration, you must rebuild the Docker container (docker compose up --build -d) to apply the changes.System Cache: To maintain optimal extraction speeds and bypass stale signatures, yt-dlp utilizes a local cache. If downloads fail due to signature errors, navigate to the System Settings tab in the Web UI and click Flush Cache to instantly clear the internal cache safely without restarting the container.