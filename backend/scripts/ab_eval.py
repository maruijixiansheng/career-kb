"""A/B 评测：RAG 重组链路 vs 全量素材单次投喂

A 组：把当前用户的全部简历原文 + 技能库一次性塞给模型，用同一套 prompt 生成
B 组：走产品真实链路（JD 解析 → 混合检索 → LLM 相关性把关 → 重组 → 事实核查）

两边用同一个 SYSTEM prompt、同一个模型、同一个 temperature，唯一的变量是
「素材由检索挑选」还是「全量都给」。

指标：
  - 耗时、LLM 调用次数、输入/输出字符数
  - JD 关键词覆盖率（技术栈 + 关键词是否出现在输出里）
  - 事实核查（同一份全量素材做裁判，score / error / warning 数）
  - 疑似新增数字（输出里出现、但原文中找不到的数字，规则检测，仅供参考）

用法：
    python backend/scripts/ab_eval.py --dry-run
    python backend/scripts/ab_eval.py --max-cases 4
    python backend/scripts/ab_eval.py --jds <jd_id,jd_id> --resumes <resume_id,...>
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
# config 的 env_file=".env" 是相对路径，必须让工作目录落在 backend/ 才能读到密钥
os.chdir(PROJECT_ROOT / "backend")

from app.core.llm_client import llm_client  # noqa: E402
from app.core.rag_engine import rag_engine  # noqa: E402
from app.core.prompts import (  # noqa: E402
    SMART_RESTRUCTURE_SYSTEM,
    SMART_RESTRUCTURE_USER,
)

# Chroma 的 "Number of requested results..." 警告与本评测无关，静音
import logging  # noqa: E402
for _name in ("chromadb", "chromadb.telemetry", "chromadb.telemetry.product.posthog"):
    logging.getLogger(_name).setLevel(logging.ERROR)

DEFAULT_USER_EMAIL = "demo@test.com"


# ============================================================
# 数据加载（直接读 SQLite，避免依赖 FastAPI 层）
# ============================================================

def load_data(db_path: Path, email: str, include_orphan_jds: bool = False):
    import sqlite3

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        user = conn.execute("SELECT id, email FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            raise SystemExit(f"[错误] 找不到用户 {email}")
        uid = user["id"]

        resumes = conn.execute(
            "SELECT id, name, raw_text FROM resumes WHERE user_id = ? AND is_active = 1", (uid,)
        ).fetchall()
        jds = conn.execute(
            "SELECT id, title, company, raw_text, user_id FROM job_descriptions "
            "WHERE user_id = ?",
            (uid,),
        ).fetchall()
        if include_orphan_jds:
            # 早期版本没有 user_id，历史上传的 JD 归属为 NULL（仍属于同一人），评测时可选纳入
            jds = list(jds) + list(
                conn.execute(
                    "SELECT id, title, company, raw_text, user_id FROM job_descriptions "
                    "WHERE user_id IS NULL"
                ).fetchall()
            )
        skills = conn.execute(
            "SELECT entry_type, title, content, tags, importance FROM skill_library "
            "WHERE user_id = ? AND is_active = 1",
            (uid,),
        ).fetchall()
        return uid, [dict(r) for r in resumes], [dict(r) for r in jds], [dict(r) for r in skills]
    finally:
        conn.close()


def build_full_materials(resumes, skills) -> str:
    """A 组素材：全部简历原文 + 技能库（不带相关性分数）"""
    parts = []
    for i, r in enumerate(resumes, 1):
        parts.append(f"[素材{i}] 来源:简历《{r['name']}》")
        parts.append((r["raw_text"] or "").strip())
        parts.append("---")
    if skills:
        parts.append("[技能库] 用户手工维护的技术栈 / 项目 / 实习：")
        for s in skills:
            parts.append(
                f"- [{s['entry_type']}] {s['title']}（重要度{s['importance']}星）"
                f"\n  {s['content']}"
            )
    return "\n".join(parts)


# ============================================================
# 指标
# ============================================================

def strip_analysis(text: str) -> str:
    return re.split(r"<analysis>", text or "", maxsplit=1)[0].strip()


SOFT_TERMS = {
    "学习能力", "团队协作", "责任心", "执行能力", "沟通", "问题拆解", "逻辑思维",
    "英文", "文档", "抗压", "主动", "自我驱动", "好奇心", "兴趣", "能力",
}


def jd_terms(jd_reqs: dict) -> list[str]:
    """JD 的硬性技术词（过滤软技能与含糊表述，避免覆盖率指标被稀释）"""
    terms = []
    for s in jd_reqs.get("technical_skills", []) or []:
        name = (s.get("name") or "").strip()
        if len(name) >= 2:
            terms.append(name)
    for k in jd_reqs.get("keywords", []) or []:
        k = (k or "").strip()
        if len(k) >= 2:
            terms.append(k)

    seen, out = set(), []
    for t in terms:
        if "（" in t or "(" in t:
            continue
        if any(soft in t for soft in SOFT_TERMS):
            continue
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            out.append(t)
    return out


def keyword_coverage(text: str, terms: list[str]):
    if not terms:
        return 0.0, 0, 0, []
    low = (text or "").lower()
    hit = [t for t in terms if t.lower() in low]
    miss = [t for t in terms if t.lower() not in low]
    return len(hit) / len(terms), len(hit), len(terms), miss


NUMBER_RE = re.compile(r"(?<![\w.])(\d{1,4}(?:\.\d+)?%?)")


def numbers_not_in_source(text: str, source: str):
    """输出中出现、原文中找不到的数字（格式化差异已忽略空格/逗号）"""
    text_norm = (text or "").replace(" ", "").replace(",", "")
    src_norm = (source or "").replace(" ", "").replace(",", "")
    bad = []
    for m in NUMBER_RE.finditer(text_norm):
        token = m.group(1)
        core = token.rstrip("%")
        # 过滤明显是年份/日期的 4 位数字
        if len(core) == 4 and core.isdigit() and core.startswith(("19", "20")):
            continue
        if token not in src_norm and core not in src_norm:
            bad.append(token)
    # 去重
    seen, uniq = set(), []
    for b in bad:
        if b not in seen:
            seen.add(b)
            uniq.append(b)
    return uniq


class CallCounter:
    """统计 LLM 调用次数与字符量（包住 llm_client.chat，chat_json 内部也会走它）"""

    def __init__(self):
        self.n = 0
        self.chars_in = 0
        self.chars_out = 0
        self._orig = llm_client.chat

    def install(self):
        counter = self

        async def wrapped(*args, **kwargs):
            text = await counter._orig(*args, **kwargs)
            counter.n += 1
            counter.chars_in += len(kwargs.get("system_prompt") or "") + len(
                kwargs.get("user_message") or ""
            )
            counter.chars_out += len(text or "")
            return text

        llm_client.chat = wrapped

    def reset(self):
        self.n = 0
        self.chars_in = 0
        self.chars_out = 0

    def uninstall(self):
        llm_client.chat = self._orig


# ============================================================
# 单组执行
# ============================================================

async def run_group_a(jd, jd_reqs, materials, jd_reqs_json):
    user_message = SMART_RESTRUCTURE_USER.format(
        jd_title=jd.get("title") or "目标岗位",
        jd_company=jd.get("company") or "",
        jd_text=jd["raw_text"],
        jd_requirements=jd_reqs_json,
        all_materials=materials,
    )
    text = await llm_client.chat(
        system_prompt=SMART_RESTRUCTURE_SYSTEM,
        user_message=user_message,
        model=rag_engine.powerful_model,
        temperature=0.1,
        max_tokens=4096,
    )
    return strip_analysis(text)


async def run_group_b(jd, resume_id: str, user_id: str):
    result = await rag_engine.smart_restructure_pipeline(
        jd_text=jd["raw_text"],
        user_id=user_id,
        jd_title=jd.get("title") or "",
        jd_company=jd.get("company") or "",
        resume_id=resume_id,
    )
    return strip_analysis(result["generated_resume"]), result.get("retrieved_chunks", [])


# ============================================================
# 主流程
# ============================================================

async def main():
    parser = argparse.ArgumentParser(description="A/B 评测：RAG 链路 vs 全量投喂")
    parser.add_argument("--db", default=str(PROJECT_ROOT / "data" / "career.db"))
    parser.add_argument("--user-email", default=DEFAULT_USER_EMAIL)
    parser.add_argument("--max-cases", type=int, default=4, help="最多跑几个 JD×简历 组合")
    parser.add_argument("--jds", default="", help="逗号分隔的 JD id（默认取最新的若干条）")
    parser.add_argument("--resumes", default="", help="逗号分隔的简历 id（默认取最新的若干份）")
    parser.add_argument("--out", default="", help="输出目录（默认 data/eval/ab_<时间戳>）")
    parser.add_argument("--include-orphan-jds", action="store_true",
                        help="纳入 user_id 为空的历史 JD（早期数据，仍属同一人）")
    parser.add_argument("--dry-run", action="store_true", help="只打印用例与素材规模，不调用 API")
    args = parser.parse_args()

    db_path = Path(args.db)
    uid, resumes, jds, skills = load_data(db_path, args.user_email, args.include_orphan_jds)

    # A 组素材必须是「用户全部可用素材」，与 B 组检索池一致；
    # --resumes 只用于挑选用例，不能缩小 A 组的素材范围
    materials = build_full_materials(resumes, skills)

    if args.resumes:
        picked = set(x.strip() for x in args.resumes.split(",") if x.strip())
        resumes = [r for r in resumes if r["id"] in picked]
    if args.jds:
        picked = set(x.strip() for x in args.jds.split(",") if x.strip())
        jds = [j for j in jds if j["id"] in picked]

    if not resumes or not jds:
        raise SystemExit("[错误] 没有可用简历或 JD")


    # 组合用例：优先 JD×简历 交叉组合，保证不同 JD / 不同简历都被覆盖
    jd_order = sorted(jds, key=lambda j: j["title"] or "")
    resume_order = sorted(resumes, key=lambda r: r["name"] or "")
    all_cases = [(jd, r) for jd in jd_order for r in resume_order]
    cases = all_cases[: args.max_cases]

    print(f"[数据] 用户 {args.user_email} | 简历 {len(resumes)} 份 | JD {len(jds)} 条 | 技能库 {len(skills)} 条")
    print(f"[素材] 全量素材 {len(materials)} 字符（A 组每次全量投喂）")
    print(f"[用例] {len(cases)} 组")
    for i, (jd, r) in enumerate(cases, 1):
        print(f"  {i}. JD《{jd['title']}》 × 简历《{r['name']}》")

    if args.dry_run:
        print("\n[dry-run] 不调用 API，结束")
        return

    if args.out:
        out_dir = Path(args.out)
        if not out_dir.is_absolute():
            out_dir = PROJECT_ROOT / out_dir
    else:
        out_dir = PROJECT_ROOT / "data" / "eval" / f"ab_{datetime.now():%Y%m%d_%H%M%S}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "outputs").mkdir(exist_ok=True)

    counter = CallCounter()
    counter.install()

    results = []
    try:
        for idx, (jd, resume) in enumerate(cases, 1):
            print(f"\n===== 用例 {idx}/{len(cases)}: {jd['title']} × {resume['name']} =====")

            # JD 解析一次，A/B 共用（B 内部也有缓存）
            t0 = time.perf_counter()
            jd_reqs = await rag_engine.parse_jd(jd["raw_text"])
            parse_elapsed = time.perf_counter() - t0
            terms = jd_terms(jd_reqs)
            jd_reqs_json = json.dumps(jd_reqs, ensure_ascii=False, indent=2)

            case = {
                "case": idx,
                "jd_id": jd["id"],
                "jd_title": jd["title"],
                "resume_id": resume["id"],
                "resume_name": resume["name"],
                "jd_terms": terms,
                "parse_elapsed_s": round(parse_elapsed, 2),
            }

            for group in ("A", "B"):
                counter.reset()
                t0 = time.perf_counter()
                try:
                    if group == "A":
                        text = await run_group_a(jd, jd_reqs, materials, jd_reqs_json)
                        retrieved = []
                    else:
                        text, retrieved = await run_group_b(jd, resume["id"], uid)
                    elapsed = time.perf_counter() - t0

                    cover, hit, total, miss = keyword_coverage(text, terms)
                    bad_numbers = numbers_not_in_source(text, materials)
                    fact = await rag_engine.fact_check(materials, text)
                    issues = fact.get("issues") or []
                    errors = sum(1 for i in issues if (i.get("severity") or "").lower() == "error")

                    row = {
                        "group": group,
                        "elapsed_s": round(elapsed, 2),
                        "llm_calls": counter.n,
                        "input_chars": counter.chars_in,
                        "output_chars": len(text),
                        "jd_coverage": round(cover, 3),
                        "jd_hit": hit,
                        "jd_total": total,
                        "jd_missing": miss,
                        "fact_score": fact.get("score"),
                        "fact_is_factual": fact.get("is_factual"),
                        "fact_errors": errors,
                        "fact_warnings": len(issues) - errors,
                        "fact_issues": issues,
                        "suspect_numbers": bad_numbers,
                        "retrieved_chunks": len(retrieved),
                        "output_file": f"outputs/{idx}_{group}_{resume['name'][:12]}.md".replace(" ", "_"),
                    }
                    (out_dir / row["output_file"]).write_text(text, encoding="utf-8")

                    print(
                        f"  [{group}] {row['elapsed_s']}s | {row['llm_calls']} 次调用 | "
                        f"{row['output_chars']} 字 | JD覆盖 {hit}/{total} | "
                        f"核查 {row['fact_score']} 分 (error {errors}, warn {row['fact_warnings']}) | "
                        f"疑似新增数字 {len(bad_numbers)}"
                    )
                    case[group] = row
                except Exception as e:
                    print(f"  [{group}] 失败: {type(e).__name__}: {e}")
                    case[group] = {"group": group, "error": f"{type(e).__name__}: {e}"}

            results.append(case)
    finally:
        counter.uninstall()

    # 写报告
    (out_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "report.md").write_text(render_report(results, materials), encoding="utf-8")
    print(f"\n[完成] 报告: {out_dir / 'report.md'}")


def render_report(results: list[dict], materials: str) -> str:
    lines = [
        "# A/B 评测报告：RAG 链路 vs 全量投喂",
        "",
        f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M}",
        f"- 全量素材规模：{len(materials)} 字符",
        "- A 组：全部简历原文 + 技能库一次性投喂，单次调用",
        "- B 组：产品真实链路（解析 JD → 混合检索 → 相关性把关 → 重组 → 事实核查）",
        "- 事实核查对两组使用同一份全量素材作裁判",
        "",
        "## 明细",
        "",
        "| 用例 | JD | 简历 | 组 | 耗时(s) | LLM调用 | 输出字符 | JD关键词覆盖 | 核查分 | error | warning | 疑似新增数字 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for c in results:
        for g in ("A", "B"):
            r = c.get(g, {})
            if "error" in r:
                lines.append(
                    f"| {c['case']} | {c['jd_title']} | {c['resume_name']} | {g} | 失败 | - | - | - | - | - | - | {r['error'][:40]} |"
                )
                continue
            lines.append(
                f"| {c['case']} | {c['jd_title']} | {c['resume_name']} | {g} | {r['elapsed_s']} | "
                f"{r['llm_calls']} | {r['output_chars']} | {r['jd_hit']}/{r['jd_total']} "
                f"({r['jd_coverage']:.0%}) | {r['fact_score']} | {r['fact_errors']} | "
                f"{r['fact_warnings']} | {len(r['suspect_numbers'])} |"
            )

    def avg(group, key, size=False):
        vals = []
        for c in results:
            r = c.get(group, {})
            if "error" in r or key not in r:
                continue
            vals.append(len(r[key]) if size else r[key])
        return sum(vals) / len(vals) if vals else 0

    lines += [
        "",
        "## 均值",
        "",
        "| 指标 | A 全量投喂 | B RAG链路 |",
        "|---|---:|---:|",
        f"| 耗时 (s) | {avg('A','elapsed_s'):.1f} | {avg('B','elapsed_s'):.1f} |",
        f"| LLM 调用次数 | {avg('A','llm_calls'):.1f} | {avg('B','llm_calls'):.1f} |",
        f"| JD 关键词覆盖率 | {avg('A','jd_coverage'):.0%} | {avg('B','jd_coverage'):.0%} |",
        f"| 事实核查分数 | {avg('A','fact_score'):.1f} | {avg('B','fact_score'):.1f} |",
        f"| 事实 error 数 | {avg('A','fact_errors'):.1f} | {avg('B','fact_errors'):.1f} |",
        f"| 事实 warning 数 | {avg('A','fact_warnings'):.1f} | {avg('B','fact_warnings'):.1f} |",
        f"| 疑似新增数字 | {avg('A','suspect_numbers', size=True):.1f} | {avg('B','suspect_numbers', size=True):.1f} |",
        "",
        "## 逐用例明细",
        "",
    ]
    for c in results:
        lines.append(f"### 用例 {c['case']}：《{c['jd_title']}》 × 《{c['resume_name']}》")
        lines.append("")
        for g in ("A", "B"):
            r = c.get(g, {})
            if "error" in r:
                lines.append(f"- {g} 组失败：{r['error']}")
                continue
            lines.append(
                f"- **{g} 组**：输出 `{r['output_file']}`｜JD 未覆盖关键词："
                f"{', '.join(r['jd_missing']) or '无'}｜疑似新增数字：{', '.join(r['suspect_numbers']) or '无'}"
                f"｜检索片段：{r['retrieved_chunks']}"
            )
        lines.append("")
    lines += [
        "## 怎么读这份报告",
        "",
        "1. **事实核查分/error 数**是最重要的指标：两组用同一份全量素材当裁判，分数低说明输出了原文没有的内容。",
        "2. **JD 关键词覆盖**只反映「有没有提到 JD 要的技术」，不代表写得更好；覆盖低不一定是坏事（可能原简历真没有）。",
        "3. **疑似新增数字**是规则检测，正常改写也可能误报（如把「三」写成「3」），必须人眼看 `outputs/` 原文确认。",
        "4. **耗时/调用次数**是 RAG 的代价，A 组 1 次、B 组 4 次左右。",
        "5. 自动指标只能排序，不能下结论；最终请抽 2 组对读 A/B 原文。",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    asyncio.run(main())
