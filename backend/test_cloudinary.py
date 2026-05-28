import os
import sys
import cloudinary
import cloudinary.api
from core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

for r_type in ["video", "raw"]:
    print(f"Scanning {r_type}...")
    try:
        response = cloudinary.api.resources(
            resource_type=r_type,
            type="upload",
            max_results=500,
            prefix="songs/"
        )
        resources = response.get("resources", [])
        for r in resources:
            print(f"[{r_type}] {r['public_id']}")
    except Exception as e:
        print(f"Error {r_type}: {e}")
