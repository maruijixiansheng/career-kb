"""专业简历HTML模板生成器 — 含证件照，重组时自动填充"""

import base64
import os
import re
from pathlib import Path
from typing import Optional


def _photo_to_base64(photo_path: Optional[str]) -> Optional[str]:
    """将证件照转为 base64 嵌入HTML"""
    if not photo_path:
        return None
    # 规范化路径：处理 Windows 反斜杠、相对路径等情况
    normalized_path = os.path.normpath(photo_path)
    if not os.path.isabs(normalized_path):
        # 如果是相对路径，尝试基于 PHOTOS_DIR 解析
        from ..config import settings
        normalized_path = os.path.join(settings.PHOTOS_DIR, os.path.basename(normalized_path))

    # 尝试找到文件（可能因容器路径变化而不存在）
    candidates = [normalized_path]
    if not os.path.exists(normalized_path):
        import logging
        # 回退：尝试从 settings.PHOTOS_DIR 中寻找同名文件
        from ..config import settings
        fallback = os.path.join(settings.PHOTOS_DIR, os.path.basename(normalized_path))
        if fallback != normalized_path:
            candidates.append(fallback)
        # 也尝试 /app/data/photos/ (Docker 常见挂载点)
        docker_fallback = os.path.join("/app/data/photos", os.path.basename(normalized_path))
        if docker_fallback not in candidates:
            candidates.append(docker_fallback)

        found = None
        for c in candidates:
            if os.path.exists(c):
                found = c
                break

        if not found:
            logging.getLogger("career-kb").warning(
                f"证件照文件不存在: 已尝试 {candidates} (原始路径: {photo_path})"
            )
            return None
        normalized_path = found

    try:
        with open(normalized_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        import logging
        logging.getLogger("career-kb").error(f"证件照读取失败: {normalized_path} | {e}")
        return None


def _parse_sections(content: str) -> dict:
    """解析简历文本为结构化板块（兼容 Markdown ## 和 【】两种格式）"""
    sections = {}
    current_section = None
    current_lines = []

    # 匹配: 【板块名】 或 ## 板块名
    section_pattern = re.compile(r'^(?:【(.+?)】|##\s+(.+?))$')

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            if current_section:
                current_lines.append('')
            continue

        match = section_pattern.match(line)
        if match:
            if current_section:
                sections[current_section] = '\n'.join(current_lines).strip()
            # match.group(1) is 【】format, match.group(2) is ## format
            current_section = match.group(1) or match.group(2)
            current_lines = []
        elif current_section:
            current_lines.append(line)
        elif line.startswith('# ') and '姓名' not in sections:
            # Markdown H1 标题视为姓名
            sections['姓名'] = line.lstrip('# ').strip()
        elif '姓名' not in sections:
            # 第一个非空非标题行视为姓名
            sections['姓名'] = line.replace('【', '').replace('】', '')

    if current_section:
        sections[current_section] = '\n'.join(current_lines).strip()

    return sections


def generate_resume_html(
    content: str,
    photo_path: Optional[str] = None,
    structured_data: Optional[dict] = None,
    scale: float = 1.0,
) -> str:
    """生成含证件照的专业简历HTML

    Args:
        content: 智能重组后的纯文本简历
        photo_path: 证件照文件路径
        structured_data: LLM解析的结构化数据（可选，用于补充信息）
        scale: 字号缩放比例（1.0 为原始大小，<1.0 用于 PDF 回缩到一页）

    Returns:
        完整的HTML文档字符串
    """
    sections = _parse_sections(content)
    photo_b64 = _photo_to_base64(photo_path)

    # 从结构化数据中提取额外信息
    contact = {}
    if structured_data:
        basic = structured_data.get("basic_info", {})
        contact["email"] = basic.get("email", "")
        contact["phone"] = basic.get("phone", "")
        contact["city"] = basic.get("city", "")

    # 尝试从内容中提取邮箱和电话
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', content)
    phone_match = re.search(r'1[3-9]\d{9}', content)
    if email_match and not contact.get("email"):
        contact["email"] = email_match.group()
    if phone_match and not contact.get("phone"):
        contact["phone"] = phone_match.group()

    name = sections.get('姓名', '')
    # 清理姓名行
    name = name.replace('【', '').replace('】', '').strip()

    # 构建联系方式和侧边栏的内容
    photo_html = f'<img src="data:image/jpeg;base64,{photo_b64}" alt="证件照">' if photo_b64 else '<div class="photo-placeholder">证件照</div>'
    contact_html = ''
    if contact.get("email"):
        contact_html += f'<div class="contact-item"><span class="contact-label">邮箱：</span>{contact["email"]}</div>'
    if contact.get("phone"):
        contact_html += f'<div class="contact-item"><span class="contact-label">电话：</span>{contact["phone"]}</div>'
    if contact.get("city"):
        contact_html += f'<div class="contact-item"><span class="contact-label">城市：</span>{contact["city"]}</div>'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{name} - 个人简历</title>
<style>
  /* ===== A4 纸张定义 ===== */
  @page {{
    size: A4;
    margin: 0;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  /* ===== 浏览器预览：A4 纸张卡片 ===== */
  body {{
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", "SimHei", sans-serif;
    font-size: 13px;
    line-height: 1.6;
    color: #333;
    background: #e8e8e8;
    margin: 0;
    padding: 24px 0;
  }}

  .page {{
    width: 210mm;
    min-height: 297mm;
    margin: 0 auto;
    background: #1a3a5c;
    box-shadow: 0 2px 16px rgba(0,0,0,0.15);
  }}
  .page::after {{
    content: "";
    display: block;
    clear: both;
  }}

  /* ===== 打印/PDF 模式 ===== */
  @media print {{
    body {{
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
      background: #fff;
      padding: 0;
      display: block;
      min-height: auto;
    }}
    .page {{
      width: 100%;
      min-height: 297mm;
      box-shadow: none;
      margin: 0;
    }}
  }}
  .sidebar {{
    float: left;
  }}
  .main {{
    margin-left: 34%;
  }}

  /* ===== 左侧栏 ===== */
  .sidebar {{
    width: 34%;
    color: #ffffff;
    padding: 28px 20px 22px;
    overflow-wrap: break-word;
    word-break: break-all;
  }}
  .sidebar > div {{
    margin-bottom: 18px;
  }}
  .sidebar > div:last-child {{
    margin-bottom: 0;
  }}
  .photo-box {{
    text-align: center;
  }}
  .photo-box img {{
    width: 100px;
    height: 128px;
    border-radius: 6px;
    border: 3px solid rgba(255,255,255,0.3);
    background: #e0e0e0;
  }}
  .photo-placeholder {{
    width: 100px;
    height: 128px;
    margin: 0 auto;
    border-radius: 6px;
    border: 3px dashed rgba(255,255,255,0.3);
    font-size: 11px;
    color: rgba(255,255,255,0.5);
    text-align: center;
    line-height: 128px;
  }}
  .sidebar h2 {{
    font-size: 15px;
    font-weight: 600;
    border-bottom: 2px solid rgba(255,255,255,0.35);
    padding-bottom: 6px;
    margin-bottom: 8px;
    margin-top: 0;
    color: #ffffff;
    letter-spacing: 1px;
  }}
  .sidebar .block {{
    font-size: 12px;
    line-height: 1.7;
  }}
  .sidebar .contact-item {{
    margin: 5px 0;
    font-size: 11px;
    line-height: 1.6;
    padding-left: 2px;
    overflow-wrap: break-word;
    word-break: break-all;
  }}
  .sidebar .skill-tag {{
    display: inline-block;
    background: rgba(255,255,255,0.15);
    padding: 3px 8px;
    border-radius: 4px;
    margin: 0 5px 6px 0;
    font-size: 10.5px;
    color: #ffffff;
    line-height: 1.5;
    white-space: nowrap;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .skills-wrap {{
    margin: 0;
    padding: 0;
  }}
  .sidebar .edu-item, .sidebar .cert-item {{
    font-size: 11px;
    margin: 5px 0;
    opacity: 0.92;
    line-height: 1.5;
    overflow-wrap: break-word;
    word-break: break-all;
  }}

  /* ===== 右侧主内容 ===== */
  .main {{
    background: #ffffff;
    min-height: 297mm;
    padding: 30px 25px 20px 25px;
  }}
  .main h1 {{
    font-size: 26px;
    font-weight: 700;
    color: #1a3a5c;
    letter-spacing: 3px;
    margin-bottom: 2px;
  }}
  .main .subtitle {{
    font-size: 13px;
    color: #666;
    margin-bottom: 15px;
  }}
  .main h2 {{
    font-size: 14px;
    font-weight: 600;
    color: #1a3a5c;
    border-left: 3px solid #2a8cd5;
    padding-left: 8px;
    margin: 16px 0 8px;
  }}
  .main .summary-text {{
    font-size: 12px;
    color: #555;
    line-height: 1.7;
    page-break-inside: avoid;
  }}

  /* ===== 项目卡片 ===== */
  .project-card {{
    margin-bottom: 10px;
    page-break-inside: avoid;
  }}
  .project-card h3 {{
    font-size: 13px;
    font-weight: 600;
    color: #222;
    margin-bottom: 2px;
  }}
  .project-card .meta {{
    font-size: 10px;
    color: #888;
    margin-bottom: 3px;
  }}
  .project-card li {{
    font-size: 11px;
    color: #444;
    margin-left: 14px;
    margin-bottom: 1px;
    list-style: disc;
  }}

  /* ===== 实习/工作卡片 ===== */
  .internship-card {{
    margin-bottom: 10px;
    padding: 8px 12px;
    background: #f8fafc;
    border-radius: 4px;
    border-left: 3px solid #2a8cd5;
    page-break-inside: avoid;
  }}
  .internship-card h3 {{
    font-size: 12px;
    font-weight: 600;
    color: #222;
  }}
  .internship-card .meta {{
    font-size: 10px;
    color: #888;
  }}
  .internship-card p {{
    font-size: 11px;
    color: #444;
    margin-top: 3px;
  }}

</style>
</head>
<body>
<div class="page">
<div class="sidebar">
  <div class="photo-box">
    {photo_html}
  </div>
  <div class="block">
    <h2>联系方式</h2>
    {contact_html}
  </div>
  <div class="block">
    <h2>专业技能</h2>
    <div class="skills-wrap">{_render_skills(sections.get('专业技能', ''))}</div>
  </div>
  <div class="block">
    <h2>教育背景</h2>
    {_render_education(sections.get('教育背景', ''))}
  </div>
  {f'<div class="block"><h2>证书荣誉</h2>{_render_certs(sections.get("证书与荣誉", ""))}</div>' if sections.get('证书与荣誉') else ''}
</div>
<div class="main">
  <h1>{name}</h1>
  <div class="subtitle">{sections.get('求职意向', '')}</div>
  {_render_projects(sections.get('项目经历', ''))}
  {_render_internships(sections.get('工作/实习经历', ''))}
  <h2>个人总结</h2>
  <div class="summary-text">{sections.get('个人总结', '')}</div>
</div>
</div>
</body>
</html>'''

    if scale != 1.0:
        html = _scale_html(html, scale)

    return html


def _scale_html(html: str, scale: float) -> str:
    """按比例缩放 font-size 并收紧 line-height（用于 PDF 回缩到一页）。

    只缩放字号与无单位 line-height，不动 A4 尺寸/内边距/照片框。
    无单位 line-height 会随字号自动缩放，这里额外按同一比例收紧并钳制到 >=1.25，
    使同样的字号回缩能收回更多垂直空间（比单纯压字号更不易影响可读性）。
    """
    def _font(match):
        return f"font-size: {round(float(match.group(1)) * scale, 2)}px"

    html = re.sub(r'font-size:\s*([0-9.]+)px', _font, html)

    def _line_height(match):
        value = max(1.25, round(float(match.group(1)) * scale, 2))
        return f"line-height: {value};"  # 保留末尾分号

    # 只匹配无单位 line-height（如 1.6），跳过带 px 的（如照片占位 128px）
    html = re.sub(r'line-height:\s*([0-9.]+);', _line_height, html)

    return html


def _render_skills(skills_text: str) -> str:
    """渲染技能为标签"""
    if not skills_text:
        return ''
    # 提取技能关键词
    tags = re.findall(r'[\w+#.]+', skills_text)
    # 过滤短词和通用词
    tags = [t for t in tags if len(t) > 2 and t not in ('熟悉', '掌握', '了解', '具备', '使用', '进行', '负责', '基于', '具有', '拥有', '能够', '可以', '通过', '需要', '包括', '其中', '主要', '相关', '以及', '及其')]
    return ' '.join(f'<span class="skill-tag">{t}</span>' for t in tags[:20])


def _render_education(edu_text: str) -> str:
    """渲染教育背景"""
    if not edu_text:
        return ''
    lines = edu_text.strip().split('\n')
    return ''.join(f'<div class="edu-item">{l.strip("- ")}</div>' for l in lines if l.strip())


def _render_certs(cert_text: str) -> str:
    """渲染证书"""
    if not cert_text:
        return ''
    lines = cert_text.strip().split('\n')
    return ''.join(f'<div class="cert-item">{l.strip("- ")}</div>' for l in lines if l.strip())


def _render_projects(projects_text: str) -> str:
    """渲染项目经历板块（自动检测分隔方式）"""
    if not projects_text:
        return ''
    html = '<h2>项目经历</h2>'

    # 先尝试按空行分隔（智能模式格式）
    parts = re.split(r'\n\n+', projects_text.strip())
    # 如果只有1个且内容很长，尝试按项目标题行分隔（含 ｜ 的行）
    if len(parts) <= 1:
        lines = projects_text.strip().split('\n')
        # 按包含 ｜ 和日期的标题行重新分割
        parts = []
        current = []
        for line in lines:
            if re.match(r'.+（.+）\｜\s*\d{4}', line.strip()):
                if current:
                    parts.append('\n'.join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            parts.append('\n'.join(current))

    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.strip().split('\n')
        first_line = lines[0].strip()

        # 跳过 "项目经历" 标题本身
        if first_line in ('项目经历', '【项目经历】', '## 项目经历'):
            continue

        title = first_line
        meta = ''
        desc = ''
        items = []

        for l in lines[1:]:
            l = l.strip()
            if not l:
                continue
            if l.startswith('技术栈') or l.startswith('技术/工具') or l.startswith('技术：'):
                meta = l.replace('技术栈/工具：', '').replace('技术栈：', '').replace('技术/工具：', '').replace('技术：', '').strip()
            elif l.startswith('项目描述') or l.startswith('描述：'):
                desc = l.replace('项目描述：', '').replace('描述：', '').strip()
            elif l.startswith('核心职责与成果') or l.startswith('职责与成果') or l.startswith('职责：') or l.startswith('成果：'):
                continue
            elif l.startswith('-') or l.startswith('•') or l.startswith('·') or l.startswith('  -'):
                items.append(l.lstrip('-•· '))
            elif l and not l.startswith('【'):
                items.append(l)

        html += f'<div class="project-card"><h3>{title}</h3>'
        if meta:
            html += f'<div class="meta">技术栈：{meta}</div>'
        if desc:
            html += f'<div class="meta" style="color:#666;">{desc}</div>'
        for item in items[:5]:
            html += f'<li>{item}</li>'
        html += '</div>'
    return html


def _render_internships(intern_text: str) -> str:
    """渲染实习/工作经历"""
    if not intern_text:
        return ''
    html = '<h2>工作/实习经历</h2>'
    parts = re.split(r'\n(?=实习|工作|\d{4})', intern_text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.strip().split('\n')
        title = lines[0].strip()
        meta = ''
        desc_lines = []
        for l in lines[1:]:
            l = l.strip()
            if any(kw in l for kw in ['时间', '部门', '岗位']):
                meta = l
            else:
                desc_lines.append(l)
        html += f'<div class="internship-card"><h3>{title}</h3>'
        if meta:
            html += f'<div class="meta">{meta}</div>'
        if desc_lines:
            html += f'<p>{" ".join(desc_lines[:3])}</p>'
        html += '</div>'
    return html
