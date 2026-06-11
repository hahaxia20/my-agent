import csv
import re

# ================== 配置 ==================
CSV_FILE_PATH = 'D:\\projects\\self_python\\my-agent\\tests\\ce47ec6d-9653-4385-93f2-19bbdd2f9bf2.csv'
KEYWORD = '物料未关联产业链'

article_ids = set()

print("正在解析日志文件...\n")

with open(CSV_FILE_PATH, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)

    for row_num, row in enumerate(reader, 1):
        content = row.get('content', '')

        if KEYWORD not in content:
            continue

        # 从 content 中提取 articleId（支持 JSON 格式）
        match = re.search(r'"articleId"\s*:\s*"([a-z0-9]{32})"', content)
        if match:
            article_id = match.group(1)
            article_ids.add(article_id)
        else:
            # 备用匹配方式
            match2 = re.search(r'articleId["\s:]+([a-z0-9]{32})', content)
            if match2:
                article_ids.add(match2.group(1))

# ================== 输出 ==================
sorted_ids = sorted(article_ids)

print(f"✅ 提取完成！共找到 **{len(sorted_ids)}** 个 articleId\n")

print("=== SQL 查询语句（直接复制使用）===")
print("WHERE articleId IN (")
for i, aid in enumerate(sorted_ids):
    comma = ',' if i < len(sorted_ids) - 1 else ''
    print(f"  '{aid}'{comma}")
print(");")

# 保存到文件
with open('article_ids_for_sql.txt', 'w', encoding='utf-8') as f:
    f.write("WHERE articleId IN (\n")
    f.write(',\n'.join([f"  '{aid}'" for aid in sorted_ids]))
    f.write("\n);")

print("\n📁 已保存到：article_ids_for_sql.txt")
print("\n=== 纯列表（带引号）===")
print(',\n'.join([f"'{aid}'" for aid in sorted_ids]))