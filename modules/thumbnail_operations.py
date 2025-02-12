import os
from PIL import Image
import requests
from urllib.parse import urlparse

from modules.constants import THUMBNAIL_CACHE_DIR

def ensure_thumbnail_cache_dir():
    if not os.path.exists(THUMBNAIL_CACHE_DIR):
        os.makedirs(THUMBNAIL_CACHE_DIR)

def get_cached_thumbnail_path(thumbnail_url):
    ensure_thumbnail_cache_dir()
    parsed_url = urlparse(thumbnail_url)
    filename = os.path.basename(parsed_url.path)
    return os.path.join(THUMBNAIL_CACHE_DIR, filename)

def fetch_thumbnail(thumbnail_url):
    cache_path = get_cached_thumbnail_path(thumbnail_url)
    if os.path.exists(cache_path):
        return Image.open(cache_path)
    
    try:
        response = requests.get(thumbnail_url, stream=True)
        if response.status_code == 200:
            with open(cache_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return Image.open(cache_path)
        else:
            print(f"Failed to fetch thumbnail. Status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
    return None