"""专业课程渲染测试：个人信息 → 简历左侧栏"""
from app.core.resume_template import _render_courses, generate_resume_html

CONTENT = """# 张三

zhangsan@example.com | 13800000000 | 杭州

## 求职意向
AI 应用开发

## 教育背景
本科 | 某大学 | 人工智能

## 专业课程
数据结构、操作系统、计算机网络
机器学习, 深度学习; 自然语言处理

【项目经历】
测试项目｜2026-01
技术栈：Python
"""


def test_render_courses_splits_on_mixed_separators():
    html = _render_courses("数据结构、操作系统,计算机网络;机器学习\n深度学习")
    assert html.count('class="course-tag"') == 5
    for name in ("数据结构", "操作系统", "计算机网络", "机器学习", "深度学习"):
        assert name in html


def test_render_courses_empty():
    assert _render_courses("") == ""
    assert _render_courses(" 、,; ") == ""


def test_courses_render_in_sidebar():
    html = generate_resume_html(content=CONTENT)
    sidebar, _, main = html.partition('<div class="main">')

    assert "专业课程" in sidebar          # 出现在左侧栏
    assert "course-tag" in sidebar
    assert "机器学习" in sidebar
    assert "专业课程" not in main         # 左右不重复
