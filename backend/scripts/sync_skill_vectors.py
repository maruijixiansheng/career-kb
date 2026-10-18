"""技能库向量一致性巡检 / 清理工具

背景：旧版 api/skill_library.py 的「编辑 / 删除」只改数据库、不碰 Chroma，
导致两类脏数据：
  - 幽灵向量（orphan）：Chroma 里有、DB 里没有 → 会被同用户检索命中，把已删除内容写进简历
  - 缺失向量（missing）：DB 里有、Chroma 里没有 → 该条目永远检索不到

本脚本默认 **dry-run（只读）**，只打印报告；加 --commit 才会：
  1) 全量备份 Chroma 目录与 SQLite 文件到 data/backups/<时间戳>/
  2) 把将删除的幽灵向量（含原文）导出为 JSON 归档（内容不丢）
  3) 删除幽灵向量
缺失向量（missing）不自动重建——重建需要调用嵌入 API，请在应用里重新编辑该条目，或重新上传简历。

用法（SQLite 本地数据）：
    python backend/scripts/sync_skill_vectors.py                  # 只读报告
    python backend/scripts/sync_skill_vectors.py --archive-only   # 只把幽灵向量原文导出为 JSON（不删任何东西）
    python backend/scripts/sync_skill_vectors.py --commit         # 备份 + 归档 + 删除

参数：
    --db        SQLite 路径，默认 <项目根>/data/career.db
    --chroma    Chroma 持久化目录，默认 <项目根>/data/chroma
    --backup-dir 备份/归档目录，默认 <项目根>/data/backups
"""

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COLLECTION = "skill_library"


def load_db_ids(db_path: Path) -> set[str]:
    if not db_path.exists():
        sys.exit(f"[错误] 找不到数据库文件: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return {row[0] for row in conn.execute("SELECT id FROM skill_library")}
    finally:
        conn.close()


def load_sqlite_user_ids(db_path: Path) -> set[str]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return {row[0] for row in conn.execute("SELECT id FROM users")}
    finally:
        conn.close()


def load_chroma_entries(chroma_dir: Path) -> tuple[list[str], list[dict], list[str]]:
    if not chroma_dir.exists():
        sys.exit(f"[错误] 找不到 Chroma 目录: {chroma_dir}")
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(chroma_dir), settings=Settings(anonymized_telemetry=False)
    )
    names = [c.name for c in client.list_collections()]
    if COLLECTION not in names:
        sys.exit(f"[提示] Chroma 中没有 {COLLECTION} 集合，无需处理")
    col = client.get_collection(COLLECTION)
    data = col.get(include=["metadatas", "documents"])
    return data.get("ids") or [], data.get("metadatas") or [], data.get("documents") or []


def backup(db_path: Path, chroma_dir: Path, backup_dir: Path) -> Path:
    """备份必须发生在打开 Chroma 客户端之前，避免复制到写入中的 SQLite"""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"skill_vector_cleanup_{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    shutil.copytree(chroma_dir, target / "chroma")
    shutil.copy2(db_path, target / db_path.name)
    return target


