/* ========================================
   My Agent - 产业链功能 (边跟随拖拽版)
   ======================================== */

let industryChartInstance = null; // 保存产业链图表实例

// 资讯数据
const newsTemplates = [
    {
        category: 'AI 技术',
        headline: 'GPT-5 发布，多模态能力大幅提升',
        summary: 'OpenAI 发布 GPT-5，支持图像、视频、文本的统一理解，性能较 GPT-4 提升显著。',
        action: '了解更多',
        query: '请帮我搜索 GPT-5 的最新消息和主要改进',
        mode: 'normal'
    },
    {
        category: '行业动态',
        headline: '2024 年全球 AI 市场规模突破 5000 亿美元',
        summary: '根据最新报告，全球 AI 市场持续增长，企业级应用成为主要驱动力。',
        action: '查看详情',
        query: '请帮我分析 2024 年 AI 市场的发展状况和未来趋势',
        mode: 'complex'
    },
    {
        category: '技术教程',
        headline: 'Python 异步编程最佳实践',
        summary: '掌握 asyncio 和 async/await 语法，提升 Python 应用的并发性能。',
        action: '学习教程',
        query: '请帮我搜索 Python 异步编程的最佳实践和常见模式',
        mode: 'normal'
    },
    {
        category: '数据分析',
        headline: '数据可视化：从入门到精通',
        summary: '学习如何使用 Python 的 Matplotlib、Seaborn 和 Plotly 创建专业的数据可视化。',
        action: '开始学习',
        query: '请帮我总结 Python 数据可视化的常用工具和技巧',
        mode: 'normal'
    },
    {
        category: '云计算',
        headline: 'Serverless 架构的优势与挑战',
        summary: 'Serverless 计算正在改变应用开发方式，但也带来了新的调试和监控挑战。',
        action: '深入探讨',
        query: '请帮我分析 Serverless 架构的优缺点和适用场景',
        mode: 'complex'
    },
    {
        category: '机器学习',
        headline: 'Transformer 模型架构详解',
        summary: '深入理解 Transformer 的自注意力机制，这是现代 NLP 和大语言模型的核心。',
        action: '学习原理',
        query: '请帮我解释 Transformer 模型的工作原理和核心组件',
        mode: 'normal'
    }
];

let currentNewsIndex = 0;
const newsPerBatch = 2;  // 每次显示 2 条资讯

// 渲染资讯
function renderNews() {
    const newsGrid = document.getElementById('newsGrid');
    newsGrid.innerHTML = '';

    for (let i = 0; i < newsPerBatch; i++) {
        const news = newsTemplates[(currentNewsIndex + i) % newsTemplates.length];
        
        const newsCard = document.createElement('div');
        newsCard.className = 'news-card';
        newsCard.onclick = () => useExample(news.query, news.mode || 'normal');
        
        const badge = news.mode === 'complex' ? '<div class="news-badge">🎯 复杂任务</div>' : '';
        
        newsCard.innerHTML = `
            ${badge}
            <div class="news-category">${news.category}</div>
            <div class="news-headline">${news.headline}</div>
            <div class="news-summary">${news.summary}</div>
            <div class="news-meta">
                <span>${getRelativeTime(i)}</span>
                <span class="news-action">${news.action} →</span>
            </div>
        `;
        
        newsGrid.appendChild(newsCard);
    }
}

// 刷新资讯
function refreshNews() {
    currentNewsIndex = (currentNewsIndex + newsPerBatch) % newsTemplates.length;
    renderNews();
}

// 切换侧边栏 Tab
function switchSidebarTab(tab) {
    document.querySelectorAll('.sidebar-tab').forEach(btn => {
        btn.classList.remove('active');
    });
    
    if (tab === 'chat') {
        document.getElementById('tabChat').classList.add('active');
        document.getElementById('panelChat').classList.add('active');
        document.getElementById('panelIndustry').classList.remove('active');
        
        document.getElementById('chatView').classList.add('active');
        document.getElementById('industryView').classList.remove('active');
    } else if (tab === 'industry') {
        document.getElementById('tabIndustry').classList.add('active');
        document.getElementById('panelChat').classList.remove('active');
        document.getElementById('panelIndustry').classList.add('active');
        
        document.getElementById('chatView').classList.remove('active');
        document.getElementById('industryView').classList.add('active');
        
        loadIndustryList();
        loadQuickChips();
    }
}

