"""PDF 生成引擎 — 复用专业排版 HTML → WeasyPrint PDF

流程:
1. 通过 resume_template.generate_resume_html() 生成与预览一致的专业排版 HTML
2. WeasyPrint 渲染为 PDF（保留颜色、侧边栏、证件照）
"""

import os
import logging
from pathlib import Path
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)


class PDFGenerator:
    """简历 PDF 生成器 — 与预览使用同一套 HTML 模板"""

    def generate(
        self,
        markdown: str,
        photo_path: Optional[str] = None,
        structured_data: Optional[dict] = None,
    ) -> bytes:
        """将 Markdown 简历渲染为专业排版 PDF

        Args:
            markdown: LLM 生成的 Markdown 简历
            photo_path: 证件照的绝对路径
            structured_data: LLM 结构化解析的简历 JSON（用于补充联系方式）

        Returns:
            PDF 文件的字节数据
        """
        from ..core.resume_template import generate_resume_html

        # 1. 使用与预览完全相同的 HTML 模板（保留颜色、侧边栏、证件照）
        html = generate_resume_html(
            content=markdown,
            photo_path=photo_path,
            structured_data=structured_data,
        )

        # 2. WeasyPrint 渲染 HTML → PDF
        pdf_bytes = self._render_pdf(html)

        return pdf_bytes

    def _render_pdf(self, html: str) -> bytes:
        """WeasyPrint 渲染 HTML 为 PDF"""
        from weasyprint import HTML

        try:
            doc = HTML(string=html)
            pdf_bytes = doc.write_pdf()
            return pdf_bytes
        except Exception as e:
            logger.error(f"WeasyPrint PDF 生成失败: {e}")
            raise RuntimeError(f"PDF 生成失败: {e}") from e


# 全局单例
pdf_generator = PDFGenerator()
