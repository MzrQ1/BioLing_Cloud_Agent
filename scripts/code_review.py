"""
项目代码定期审查脚本

功能：
1. 审查最近的代码修改（git diff + commit 分析）
2. 检查已知报错和修复记录
3. 记忆系统健康度评估
4. 生成审查摘要

用法：
    python scripts/code_review.py              # 审查最近7天
    python scripts/code_review.py --days 14    # 审查最近14天
    python scripts/code_review.py --memory-only # 仅检查记忆系统
    python scripts/code_review.py --full       # 全量审查
"""
import sys
import os
import subprocess
import json
from datetime import datetime, timedelta
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_recent_commits(days: int = 7) -> list:
    """获取最近N天的git提交"""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--pretty=format:%h|%s|%ad|%an", "--date=short"],
            capture_output=True, text=True, check=True
        )
        if not result.stdout.strip():
            return []
        commits = []
        for line in result.stdout.strip().split("\n"):
            parts = line.split("|")
            if len(parts) >= 4:
                commits.append({
                    "hash": parts[0],
                    "message": parts[1],
                    "date": parts[2],
                    "author": parts[3]
                })
        return commits
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] 获取git日志失败: {e.stderr}")
        return []


def get_commit_stats(commit_hash: str) -> dict:
    """获取单个提交的变更统计"""
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", f"{commit_hash}~1", commit_hash],
            capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().split("\n")
        files_changed = 0
        insertions = 0
        deletions = 0
        for line in lines:
            if "|" in line and ("insertion" in line or "deletion" in line or "changed" in line):
                parts = line.split("|")
                if len(parts) >= 2:
                    files_changed += 1
                    stats = parts[-1]
                    if "insertion" in stats:
                        n = int("".join(filter(str.isdigit, stats.split("insertion")[0])))
                        insertions += n
                    if "deletion" in stats:
                        n = int("".join(filter(str.isdigit, stats.split("deletion")[0])))
                        deletions += n
        return {"files": files_changed, "insertions": insertions, "deletions": deletions}
    except Exception:
        return {"files": 0, "insertions": 0, "deletions": 0}


def get_changed_files(days: int = 7) -> dict:
    """统计被修改的文件频率"""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"--since={since}"],
            capture_output=True, text=True, check=True
        )
        if not result.stdout.strip():
            # 尝试用 log 方式获取
            result = subprocess.run(
                ["git", "log", f"--since={since}", "--name-only", "--pretty=format:"],
                capture_output=True, text=True, check=True
            )
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        return dict(Counter(files).most_common(15))
    except Exception as e:
        print(f"[WARN] 获取文件变更失败: {e}")
        return {}


def check_memory_health() -> dict:
    """检查记忆系统健康度"""
    health = {
        "status": "unknown",
        "issues": [],
        "suggestions": []
    }

    try:
        from app.database.conversation_store import ConversationStore, MemoryScorer
        from app.database.database import get_db_context
        from app.database.models import ConversationHistory
        from sqlalchemy import func

        with get_db_context() as db:
            total = db.query(func.count(ConversationHistory.id)).scalar() or 0

            if total == 0:
                health["status"] = "empty"
                health["suggestions"].append("记忆系统为空，建议积累一些对话数据后再评估")
                return health

            avg_score = db.query(func.avg(
                func.length(ConversationHistory.content)
            )).scalar() or 0

            # 检查是否超过上限
            user_counts = db.query(
                ConversationHistory.user_id,
                func.count(ConversationHistory.id)
            ).group_by(ConversationHistory.user_id).all()

            for uid, count in user_counts:
                if count > ConversationStore.MAX_MEMORIES_PER_USER:
                    health["issues"].append(
                        f"用户 {uid} 记忆数({count})超过上限({ConversationStore.MAX_MEMORIES_PER_USER})"
                    )
                    health["suggestions"].append(f"建议为用户 {uid} 运行记忆反思清理")

            # 检查平均内容长度
            if avg_score < 20:
                health["suggestions"].append("平均对话内容较短，可能影响记忆质量")

            health["status"] = "healthy" if not health["issues"] else "needs_attention"
            health["total_memories"] = total
            health["users"] = len(user_counts)
            health["user_distribution"] = {uid: count for uid, count in user_counts}

    except ImportError as e:
        health["status"] = "import_error"
        health["issues"].append(f"无法导入记忆模块: {e}")
    except Exception as e:
        health["status"] = "error"
        health["issues"].append(f"检查记忆系统时出错: {e}")

    return health