// 加载产业链列表
async function loadIndustryList() {
    try {
        const token = localStorage.getItem('authToken');
        const response = await fetch(`${API_BASE_URL}/api/v1/industry/chains`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.status === 401) {
            window.location.href = 'login.html';
            return;
        }
        
        const data = await response.json();
        
        if (data.success) {
            renderIndustryList(data.chains);
        } else {
            document.getElementById('industryList').innerHTML = 
                '<div class="loading-text">加载失败</div>';
        }
    } catch (error) {
        console.error('加载产业链列表失败:', error);
        document.getElementById('industryList').innerHTML = 
            '<div class="loading-text">加载失败</div>';
    }
}

// 渲染产业链列表
function renderIndustryList(chains) {
    const container = document.getElementById('industryList');
    
    if (!chains || chains.length === 0) {
        container.innerHTML = '<div class="loading-text">暂无产业链数据</div>';
        return;
    }
    
    container.innerHTML = chains.map(chain => `
        <div class="industry-item" onclick="viewIndustryGraph('${chain}')">
            📊 ${chain}
        </div>
    `).join('');
}

// 加载快速访问芯片
function loadQuickChips() {
    const chips = ['氢能', '核能', '新能源', '储能', '航空航天', '新材料'];
    const container = document.getElementById('quickChips');
    container.innerHTML = chips.map(chip => `
        <div class="quick-chip" onclick="viewIndustryGraph('${chip}')">
            ${chip}
        </div>
    `).join('');
}

