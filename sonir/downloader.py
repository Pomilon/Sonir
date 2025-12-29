import os
import re
import hashlib
import yt_dlp
from .config import Config

class AudioDownloader:
    CACHE_DIR = "sonir_cache"

    @staticmethod
    def is_url(string):
        """Checks if the input string looks like a URL."""
        regex = re.compile(
            r'^(?:http|ftp)s?://' # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
            r'localhost|' # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
            r'(?::\d+)?' # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return re.match(regex, string) is not None

    @staticmethod
    def download(url):
        """
        Downloads audio from the URL using yt-dlp.
        Returns the path to the downloaded file.
        """
        if not os.path.exists(AudioDownloader.CACHE_DIR):
            os.makedirs(AudioDownloader.CACHE_DIR)

        # Create a hash of the URL to use as the filename (caching mechanism)
        url_hash = hashlib.md5(url.encode()).hexdigest()
        output_template = os.path.join(AudioDownloader.CACHE_DIR, f"{url_hash}.%(ext)s")
        
        # Check if we already have a file with this hash (ignoring extension)
        for f in os.listdir(AudioDownloader.CACHE_DIR):
            if f.startswith(url_hash):
                print(f"Using cached audio: {f}")
                return os.path.join(AudioDownloader.CACHE_DIR, f)

        print(f"Downloading audio from {url}...")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # FFmpeg conversion changes extension, so we need to find the actual file
                base, _ = os.path.splitext(filename)
                final_path = f"{base}.mp3"
                
                # Update config window title with video title if possible
                if 'title' in info:
                    print(f"Title: {info['title']}")
                
                return final_path
        except Exception as e:
            print(f"Download failed: {e}")
            return None
