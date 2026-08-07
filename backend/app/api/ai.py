"""AI 辅助录入 API — 公司/岗位补全，OCR，语音转文字"""

from fastapi import APIRouter, Depends, HTTPException

from ..core.deps import get_current_user
from ..models.user import User
from ..schemas import (
    CompanyAutocompleteRequest,
    CompanyAutocompleteResponse,
    PositionAutocompleteRequest,
    PositionAutocompleteResponse,
    OCRRequest,
    OCRResponse,
    STTRequest,
    STTResponse,
)
from ..core.ai_assistant import ai_assistant

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/company-autocomplete", response_model=CompanyAutocompleteResponse)
async def company_autocomplete(
    request: CompanyAutocompleteRequest,
    current_user: User = Depends(get_current_user),
):
    """公司名称 → AI 补全行业/规模/简介"""
    try:
        result = await ai_assistant.autocomplete_company(request.company_name)
        return CompanyAutocompleteResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"补全失败: {str(e)}")


@router.post("/position-autocomplete", response_model=PositionAutocompleteResponse)
async def position_autocomplete(
    request: PositionAutocompleteRequest,
    current_user: User = Depends(get_current_user),
):
    """岗位名称 → AI 补全技能/职责/薪资"""
    try:
        result = await ai_assistant.autocomplete_position(
            request.position_name,
            industry=request.industry,
        )
        return PositionAutocompleteResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"补全失败: {str(e)}")


@router.post("/ocr-jd", response_model=OCRResponse)
async def ocr_jd(
    request: OCRRequest,
    current_user: User = Depends(get_current_user),
):
    """JD 截图 → OCR 识别文字"""
    try:
        result = await ai_assistant.ocr_jd(request.image_base64)
        return OCRResponse(**result)
    except Exception as e:
        return OCRResponse(success=False, error=str(e))


@router.post("/speech-to-text", response_model=STTResponse)
async def speech_to_text(
    request: STTRequest,
    current_user: User = Depends(get_current_user),
):
    """语音 → 文字"""
    try:
        result = await ai_assistant.speech_to_text(request.audio_base64)
        return STTResponse(**result)
    except Exception as e:
        return STTResponse(success=False, error=str(e))
