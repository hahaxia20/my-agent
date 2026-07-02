/* ========================================
   My Agent - App Bootstrap
   ======================================== */

document.addEventListener('DOMContentLoaded', async () => {
    if (!checkAuth()) {
        return;
    }

    if (typeof marked === 'undefined') {
        console.error('marked is not loaded');
    } else {
        console.log('marked loaded');
    }

    displayCurrentUser();
    await loadSessions();
    document.getElementById('messageInput').focus();

    console.log('My Agent initialized');
});

window.addEventListener('beforeunload', () => {
    // No teardown needed.
});

window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
});
