from typing import Dict, Any
from ninja import Router
from .schemas import ExtractRequestSchema
from .service import OCRService

router = Router()

@router.post("/extract", response={200: Dict[str, Any]})
async def extract(request, payload: ExtractRequestSchema):
    """Forward a JSON payload containing a public URL to the external OCR service.
    Returns the OCR service JSON response directly.
    """
    result = await OCRService.extract_from_url(payload.url)
    return result

@router.post("/extract/documents", response={200: Dict[str, Any]})
async def extract_documents(request):
    """Accept multipart file upload(s) and forward them to the external OCR service.
    The OCR service expects the field name `file` (or `files`). All received files are passed through.
    """
    # Collect uploaded files from the request
    uploaded_files = []
    # Ninja exposes files via request.FILES
    for key in request.FILES:
        for uploaded in request.FILES.getlist(key):
            # uploaded is an UploadedFile instance
            uploaded_files.append((key, (uploaded.name, uploaded.read(), uploaded.content_type)))
    result = await OCRService.extract_from_files(uploaded_files)
    return result