def check_common_issues() -> list:
    """检查常见问题模式"""
    issues = []

    # 检查 nodes.py 中是否有 next_node 设置
    try:
        with open("app/agent/nodes.py", "r", encoding="utf-8") as f:
            content = f.read()
            # 检查所有节点函数是否都设置了 next_node
            import re
            node_funcs = re.findall(r'def (\w+_node)\(state', content)
            next_node_set = re.findall(r'state\["next_node"\]', content)
            if len(next_node_set) < len(node_funcs):
                missing = len(node_funcs) - len(next_node_set)
                issues.append(f"[NODES] {missing} 个节点可能未设置 next_node 路由")
    except FileNotFoundError:
        issues.append("[NODES] nodes.py 文件不存在")

    # 检查 .env 是否存在
    if not os.path.exists(".env"):
        issues.append("[CONFIG] .env 文件不存在，需从 .env.example 复制")

    # 检查 requirements.txt 是否有明显问题
    try:
        with open("requirements.txt", "r") as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            packages = [l.split("==")[0].split(">=")[0].split("<")[0].strip() for l in lines]
            if len(packages) != len(set(packages)):
                dupes = [p for p in packages if packages.count(p) > 1]
                issues.append(f"[DEPS] requirements.txt 中有重复依赖: {set(dupes)}")
    except FileNotFoundError:
        issues.append("[DEPS] requirements.txt 不存在")

    return issues


def print_separator(title: str, char: str = "="):
    width = 60
    print(f"\n{char * width}")
    print(f"  {title}")
    print(f"{char * width}")


def run_review(days: int = 7, memory_only: bool = False, full: bool = False):
    """执行审查"""
    review_days = 30 if full else days

    if not memory_only:
        # === 1. 提交审查 ===
        print_separator("代码变更审查")
        print(f"审查周期: 最近 {review_days} 天")
        print(f"审查时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        commits = get_recent_commits(review_days)
        if commits:
            print(f"\n提交数量: {len(commits)}")
            print("\n最近提交:")
            for c in commits[:10]:
                stats = get_commit_stats(c["hash"])
                print(f"  {c['hash']} | {c['date']} | {c['message']} "
                      f"(+{stats['insertions']} -{stats['deletions']})")
        else:
            print("\n最近无新提交")

        # === 2. 文件变更热度 ===
        print_separator("文件变更热度")
        changed = get_changed_files(review_days)
        if changed:
            for file, count in changed.items():
                bar = "█" * min(count, 30)
                print(f"  {file:<45} {bar} ({count})")
        else:
            print("  无文件变更记录")

        # === 3. 常见问题检查 ===
        print_separator("常见问题检查")
        issues = check_common_issues()
        if issues:
            for issue in issues:
                print(f"  ⚠ {issue}")
        else:
            print("  ✓ 未发现明显问题")

    # === 4. 记忆系统健康度 ===
    print_separator("记忆系统健康度")
    mem_health = check_memory_health()
    print(f"  状态: {mem_health['status']}")
    if "total_memories" in mem_health:
        print(f"  总记忆数: {mem_health['total_memories']}")
        print(f"  用户数: {mem_health['users']}")
    if mem_health["issues"]:
        print("\n  问题:")
        for issue in mem_health["issues"]:
            print(f"    ⚠ {issue}")
    if mem_health["suggestions"]:
        print("\n  建议:")
        for s in mem_health["suggestions"]:
            print(f"    → {s}")

    # === 5. 审查摘要 ===
    print_separator("审查摘要")
    print(f"  审查完成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if commits:
        print(f"  本周提交 {len(commits)} 次，建议关注 LangGraph 节点路由完整性")
    print(f"  记忆系统状态: {mem_health['status']}")
    if issues:
        print(f"  发现 {len(issues)} 个潜在问题，建议逐一处理")
    else:
        print("  未发现潜在问题")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BioLing Cloud Agent 代码审查脚本")
    parser.add_argument("--days", type=int, default=7, help="审查天数 (默认7)")
    parser.add_argument("--memory-only", action="store_true", help="仅检查记忆系统")
    parser.add_argument("--full", action="store_true", help="全量审查（30天）")

    args = parser.parse_args()
    run_review(days=args.days, memory_only=args.memory_only, full=args.full)
