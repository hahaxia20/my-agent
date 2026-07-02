/* ========================================
   My Agent - Utility Functions
   ======================================== */

const API_BASE_URL = '';

function formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    const diffMinutes = diff / 60000;
    const diffHours = diff / 3600000;
    const diffDays = diff / 86400000;

    if (diffMinutes < 1) return 'just now';
    if (diffMinutes < 60) return `${Math.floor(diffMinutes)} min ago`;
    if (diffHours < 24) return `${Math.floor(diffHours)} hr ago`;
    if (diffDays < 7) return `${Math.floor(diffDays)} day ago`;

    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
}

function scrollToBottom() {
    const container = document.getElementById('chatContainer');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

function getCurrentUser() {
    return localStorage.getItem('currentUser');
}

function displayCurrentUser() {
    const user = getCurrentUser();
    if (user) {
        document.getElementById('currentUser').textContent = user;
    }
}

function logout() {
    if (!confirm('Are you sure you want to log out?')) return;

    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    window.location.href = 'login.html';
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        sendMessage();
    }
}

function checkAuth() {
    const token = localStorage.getItem('authToken');
    if (!token) {
        window.location.href = 'login.html';
        return false;
    }
    return true;
}

function setUploadStatus(message = '', type = '') {
    const status = document.getElementById('uploadStatus');
    if (!status) return;

    status.textContent = message;
    status.className = 'upload-status';
    if (type) {
        status.classList.add(type);
    }
}
