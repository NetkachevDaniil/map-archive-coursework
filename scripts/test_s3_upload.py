from app.services.parser_service import _download_bytes
from app.services.storage_service import storage_service

url = "https://raw.githubusercontent.com/efradkin/o-maps/main/maps/moscow/lr/novokosino_2025.webp"
data = _download_bytes(url)
print("downloaded", len(data))
key = storage_service.upload_bytes(data, "novokosino_2025.webp")
print("key", key)

gif_url = "https://o-maps.spb.ru/original_maps/moscow/ak/electrogorsk_rogaine_2025_omaps.gif"
gif_data = _download_bytes(gif_url)
print("gif downloaded", len(gif_data))
key2 = storage_service.upload_bytes(gif_data, "test.gif")
print("gif key", key2)
