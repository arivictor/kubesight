// KubeSight Application JavaScript

// Auto-refresh functionality
let autoRefreshInterval = null;

function enableAutoRefresh(intervalSeconds = 30) {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    autoRefreshInterval = setInterval(() => {
        refreshPods();
    }, intervalSeconds * 1000);
    
    console.log(`Auto-refresh enabled (${intervalSeconds}s)`);
}

function disableAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        console.log('Auto-refresh disabled');
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Escape to close modal
    if (e.key === 'Escape') {
        closeModal();
    }
    
    // Ctrl+R or Cmd+R to refresh (prevent default browser refresh)
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        refreshPods();
    }
});

// Error handling for fetch requests
function handleFetchError(error) {
    console.error('Fetch error:', error);
    
    // Show user-friendly error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error';
    errorDiv.style.position = 'fixed';
    errorDiv.style.top = '20px';
    errorDiv.style.right = '20px';
    errorDiv.style.zIndex = '9999';
    errorDiv.style.maxWidth = '400px';
    errorDiv.textContent = `Error: ${error.message}`;
    
    document.body.appendChild(errorDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('KubeSight initialized');
    
    // Optional: Enable auto-refresh (uncomment to enable)
    // enableAutoRefresh(30);
});
