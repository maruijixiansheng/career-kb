"""测试简历解析器"""

import os
import tempfile
import pytest
from app.utils.parser import (
    parse_text,
    parse_markdown,
    ResumeParseResult,
    reconstruct_reading_order,
)


class TestParseText:
    """纯文本解析测试"""

    def test_basic_parsing(self):
        text = "姓名: 张三\n电话: 13800138000\n工作经历: 字节跳动"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(text)
            temp_path = f.name

        try:
            result = parse_text(temp_path)
            assert isinstance(result, ResumeParseResult)
            assert result.source_format == "txt"
            assert "张三" in result.raw_text
            assert "字节跳动" in result.raw_text
        finally:
            os.unlink(temp_path)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("")
            temp_path = f.name

        try:
            result = parse_text(temp_path)
            assert result.raw_text == ""
        finally:
            os.unlink(temp_path)

    def test_filename_retained(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("test")
            temp_path = f.name

        try:
            result = parse_text(temp_path)
            assert result.source_filename.endswith(".txt")
        finally:
            os.unlink(temp_path)

    def test_resume_parse_result_repr(self):
        result = ResumeParseResult(
            raw_text="测试内容",
            source_format="txt",
            source_filename="resume.txt",
        )
        repr_str = repr(result)
        assert "txt" in repr_str
        assert "chars" in repr_str


class TestParseMarkdown:
    """Markdown 解析测试"""

    def test_basic_markdown(self):
        text = "# 张三\n\n## 工作经历\n\n- 字节跳动\n- 阿里巴巴"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(text)
            temp_path = f.name

        try:
            result = parse_markdown(temp_path)
            assert result.source_format == "md"
            assert len(result.paragraphs) > 0
            # 第一行是标题，应该有 is_heading=True
            assert result.paragraphs[0]["is_heading"] is True
            assert "张三" in result.paragraphs[0]["text"]
        finally:
            os.unlink(temp_path)

    def test_heading_detection(self):
        text = "# 一级标题\n## 二级标题\n普通文本"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(text)
            temp_path = f.name

        try:
            result = parse_markdown(temp_path)
            headings = [p for p in result.paragraphs if p["is_heading"]]
            assert len(headings) == 2
        finally:
            os.unlink(temp_path)


class TestReconstructReadingOrder:
    """阅读顺序重建测试"""

    def test_already_ordered(self):
        paras = [
            {"text": "第一行", "y0": 0, "x0": 0},
            {"text": "第二行", "y0": 20, "x0": 0},
            {"text": "第三行", "y0": 40, "x0": 0},
        ]
        ordered = reconstruct_reading_order(paras)
        assert ordered[0]["text"] == "第一行"
        assert ordered[2]["text"] == "第三行"

    def test_same_line_reorder(self):
        """同一行内的元素按 x 坐标重排"""
        paras = [
            {"text": "右边", "y0": 10, "x0": 200},
            {"text": "左边", "y0": 10, "x0": 10},
        ]
        ordered = reconstruct_reading_order(paras)
        assert ordered[0]["text"] == "左边"
        assert ordered[1]["text"] == "右边"

    def test_no_coordinates(self):
        """没有坐标信息的段落保持原样"""
        paras = [
            {"text": "段落1"},
            {"text": "段落2"},
        ]
        ordered = reconstruct_reading_order(paras)
        assert len(ordered) == 2

    def test_empty_list(self):
        ordered = reconstruct_reading_order([])
        assert len(ordered) == 0

    def test_multi_page(self):
        """多页文档按页码排序"""
        paras = [
            {"text": "第二页", "y0": 0, "x0": 0, "page": 1},
            {"text": "第一页", "y0": 0, "x0": 0, "page": 0},
        ]
        ordered = reconstruct_reading_order(paras)
        assert ordered[0]["text"] == "第一页"
        assert ordered[1]["text"] == "第二页"