// 查看产业链图谱
async function viewIndustryGraph(industry) {
    document.querySelectorAll('.industry-item').forEach(item => {
        item.classList.remove('active');
    });
    if (event && event.target) {
        event.target.closest('.industry-item')?.classList.add('active');
    }
    
    document.getElementById('industryPlaceholder').style.display = 'none';
    document.getElementById('industryGraphFull').style.display = 'block';
    document.getElementById('industryFullTitle').textContent = `${industry}图谱`;
    document.getElementById('industryFullStats').textContent = '加载中...';
    document.getElementById('industryMainStats').textContent = `正在查询: ${industry}`;
    
    try {
        const token = localStorage.getItem('authToken');
        const response = await fetch(`${API_BASE_URL}/api/v1/industry/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                industry: industry,
                include_codes: true
            })
        });
        
        if (response.status === 401) {
            window.location.href = 'login.html';
            return;
        }
        
        const data = await response.json();
        
        if (data.success && data.graph) {
            renderIndustryGraphInMain(data.graph, industry, data.stats, data.description);
            document.getElementById('industryMainStats').textContent = 
                `${industry}: ${data.graph.nodes.length} 个环节, ${data.graph.edges.length} 个依赖关系`;
        } else {
            document.getElementById('industryFullStats').textContent = 
                `查询失败: ${data.error || '未知错误'}`;
        }
    } catch (error) {
        console.error('查询产业链失败:', error);
        document.getElementById('industryFullStats').textContent = '查询失败';
    }
}

// 在主内容区渲染产业链图谱（边跟随拖拽）
function renderIndustryGraphInMain(graphData, chainName, stats, description) {
    if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
        console.warn('图谱数据为空');
        return;
    }
    
    if (industryChartInstance) {
        industryChartInstance.dispose();
    }
    
    document.getElementById('industryFullStats').textContent = 
        `节点: ${graphData.nodes.length} | 关系: ${graphData.edges.length} | 💡 拖拽节点，边会自动跟随`;
    
    industryChartInstance = echarts.init(document.getElementById('industryFullChart'));
    
    // 为节点添加初始位置（随机位置，让力导向从这些位置开始）
    const width = document.getElementById('industryFullChart').clientWidth;
    const height = document.getElementById('industryFullChart').clientHeight;
    
    const nodesWithPositions = graphData.nodes.map((node, index) => {
        // 根据节点类别分配不同区域的初始位置
        let x, y;
        const category = node.category || '未知';
        const angle = (index / graphData.nodes.length) * Math.PI * 2;
        
        if (category === '上游') {
            x = width * 0.2 + Math.cos(angle) * 80;
            y = height * 0.3 + Math.sin(angle) * 60;
        } else if (category === '中游') {
            x = width * 0.5 + Math.cos(angle) * 100;
            y = height * 0.5 + Math.sin(angle) * 80;
        } else if (category === '下游') {
            x = width * 0.8 + Math.cos(angle) * 80;
            y = height * 0.6 + Math.sin(angle) * 60;
        } else {
            x = width * 0.5 + Math.cos(angle) * 120;
            y = height * 0.2 + Math.sin(angle) * 80;
        }
        
        return {
            id: node.id,
            name: node.name,
            category: node.category || '未知',
            symbolSize: 50,
            sequence: node.sequence || 0,
            value: node.name,
            x: Math.max(50, Math.min(width - 50, x)),
            y: Math.max(50, Math.min(height - 50, y)),
            fixed: false,
            itemStyle: {
                shadowBlur: 10,
                shadowColor: 'rgba(0, 0, 0, 0.3)'
            }
        };
    });
    
    const option = {
        tooltip: {
            trigger: 'item',
            formatter: function(params) {
                if (params.dataType === 'node') {
                    return `
                        <div style="padding: 8px;">
                            <strong>${params.data.name}</strong><br/>
                            位置: ${params.data.category || '未知'}<br/>
                            序号: ${params.data.sequence || '-'}<br/>
                            <em style="color: #999; font-size: 12px;">✨ 拖拽节点，连线自动跟随</em>
                        </div>
                    `;
                } else if (params.dataType === 'edge') {
                    return `<strong>依赖关系</strong><br/>上游 → 下游`;
                }
            }
        },
        legend: {
            data: ['上游', '中游', '下游', '消费'],
            bottom: 10,
            orient: 'horizontal',
            left: 'center'
        },
        series: [{
            type: 'graph',
            layout: 'force',
            // 关键配置：支持拖拽且边自动跟随
            roam: true,
            draggable: true,
            focusNodeAdjacency: false,
            // 力导向布局配置 - 优化拖拽体验
            force: {
                repulsion: 800,          // 增大斥力，让节点更分散
                edgeLength: [150, 250],  // 边长范围，让边有弹性
                gravity: 0.03,           // 减小重力，让拖拽更顺滑
                friction: 0.05,          // 减小摩擦力
                initIterations: 400,     // 初始迭代次数
                layoutAnimation: true,   // 布局动画
                // 重要：拖拽时降低力导向的影响
                onNodeDrag: function(node) {
                    // 拖拽时临时禁用力导向对当前节点的影响
                    node.fixed = true;
                }
            },
            // 节点数据（带初始位置）
            data: nodesWithPositions,
            // 边数据
            links: graphData.edges.map(edge => ({
                source: edge.source,
                target: edge.target,
                lineStyle: {
                    width: 2,
                    curveness: 0.2,
                    type: 'solid'
                },
                label: {
                    show: false  // 默认不显示标签，避免拥挤
                }
            })),
            // 分类
            categories: [
                {name: '上游', itemStyle: {color: '#ff6b6b'}},
                {name: '中游', itemStyle: {color: '#4ecdc4'}},
                {name: '下游', itemStyle: {color: '#45b7d1'}},
                {name: '消费', itemStyle: {color: '#96ceb4'}},
                {name: '未知', itemStyle: {color: '#999'}}
            ],
            // 标签样式
            label: {
                show: true,
                position: 'right',
                formatter: '{b}',
                fontSize: 12,
                fontWeight: 'bold',
                offset: [5, 0]
            },
            // 强调效果
            emphasis: {
                focus: 'adjacency',
                lineStyle: {
                    width: 4,
                    color: '#ffaa00'
                },
                label: {
                    show: true,
                    fontWeight: 'bold'
                }
            },
            // 边样式
            lineStyle: {
                color: 'source',
                curveness: 0.2,
                width: 2,
                opacity: 0.7
            },
            // 节点样式
            itemStyle: {
                borderColor: '#fff',
                borderWidth: 2,
                shadowBlur: 10,
                shadowColor: 'rgba(0, 0, 0, 0.3)'
            },
            // 布局完成后不自动调整
            layoutAnimation: true,
            // 边的箭头
            edgeSymbol: ['none', 'arrow'],
            edgeSymbolSize: [0, 8]
        }]
    };
    
    industryChartInstance.setOption(option);
    
    // 拖拽相关变量
    let isDragging = false;
    let draggedNodeId = null;
    
    // 拖拽开始
    industryChartInstance.on('dragstart', function(params) {
        if (params.dataType === 'node') {
            isDragging = true;
            draggedNodeId = params.data.id;
            console.log('开始拖拽节点:', params.data.name);
            
            // 高亮连接的边
            industryChartInstance.dispatchAction({
                type: 'highlight',
                seriesIndex: 0,
                name: params.data.name
            });
        }
    });
    
    // 拖拽中 - 实时更新边的位置（ECharts 自动处理，这里只做视觉反馈）
    industryChartInstance.on('drag', function(params) {
        if (params.dataType === 'node' && isDragging) {
            // ECharts 会自动更新边，我们只需要更新提示
            const currentOption = industryChartInstance.getOption();
            const seriesData = currentOption.series[0].data;
            const nodeIndex = seriesData.findIndex(n => n.id === draggedNodeId);
            
            if (nodeIndex !== -1 && params.event && params.event.event) {
                // 获取拖拽位置并更新节点坐标
                const newX = params.event.event.offsetX;
                const newY = params.event.event.offsetY;
                
                // 更新节点位置（ECharts 会自动处理边）
                seriesData[nodeIndex].x = newX;
                seriesData[nodeIndex].y = newY;
                seriesData[nodeIndex].fixed = true;
                
                // 静默更新（不触发重绘）
                industryChartInstance.setOption({
                    series: [{
                        data: seriesData
                    }]
                }, false);
            }
        }
    });
    
    // 拖拽结束
    industryChartInstance.on('dragend', function(params) {
        if (params.dataType === 'node' && params.data) {
            console.log('拖拽结束，节点:', params.data.name);
            
            const currentOption = industryChartInstance.getOption();
            const seriesData = currentOption.series[0].data;
            const nodeIndex = seriesData.findIndex(node => node.id === params.data.id);
            
            if (nodeIndex !== -1) {
                // 标记为固定，防止力导向重新调整
                seriesData[nodeIndex].fixed = true;
                seriesData[nodeIndex].itemStyle = {
                    borderColor: '#ffaa00',
                    borderWidth: 3,
                    shadowBlur: 10,
                    shadowColor: 'rgba(0, 0, 0, 0.3)'
                };
                
                industryChartInstance.setOption({
                    series: [{
                        data: seriesData
                    }]
                });
                
                // 显示提示
                showTemporaryMessage(`节点 "${params.data.name}" 已固定，连线已自动调整`);
            }
            
            // 取消高亮
            industryChartInstance.dispatchAction({
                type: 'downplay',
                seriesIndex: 0
            });
            
            isDragging = false;
            draggedNodeId = null;
        }
    });
    
    // 双击节点解除固定
    industryChartInstance.on('dblclick', function(params) {
        if (params.dataType === 'node' && params.data) {
            const currentOption = industryChartInstance.getOption();
            const seriesData = currentOption.series[0].data;
            
            const nodeIndex = seriesData.findIndex(node => node.id === params.data.id);
            if (nodeIndex !== -1 && seriesData[nodeIndex].fixed) {
                seriesData[nodeIndex].fixed = false;
                seriesData[nodeIndex].itemStyle = {
                    borderColor: '#fff',
                    borderWidth: 2,
                    shadowBlur: 10,
                    shadowColor: 'rgba(0, 0, 0, 0.3)'
                };
                
                industryChartInstance.setOption({
                    series: [{
                        data: seriesData,
                        force: {
                            initIterations: 100  // 重新进行力导向布局
                        }
                    }]
                });
                
                showTemporaryMessage(`节点 "${params.data.name}" 已解除固定，可重新布局`);
            }
        }
    });
    
    // 点击节点显示详情
    industryChartInstance.on('click', function(params) {
        if (params.dataType === 'node' && !isDragging) {
            showNodeDetail(params.data);
        }
    });
    
    // 响应式调整
    window.addEventListener('resize', function() {
        if (industryChartInstance) {
            industryChartInstance.resize();
        }
    });
    
    // 显示描述文字
    if (description) {
        const descDiv = document.getElementById('industryDescription');
        let cleanDescription = description || '';
        cleanDescription = cleanDescription.replace(/\[GRAPH_DATA_START\][\s\S]*?\[GRAPH_DATA_END\]/g, '');
        cleanDescription = cleanDescription.replace(/```json[\s\S]*?```/g, '');
        cleanDescription = cleanDescription.trim();
        
        if (typeof marked !== 'undefined' && cleanDescription) {
            descDiv.innerHTML = marked.parse(cleanDescription);
        } else {
            descDiv.textContent = cleanDescription;
        }
        descDiv.style.display = 'block';
    }
}

// 显示临时提示消息
function showTemporaryMessage(message, duration = 2000) {
    // 移除已有的提示
    const existingMsg = document.querySelector('.temp-message');
    if (existingMsg) existingMsg.remove();
    
    const msgDiv = document.createElement('div');
    msgDiv.className = 'temp-message';
    msgDiv.textContent = message;
    msgDiv.style.cssText = `
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 14px;
        z-index: 10000;
        pointer-events: none;
        animation: fadeInOut ${duration}ms ease;
    `;
    
    document.body.appendChild(msgDiv);
    
    setTimeout(() => {
        if (msgDiv.parentNode) msgDiv.remove();
    }, duration);
}

// 添加淡入淡出动画
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeInOut {
        0% { opacity: 0; transform: translateX(-50%) translateY(10px); }
        15% { opacity: 1; transform: translateX(-50%) translateY(0); }
        85% { opacity: 1; transform: translateX(-50%) translateY(0); }
        100% { opacity: 0; transform: translateX(-50%) translateY(-10px); }
    }
`;
document.head.appendChild(style);

// 显示节点详情
function showNodeDetail(node) {
    const detailHtml = `
        <div style="position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                    background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                    z-index: 10000; max-width: 350px; min-width: 250px;">
            <h3 style="margin: 0 0 10px 0; color: #333;">📌 ${node.name}</h3>
            <p><strong>🏷️ 位置:</strong> ${node.category || '未知'}</p>
            <p><strong>🔢 序号:</strong> ${node.sequence || '-'}</p>
            <p><strong>💡 提示:</strong></p>
            <ul style="margin: 5px 0; padding-left: 20px; color: #666;">
                <li>拖拽节点可移动位置</li>
                <li>连线会自动跟随节点</li>
                <li>双击节点可固定/解除位置</li>
            </ul>
            <button onclick="this.closest('.node-detail-dialog').remove()" style="margin-top: 15px; padding: 6px 20px; 
                    background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; width: 100%;">
                关闭
            </button>
        </div>
    `;
    
    const existingDialog = document.querySelector('.node-detail-dialog');
    if (existingDialog) existingDialog.remove();
    
    const dialog = document.createElement('div');
    dialog.className = 'node-detail-dialog';
    dialog.innerHTML = detailHtml;
    document.body.appendChild(dialog);
    
    dialog.addEventListener('click', function(e) {
        if (e.target === dialog) dialog.remove();
    });
}

// 搜索产业链
async function searchIndustry() {
    const keyword = document.getElementById('industrySearchInput').value.trim();
    
    if (!keyword) {
        alert('请输入产业链名称');
        return;
    }
    
    viewIndustryGraph(keyword);
}

// 渲染产业链图谱（在消息中）
function renderIndustryGraph(graphData, container) {
    if (!graphData || !graphData.graph || !graphData.graph.nodes || graphData.graph.nodes.length === 0) {
        console.warn('图谱数据为空');
        return;
    }

    const chartId = 'graph-' + Date.now();
    const graphContainer = document.createElement('div');
    graphContainer.className = 'industry-graph-container';
    graphContainer.innerHTML = `
        <div class="industry-graph-header">
            <span>📊</span>
            <span>${graphData.chain_name || '产业链'}图谱</span>
        </div>
        <div id="${chartId}" class="industry-graph-chart"></div>
        <div class="industry-graph-footer">
            <span>节点: ${graphData.graph.nodes.length} | 关系: ${graphData.graph.edges.length}</span>
            <span>✨ 拖拽节点，连线自动跟随 | 双击节点固定位置</span>
        </div>
    `;

    if (container) {
        container.appendChild(graphContainer);
    }

    const chart = echarts.init(document.getElementById(chartId));
    
    const width = graphContainer.clientWidth;
    const height = 500;
    
    const nodesWithPositions = graphData.graph.nodes.map((node, index) => {
        const category = node.category || '未知';
        const angle = (index / graphData.graph.nodes.length) * Math.PI * 2;
        let x, y;
        
        if (category === '上游') {
            x = width * 0.2 + Math.cos(angle) * 80;
            y = height * 0.3 + Math.sin(angle) * 60;
        } else if (category === '中游') {
            x = width * 0.5 + Math.cos(angle) * 100;
            y = height * 0.5 + Math.sin(angle) * 80;
        } else {
            x = width * 0.8 + Math.cos(angle) * 80;
            y = height * 0.6 + Math.sin(angle) * 60;
        }
        
        return {
            id: node.id,
            name: node.name,
            category: category,
            symbolSize: 45,
            sequence: node.sequence || 0,
            x: Math.max(40, Math.min(width - 40, x)),
            y: Math.max(40, Math.min(height - 40, y)),
            fixed: false,
            itemStyle: {
                shadowBlur: 10,
                shadowColor: 'rgba(0, 0, 0, 0.3)'
            }
        };
    });
    
    const option = {
        tooltip: {
            trigger: 'item',
            formatter: function(params) {
                if (params.dataType === 'node') {
                    return `<strong>${params.data.name}</strong><br/>位置: ${params.data.category}<br/>序号: ${params.data.sequence}`;
                }
                return '依赖关系';
            }
        },
        legend: {
            data: ['上游', '中游', '下游', '消费'],
            bottom: 10
        },
        series: [{
            type: 'graph',
            layout: 'force',
            roam: true,
            draggable: true,
            force: {
                repulsion: 600,
                edgeLength: [120, 200],
                gravity: 0.05,
                friction: 0.1,
                initIterations: 300
            },
            data: nodesWithPositions,
            links: graphData.graph.edges.map(edge => ({
                source: edge.source,
                target: edge.target,
                lineStyle: { width: 2, curveness: 0.2 }
            })),
            categories: [
                {name: '上游', itemStyle: {color: '#ff6b6b'}},
                {name: '中游', itemStyle: {color: '#4ecdc4'}},
                {name: '下游', itemStyle: {color: '#45b7d1'}},
                {name: '消费', itemStyle: {color: '#96ceb4'}}
            ],
            label: {
                show: true,
                position: 'right',
                fontSize: 11,
                fontWeight: 'bold'
            },
            lineStyle: {
                color: 'source',
                curveness: 0.2,
                width: 2
            },
            edgeSymbol: ['none', 'arrow'],
            edgeSymbolSize: [0, 8]
        }]
    };
    
    chart.setOption(option);
    
    // 拖拽结束后固定节点
    chart.on('dragend', function(params) {
        if (params.dataType === 'node') {
            const currentOption = chart.getOption();
            const seriesData = currentOption.series[0].data;
            const nodeIndex = seriesData.findIndex(n => n.id === params.data.id);
            if (nodeIndex !== -1) {
                seriesData[nodeIndex].fixed = true;
                seriesData[nodeIndex].itemStyle = {
                    borderColor: '#ffaa00',
                    borderWidth: 2,
                    shadowBlur: 10
                };
                chart.setOption({ series: [{ data: seriesData }] });
            }
        }
    });
    
    window.addEventListener('resize', () => chart.resize());
}

// 在消息中渲染图谱
function renderGraphInMessage(contentDiv, content) {
    const graphData = extractGraphData(content);
    if (graphData) {
        renderIndustryGraph(graphData.graph, contentDiv);
    }
}

// 辅助函数：获取相对时间
function getRelativeTime(index) {
    const times = ['刚刚', '5分钟前', '1小时前', '昨天'];
    return times[index % times.length];
}

// 示例函数：使用资讯查询
function useExample(query, mode) {
    console.log(`使用示例: ${query}, 模式: ${mode}`);
    // 这里调用您的对话处理函数
    if (typeof sendMessage === 'function') {
        sendMessage(query);
    }
}

// 导出函数供外部使用
window.viewIndustryGraph = viewIndustryGraph;
window.searchIndustry = searchIndustry;
window.switchSidebarTab = switchSidebarTab;
window.refreshNews = refreshNews;
window.useExample = useExample;