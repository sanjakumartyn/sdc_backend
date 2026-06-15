import os
import httpx
from typing import List, Tuple, Any, Dict

OCR_BASE_URL = os.getenv("OCR_SERVICE_URL", "https://semisweet-craziness-dreamless.ngrok-free.dev")

class OCRService:
    @staticmethod
    async def extract_from_url(url: str) -> Dict[str, Any]:
        """Send a JSON payload with a document URL to the external OCR service.
        Returns the JSON response from the OCR service.
        """
        endpoint = f"{OCR_BASE_URL}/extract"
        async with httpx.AsyncClient() as client:
            response = await client.post(endpoint, json={"url": url})
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def extract_from_files(files: List[Tuple[str, Tuple[str, bytes, str]]]) -> Dict[str, Any]:
        """Send multipart files to the external OCR service.
        `files` is a list of tuples: (field_name, (filename, file_bytes, content_type)).
        The external OCR expects the field name `file` (or `files`).
        """
        endpoint = f"{OCR_BASE_URL}/extract/documents"
        multipart_data = {}
        # Build multipart payload respecting field names
        for idx, (field_name, (filename, content, content_type)) in enumerate(files):
            # httpx expects (field_name, (filename, file_bytes, content_type))
            multipart_data[field_name] = (filename, content, content_type)
        async with httpx.AsyncClient() as client:
            response = await client.post(endpoint, files=multipart_data)
            response.raise_for_status()
            return response.json()
