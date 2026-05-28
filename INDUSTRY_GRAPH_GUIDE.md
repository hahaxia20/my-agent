# 产业链图谱系统使用指南

## 📋 概述

本系统基于 Neo4j 图数据库实现产业链图谱的存储、查询和可视化，支持 12+ 个产业链的完整结构展示。

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

新增依赖：
- `neo4j==5.16.0` - Neo4j Python 驱动
- `openpyxl==3.1.2` - Excel 文件读取
- `pandas==2.1.4` - 数据处理

### 2. 启动 Neo4j

**使用 Docker（推荐）**：

```bash
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/123456 neo4j:5.16
```

**访问 Neo4j Browser**：http://localhost:7474

### 3. 配置环境变量

编辑 `.env` 文件：

```env
# Neo4j 配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j
```

### 4. 导入数据

```bash
# 方式 1：使用快速启动脚本（推荐）
python start_industry_graph.py

# 方式 2：单独导入数据
python scripts/import_industry_chains.py
```

### 5. 启动服务

```bash
python run.py
```

## 📊 支持的产业链

系统已内置以下产业链数据：

1. ✅ 核能
2. ✅ 氢能
3. ✅ 生物制造
4. ✅ 量子科技
5. ✅ 具身智能
6. ✅ 航空航天
7. ✅ 新材料
8. ✅ 大宗
9. ✅ 新能源
10. ✅ 储能
11. ✅ 6G
12. ✅ 脑机接口
13. ✅ 低空经济

## 🔌 API 接口

### 1. 查询产业链图谱

**POST** `/api/v1/industry/query`

```json
{
  "industry": "氢能",
  "include_codes": true
}
```

**响应**：

```json
{
  "success": true,
  "industry": "氢能",
  "description": "**氢能产业链** 共包含 X 个环节...",
  "graph": {
    "nodes": [
      {
        "id": "氢能_1_制氢原料与能源",
        "name": "制氢原料与能源",
        "position": "上游：制氢",
        "sequence": 1,
        "category": "上游",
        "codes": ["0610 烟煤和无烟煤开采洗选"]
      }
    ],
    "edges": [
      {
        "source": "氢能_2_制氢技术与装备",
        "target": "氢能_1_制氢原料与能源",
        "type": "depends_on",
        "label": "依赖"
      }
    ]
  },
  "stats": {
    "total_segments": 15,
    "total_positions": 4
  }
}
```

### 2. 列出所有产业链

**GET** `/api/v1/industry/chains`

**响应**：

```json
{
  "success": true,
  "chains": ["氢能", "核能", "新能源", ...],
  "count": 13
}
```

### 3. 查询上游依赖

**POST** `/api/v1/industry/upstream`

```json
{
  "industry": "氢能",
  "segment": "燃料电池系统",
  "depth": 3
}
```

### 4. 图谱统计

**GET** `/api/v1/industry/stats`

## 🤖 Agent 工具集成

系统自动注册以下工具供 Agent 使用：

### 1. `query_industry_chain`
- **功能**：查询完整产业链图谱
- **用法**：Agent 自动调用回答产业链相关问题

### 2. `list_industry_chains`
- **功能**：列出所有可用产业链
- **用法**：用户询问"有哪些产业链"时调用

### 3. `find_upstream_dependencies`
- **功能**：查找上游依赖链
- **用法**：分析供应链关系

## 💡 使用示例

### 示例 1：查询产业链

**用户**：氢能产业链有哪些环节？

**Agent**：
```
氢能产业链共包含 15 个环节，分为 4 个主要阶段：

**上游：制氢** (2个环节)
  - 制氢原料与能源
  - 制氢技术与装备

**中游：储运与加氢** (2个环节)
  - 储运技术与装备
  - 加氢站与基础设施

**中游：应用装备** (1个环节)
  - 燃料电池系统

**下游：交通应用** (1个环节)
  - 氢能交通

...

📊 产业链图谱：
[图谱数据返回给前端渲染]
```

### 示例 2：分析依赖关系

**用户**：燃料电池系统的上游依赖有哪些？

**Agent**：
```
燃料电池系统的上游依赖链（深度3层）：

层级 1（直接依赖）：
  - 储运技术与装备
  - 加氢站与基础设施

层级 2：
  - 制氢技术与装备
  - 制氢原料与能源

层级 3：
  - 煤炭、天然气、电力等基础资源

📊 依赖关系图谱：
[图谱数据返回]
```

## 🎨 前端可视化

使用 ECharts 或 AntV G6 渲染图谱：

```javascript
// 示例：ECharts 渲染
const option = {
  series: [{
    type: 'graph',
    layout: 'force',
    data: graph.nodes.map(node => ({
      name: node.name,
      category: node.category,
      value: node.sequence
    })),
    links: graph.edges,
    categories: [
      {name: '上游', itemStyle: {color: '#ff6b6b'}},
      {name: '中游', itemStyle: {color: '#4ecdc4'}},
      {name: '下游', itemStyle: {color: '#45b7d1'}},
      {name: '消费', itemStyle: {color: '#96ceb4'}}
    ],
    force: {
      repulsion: 300,
      edgeLength: 100
    }
  }]
};

chart.setOption(option);
```

## 🔍 Neo4j 查询示例

### 查看完整产业链

```cypher
MATCH (chain:IndustryChain {name: '氢能'})
-[:HAS_SEGMENT]->(segment)
RETURN segment
ORDER BY segment.sequence
```

### 查找依赖关系

```cypher
MATCH path = (a:IndustrySegment {chain: '氢能'})
-[:DEPENDS_ON*1..3]->(b)
RETURN path
```

### 统计信息

```cypher
MATCH (chain:IndustryChain)
RETURN 
  chain.name as 产业链,
  count { (chain)-[:HAS_SEGMENT]->() } as 环节数
ORDER BY 环节数 DESC
```

## 📁 项目结构

```
my-agent/
├── src/
│   ├── storage/
│   │   └── neo4j.py              # Neo4j 管理器
│   ├── tools/
│   │   └── industry_graph.py     # 图谱工具
│   └── api/routes/
│       └── industry.py           # 图谱 API
├── scripts/
│   └── import_industry_chains.py # 数据导入脚本
├── start_industry_graph.py       # 快速启动脚本
└── 产业链（结构）标签-0429.xlsx   # 源数据
```

## ⚠️ 注意事项

1. **Neo4j 版本**：推荐使用 5.x 版本
2. **内存要求**：至少 2GB RAM
3. **端口占用**：7474 (HTTP), 7687 (Bolt)
4. **数据安全**：生产环境请修改默认密码

## 🐛 常见问题

### Q: Neo4j 连接失败？
```bash
# 检查 Neo4j 是否运行
docker ps | grep neo4j

# 查看日志
docker logs neo4j
```

### Q: 导入数据失败？
```bash
# 检查 Excel 文件是否存在
ls -la "产业链（结构）标签-0429.xlsx"

# 检查 Neo4j 连接
python -c "from src.storage.neo4j import get_neo4j; print(get_neo4j())"
```

### Q: Agent 无法使用图谱工具？
```bash
# 检查工具是否注册
# 查看启动日志中的 "✅ 注册图谱工具" 信息
```

## 📞 技术支持

如有问题，请查看日志：
```bash
tail -f logs/agent.log | grep "图谱"
```