def write_archive(ghosts: list[tuple[str, dict, str]], path: Path) -> Path:
    """把幽灵向量（含原文）导出为 JSON，确保内容不丢"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [{"id": i, "metadata": md, "document": doc} for i, md, doc in ghosts],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="技能库向量巡检 / 清理（默认 dry-run）")
    parser.add_argument("--db", default=str(PROJECT_ROOT / "data" / "career.db"))
    parser.add_argument("--chroma", default=str(PROJECT_ROOT / "data" / "chroma"))
    parser.add_argument("--backup-dir", default=str(PROJECT_ROOT / "data" / "backups"))
    parser.add_argument("--commit", action="store_true", help="真正执行删除（默认只读）")
    parser.add_argument("--archive-only", action="store_true",
                        help="只把幽灵向量原文导出为 JSON，不删除任何数据")
    parser.add_argument("--allow-mismatch", action="store_true",
                        help="即使 DB 与 Chroma 条目几乎不重叠也继续（危险，仅确认过时使用）")
    args = parser.parse_args()

    db_path = Path(args.db)
    chroma_dir = Path(args.chroma)
    backup_dir = Path(args.backup_dir)

    db_ids = load_db_ids(db_path)

    backup_path = None
    if args.commit:
        # 先备份，再打开 Chroma
        backup_path = backup(db_path, chroma_dir, backup_dir)
        print(f"[备份] Chroma + DB 已复制到: {backup_path}")

    ids, metadatas, documents = load_chroma_entries(chroma_dir)
    chroma_ids = set(ids)

    ghosts = [(i, metadatas[n] or {}, documents[n] or "") for n, i in enumerate(ids)
              if i not in db_ids]

    # 安全闸门：Docker 部署跑在 PostgreSQL 上，本脚本读的是 SQLite。
    # 若幽灵向量的 user_id 在 SQLite 用户表里根本不存在，说明这些"幽灵"是 PG 里的真实条目，
    # 继续删会误删真实向量（本项目已实测踩到：14 vs 8，其中 8 条是 PG 里的真条目）。
    if ghosts and not args.allow_mismatch:
        known_users = load_sqlite_user_ids(db_path)
        ghost_users = {
            str(md.get("user_id") or "") for _, md, _ in ghosts
        } - {"", "None", "none"}
        unknown_users = sorted(u for u in ghost_users if u not in known_users)
        if unknown_users:
            print(
                "[中止] 幽灵向量的 user_id 不在本地 SQLite 用户表中："
                f"{', '.join(u[:8] for u in unknown_users)}\n"
                "       说明 Chroma 里的数据属于另一个数据库（很可能是 Docker + PostgreSQL）。\n"
                "       删掉它们会误删真实条目的向量。确认要删请加 --allow-mismatch。"
            )
            return

    missing = sorted(db_ids - chroma_ids)

    print(f"\n[现状] DB 条目 {len(db_ids)} 条 / Chroma 向量 {len(ids)} 条")
    print(f"[幽灵向量] {len(ghosts)} 条（Chroma 有、DB 无）")
    for i, md, doc in ghosts:
        title = md.get("title") or "-"
        user = str(md.get("user_id") or "-")[:8]
        preview = doc.replace("\n", " / ")[:70]
        print(f"  - {i}  [{md.get('entry_type') or '?'}] {title}  user={user}")
        print(f"      {preview}")

    print(f"[缺失向量] {len(missing)} 条（DB 有、Chroma 无）")
    for i in missing:
        print(f"  - {i}")

    if args.archive_only:
        if not ghosts:
            print("\n[完成] 没有幽灵向量需要归档")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = write_archive(ghosts, backup_dir / f"orphan_skill_vectors_{stamp}.json")
        print(f"\n[归档] {len(ghosts)} 条幽灵向量（含原文）已导出: {path}")
        print("[未删除] 向量仍在 Chroma 中；确认无用后再执行 --commit")
        return

    if not args.commit:
        print("\n[dry-run] 未做任何修改。确认无误后加 --commit 执行：")
        print("    python backend/scripts/sync_skill_vectors.py --commit")
        return

    if not ghosts:
        print("\n[完成] 没有幽灵向量需要删除")
        return

    # 1) 归档要删除的内容（先落盘，再删）
    archive = write_archive(ghosts, backup_path / "orphan_skill_vectors.json")
    print(f"[归档] 幽灵向量原文已导出: {archive}")

    # 2) 删除
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(chroma_dir), settings=Settings(anonymized_telemetry=False)
    )
    col = client.get_collection(COLLECTION)
    ghost_ids = [i for i, _, _ in ghosts]
    col.delete(ids=ghost_ids)

    remain = len(col.get(include=[])["ids"])
    print(f"[完成] 已删除 {len(ghost_ids)} 条幽灵向量，剩余 {remain} 条")

    if missing:
        print("[待办] 以下 DB 条目缺向量，请在应用里重新编辑保存，或重新上传对应简历：")
        for i in missing:
            print(f"  - {i}")


if __name__ == "__main__":
    main()
