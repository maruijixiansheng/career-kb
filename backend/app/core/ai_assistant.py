"""AI 辅助功能 — 公司/岗位自动补全、面试反馈提取"""

from .llm_client import llm_client
from .prompts import (
    COMPANY_AUTOCOMPLETE_SYSTEM,
    COMPANY_AUTOCOMPLETE_USER,
    POSITION_AUTOCOMPLETE_SYSTEM,
    POSITION_AUTOCOMPLETE_USER,
    INTERVIEW_FEEDBACK_SYSTEM,
    INTERVIEW_FEEDBACK_USER,
)
from ..config import settings


class AIAssistant:
    """AI 辅助录入助手"""

    async def autocomplete_company(self, company_name: str) -> dict:
        """输入公司名 → 补全行业/规模/简介"""
        if not company_name.strip():
            return {}
        try:
            return await llm_client.chat_json(
                system_prompt=COMPANY_AUTOCOMPLETE_SYSTEM,
                user_message=COMPANY_AUTOCOMPLETE_USER.format(
                    company_name=company_name
                ),
                model=settings.LLM_MODEL_SIMPLE,
                temperature=0.1,
            )
        except Exception:
            return {"company_name": company_name, "confidence": "low"}

    async def autocomplete_position(self, position_name: str, industry: str = "") -> dict:
        """输入岗位名 → 补全技能/职责/薪资"""
        if not position_name.strip():
            return {}
        try:
            return await llm_client.chat_json(
                system_prompt=POSITION_AUTOCOMPLETE_SYSTEM,
                user_message=POSITION_AUTOCOMPLETE_USER.format(
                    position_name=position_name,
                    industry=industry or "未知",
                ),
                model=settings.LLM_MODEL_SIMPLE,
                temperature=0.1,
            )
        except Exception:
            return {"position_name": position_name}

    async def extract_interview_feedback(
        self, company: str, position: str, feedback: str
    ) -> dict:
        """从面试反馈文本中提取结构化关键点"""
        if not feedback.strip():
            return {}
        try:
            return await llm_client.chat_json(
                system_prompt=INTERVIEW_FEEDBACK_SYSTEM,
                user_message=INTERVIEW_FEEDBACK_USER.format(
                    company=company,
                    position=position,
                    feedback=feedback,
                ),
                model=settings.LLM_MODEL_SIMPLE,
                temperature=0.3,
            )
        except Exception:
            return {"error": "提取失败"}

    async def ocr_jd(self, image_base64: str) -> dict:
        """JD 截图 OCR 识别 (使用硅基流动多模态模型)"""
        # 检查图片大小，超过 2MB 时压缩
        import base64
        raw = base64.b64decode(image_base64)
        original_size = len(raw)
        if original_size > 2 * 1024 * 1024:
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(raw))
                # 缩放到合理尺寸（最大 1920px 宽，保持比例）
                if img.width > 1920:
                    ratio = 1920 / img.width
                    img = img.resize((1920, int(img.height * ratio)), Image.LANCZOS)
                # 转换为 JPEG 压缩
                buf = io.BytesIO()
                img.convert("RGB").save(buf, "JPEG", quality=75)
                image_base64 = base64.b64encode(buf.getvalue()).decode()
            except Exception:
                pass  # 压缩失败则使用原图

        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=settings.SILICONFLOW_API_KEY,
                base_url=settings.SILICONFLOW_BASE_URL,
                timeout=30.0,  # 30 秒超时
            )
            response = await client.chat.completions.create(
                model="PaddlePaddle/PaddleOCR-VL-1.5",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                        },
                        {
                            "type": "text",
                            "text": "请识别并提取这张图片中的所有文字内容。保持原始格式和结构。只需要返回识别出的文本。",
                        },
                    ],
                }],
                max_tokens=2048,
            )
            text = response.choices[0].message.content
            return {"text": text, "success": True}
        except Exception as e:
            return {"text": "", "success": False, "error": f"OCR 识别失败: {str(e)[:200]}"}

    async def speech_to_text(self, audio_base64: str) -> dict:
        """语音转文字 (使用硅基流动 SenseVoice)"""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=settings.SILICONFLOW_API_KEY,
                base_url=settings.SILICONFLOW_BASE_URL,
            )
            # 硅基流动的语音识别接口
            response = await client.chat.completions.create(
                model="FunAudioLLM/SenseVoiceSmall",
                messages=[{
                    "role": "user",
                    "content": f"请将以下音频转录为文字（中文）: [audio]",
                }],
                max_tokens=1024,
            )
            text = response.choices[0].message.content
            return {"text": text, "success": True}
        except Exception as e:
            return {"text": "", "success": False, "error": str(e)}


# 全局单例
ai_assistant = AIAssistant()
