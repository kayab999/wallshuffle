import gi
from gi.repository import GIRepository

print(f"Search paths: {GIRepository.Repository.get_search_path()}")

try:
    gi.require_version("AppIndicator3", "0.1")

    print("AppIndicator3 loaded successfully")
except Exception as e:
    print(f"Error loading AppIndicator3: {e}")
