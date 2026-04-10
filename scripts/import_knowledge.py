"""
RAG知识库导入脚本

使用方法：
    python scripts/import_knowledge.py

功能：
    - 扫描docs/目录下的.txt和.md文件
    - 自动分块、生成Embedding
    - 存入Chroma向量数据库
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import re
from app.database.vector_store import VectorStore
from app.config import config


def parse_markdown(content: str) -> list:
    """
    解析Markdown文件，提取段落内容
    
    Args:
        content: Markdown文件内容
        
    Returns:
        段落列表，每个元素是纯文本段落
    """
    lines = content.split('\n')
    paragraphs = []
    current_para = []
    
    for line in lines:
        stripped = line.strip()
        
        if stripped.startswith('#'):
            if current_para:
                text = ' '.join(current_para).strip()
                if len(text) >= 20:
                    paragraphs.append(text)
                current_para = []
            continue
        
        if stripped.startswith('```'):
            if current_para:
                text = ' '.join(current_para).strip()
                if len(text) >= 20:
                    paragraphs.append(text)
                current_para = []
            continue
        
        if stripped.startswith(('-', '*', '+', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
            cleaned = re.sub(r'^[-*+]\s*', '', stripped)
            cleaned = re.sub(r'^\d+\.\s*', '', cleaned)
            cleaned = re.sub(r'\*\*(.+?)\*\*', r'\1', cleaned)
            cleaned = re.sub(r'\*(.+?)\*', r'\1', cleaned)
            cleaned = re.sub(r'`(.+?)`', r'\1', cleaned)
            if cleaned:
                current_para.append(cleaned)
        elif stripped.startswith('|'):
            continue
        elif stripped == '':
            if current_para:
                text = ' '.join(current_para).strip()
                text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
                text = re.sub(r'\*(.+?)\*', r'\1', text)
                text = re.sub(r'`(.+?)`', r'\1', text)
                text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
                if len(text) >= 20:
                    paragraphs.append(text)
                current_para = []
        else:
            cleaned = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
            cleaned = re.sub(r'\*(.+?)\*', r'\1', cleaned)
            cleaned = re.sub(r'`(.+?)`', r'\1', cleaned)
            cleaned = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', cleaned)
            if cleaned:
                current_para.append(cleaned)
    
    if current_para:
        text = ' '.join(current_para).strip()
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        if len(text) >= 20:
            paragraphs.append(text)
    
    return paragraphs


def parse_text(content: str) -> list:
    """
    解析纯文本文件，按空行分段
    
    Args:
        content: 文本文件内容
        
    Returns:
        段落列表
    """
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [content.strip()] if content.strip() else []
    return paragraphs


def process_file(file_path: Path, vs: VectorStore) -> int:
    """
    处理单个文件并导入知识库
    
    Args:
        file_path: 文件路径
        vs: VectorStore实例
        
    Returns:
        导入的段落数量
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        
        if not content:
            print(f"  跳过空文件: {file_path.name}")
            return 0
        
        if file_path.suffix.lower() == '.md':
            paragraphs = parse_markdown(content)
        else:
            paragraphs = parse_text(content)
        
        category = file_path.stem.replace("_", " ").title()
        
        count = 0
        for i, para in enumerate(paragraphs):
            if len(para) < 20:
                continue
            
            doc = {
                "id": f"{file_path.stem}_{i}",
                "category": category,
                "content": para,
                "source": file_path.name
            }
            
            if vs.add_document(doc):
                count += 1
                preview = para[:50] + "..." if len(para) > 50 else para
                print(f"  导入段落 {i+1}: {preview}")
        
        return count
        
    except Exception as e:
        print(f"  处理失败: {e}")
        return 0


def import_knowledge():
    """
    导入知识库到向量数据库
    """
    docs_path = Path(config.RAG.KNOWLEDGE_BASE_PATH)
    
    if not docs_path.exists():
        docs_path.mkdir(parents=True, exist_ok=True)
        print(f"已创建知识库目录: {docs_path}")
        print("请将.txt或.md文件放入该目录后重新运行此脚本")
        return 0
    
    txt_files = list(docs_path.glob("*.txt"))
    md_files = list(docs_path.glob("*.md"))
    all_files = txt_files + md_files
    
    if not all_files:
        print(f"未在 {docs_path} 中找到.txt或.md文件")
        print("请将知识文件放入该目录后重新运行")
        return 0
    
    print(f"找到 {len(txt_files)} 个.txt文件, {len(md_files)} 个.md文件")
    
    vs = VectorStore()
    
    total_count = 0
    for file_path in all_files:
        print(f"\n处理文件: {file_path.name}")
        count = process_file(file_path, vs)
        total_count += count
    
    vs.save_knowledge_base()
    
    print(f"\n导入完成！共导入 {total_count} 条知识")
    return total_count


def show_knowledge_stats():
    """
    显示知识库统计信息
    """
    vs = VectorStore()
    
    print("\n知识库统计:")
    print(f"  总文档数: {len(vs._knowledge_base)}")
    
    categories = {}
    sources = {}
    for doc in vs._knowledge_base:
        cat = doc.get("category", "unknown")
        src = doc.get("source", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
        sources[src] = sources.get(src, 0) + 1
    
    print("\n按类别统计:")
    for cat, count in categories.items():
        print(f"  {cat}: {count} 条")
    
    print("\n按来源统计:")
    for src, count in sources.items():
        print(f"  {src}: {count} 条")


def test_query(query: str = "如何缓解压力"):
    """
    测试知识库检索
    """
    vs = VectorStore()
    
    print(f"\n测试查询: {query}")
    print("-" * 50)
    
    results = vs.query(query, top_k=3)
    
    for i, r in enumerate(results):
        print(f"\n结果 {i+1}:")
        print(f"  类别: {r.get('category')}")
        print(f"  来源: {r.get('source')}")
        print(f"  内容: {r.get('content')[:100]}...")
        if "hybrid_score" in r:
            print(f"  混合得分: {r['hybrid_score']:.4f}")
        if "rerank_score" in r:
            print(f"  Rerank得分: {r['rerank_score']:.4f}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG知识库管理工具")
    parser.add_argument("--import", action="store_true", dest="import_kb", help="导入知识库")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--test", type=str, default=None, help="测试查询")
    
    args = parser.parse_args()
    
    if args.import_kb:
        import_knowledge()
    elif args.stats:
        show_knowledge_stats()
    elif args.test:
        test_query(args.test)
    else:
        print("RAG知识库管理工具")
        print("\n使用方法:")
        print("  python scripts/import_knowledge.py --import   # 导入知识库")
        print("  python scripts/import_knowledge.py --stats    # 显示统计")
        print("  python scripts/import_knowledge.py --test '如何缓解压力'  # 测试查询")
        print("\n支持格式: .txt, .md")
