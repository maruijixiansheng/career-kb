"""PDF 生成引擎 — 复用专业排版 HTML → WeasyPrint PDF

流程:
1. 通过 resume_template.generate_resume_html() 生成与预览一致的专业排版 HTML
2. 渲染-测量-回缩循环：内容溢出且第二页不足半页时，逐级降字号回缩到一页
3. WeasyPrint 渲染为 PDF（保留颜色、侧边栏、证件照）
"""

import re
import logging
from typing import Callable, Optional

from ..config import settings

logger = logging.getLogger(__name__)

# A4 高度（CSS px，96dpi）；WeasyPrint 中 297mm = 1122.52px
_A4_HEIGHT_PX = 1122.52
# 半页阈值：第二页内容不足半页才尝试回缩
_HALF_PAGE_PX = _A4_HEIGHT_PX / 2
# 回缩循环参数：每次字号 -2%，最多 -25%
# 下限 -25% 是为了覆盖「整段个人总结被 page-break-inside:avoid 推到第二页」这类
# 真实溢出（常见 150~250px），而 -15% 只能回缩 ~100px，不足以把总结拉回第一页。
_SHRINK_STEP = 0.02
_SHRINK_FLOOR = 0.75


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

        def make_html(scale: float) -> str:
            return generate_resume_html(
                content=markdown,
                photo_path=photo_path,
                structured_data=structured_data,
                scale=scale,
            )

        # 1. 渲染-测量-回缩循环，得到合适的字号比例
        scale = self._resolve_scale(make_html)
        if scale != 1.0:
            logger.info(f"简历内容溢出，字号回缩到 {scale:.0%} 以贴合单页 A4")

        # 2. 使用与预览完全相同的 HTML 模板（保留颜色、侧边栏、证件照）
        html = make_html(scale)

        # 3. WeasyPrint 渲染 HTML → PDF
        return self._render_pdf(html)

    def _resolve_scale(self, make_html: Callable[[float], str]) -> float:
        """测量溢出并决定回缩字号比例，返回 1.0 表示无需回缩。

        规则（需求）：
        - 内容在一页内 → 不做任何处理
        - 恰好两页，且第二页内容不足半页 → 逐级降字号回缩到一页
        - 第二页超过半页，或超过两页 → 保持原样（允许两页）
        """
        from weasyprint import HTML

        def measure(scale: float):
            # 剥离 min-height 再测量：否则 min-height 会作用到每个分页片段，
            # 把第二页撑满到 297mm，导致溢出高度无法被准确读出。
            html = self._strip_min_height(make_html(scale))
            doc = HTML(string=html).render()
            return doc.pages

        try:
            pages = measure(1.0)
        except Exception as e:
            # 测量失败（如环境缺字体/库）不应阻断生成，回退为不缩放
            logger.warning(f"回缩测量失败，跳过回缩: {e}")
            return 1.0

        if len(pages) <= 1:
            return 1.0  # 一页内，无需回缩
        if len(pages) > 2:
            return 1.0  # 超过两页，内容过多，不做回缩

        # 恰好两页：测量第二页实际内容高度
        overflow_px = self._page_content_height(pages[1])
        if overflow_px >= _HALF_PAGE_PX:
            return 1.0  # 第二页超过半页，允许两页

        # 第二页不足半页 → 逐级回缩，直到收敛到一页或触及下限
        scale = 1.0 - _SHRINK_STEP
        while scale >= _SHRINK_FLOOR - 1e-9:
            try:
                pages = measure(scale)
            except Exception as e:
                logger.warning(f"回缩测量失败（scale={scale:.0%}），中止: {e}")
                break
            if len(pages) == 1:
                return scale
            scale = round(scale - _SHRINK_STEP, 4)

        # 回缩到底仍无法一页 → 保持原始字号（放弃回缩，接受两页）
        return 1.0

    @staticmethod
    def _strip_min_height(html: str) -> str:
        """剥离 min-height: 297mm（仅用于测量自然内容高度）"""
        return re.sub(r'min-height:\s*297mm', 'min-height: 0', html)

    @staticmethod
    def _page_content_height(page) -> float:
        """返回某页内容块的最大底部坐标（CSS px）"""
        page_box = page._page_box
        if not page_box.children:
            return 0.0
        return max(
            (getattr(child, 'position_y', 0.0) + child.margin_height()
             for child in page_box.children),
            default=0.0,
        )

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
