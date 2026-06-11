import pandas as pd
import json

# 读取时明确没有表头，所有行都是数据
df = pd.read_excel(r'D:\\projects\\self_python\\my-agent\\tests\\2.xlsx', header=None, dtype=str)

def extract_level4(cell):
    if pd.isna(cell) or str(cell).strip() == 'NULL':
        return ''
    try:
        obj = json.loads(str(cell))
        code = obj.get('level4Code', '')
        name = obj.get('level4Name', '')
        return f"{code} {name}".strip()
    except:
        return ''

# 第 4 列（索引 3）对应原来的 D 列
df['L'] = df[3].apply(extract_level4)

# 保存时也不加表头，保持原样
df.to_excel('结果数据.xlsx', index=False, header=False)
print("生成成功：结果数据.xlsx")