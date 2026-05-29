/* ========================================
   My Agent - 工具函数
   ======================================== */

// API 基础配置
const API_BASE_URL = 'http://localhost:8001';

// 格式化时间
function formatTime(timestamp) {
    // MongoDB 返回的是 UTC 时间字符串
    const date = new Date(timestamp);
    const now = new Date();

    // 计算时间差（毫秒）
    const diff = now - date;

    // 转换为分钟
    const diffMinutes = diff / 60000;
    const diffHours = diff / 3600000;
    const diffDays = diff / 86400000;

    if (diffMinutes < 1) return '刚刚';
    if (diffMinutes < 60) return `${Math.floor(diffMinutes)}分钟前`;
    if (diffHours < 24) return `${Math.floor(diffHours)}小时前`;
    if (diffDays < 7) return `${Math.floor(diffDays)}天前`;

    // 超过7天显示具体日期
    return date.toLocaleDateString('zh-CN', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 获取相对时间（模拟）
function getRelativeTime(index) {
    const times = ['刚刚', '5分钟前', '10分钟前', '15分钟前', '20分钟前', '30分钟前'];
    return times[index % times.length];
}

// 自动调整文本框高度
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

// 滚动到底部
function scrollToBottom() {
    const container = document.getElementById('chatContainer');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

// 切换侧边栏（移动端）
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

// 获取当前用户
function getCurrentUser() {
    return localStorage.getItem('currentUser');
}

// 显示当前用户
function displayCurrentUser() {
    const user = getCurrentUser();
    if (user) {
        document.getElementById('currentUser').textContent = `👤 ${user}`;
    }
}

// 退出登录
function logout() {
    if (!confirm('确定要退出登录吗？')) return;

    // 清除登录信息
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');

    // 跳转到登录页
    window.location.href = 'login.html';
}

// 处理键盘事件
function handleKeyDown(event) {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        sendMessage();
    }
}

// 检查登录状态
function checkAuth() {
    const token = localStorage.getItem('authToken');
    if (!token) {
        window.location.href = 'login.html';
        return false;
    }
    return true;
}

