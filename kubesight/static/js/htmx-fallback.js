// Simple HTMX-like functionality using fetch API
document.addEventListener('DOMContentLoaded', function() {
    console.log('HTMX fallback loaded');
    
    // Load initial pods
    loadPods();
});

function loadPods() {
    const namespace = document.getElementById('namespace-select')?.value || 'default';
    const search = document.getElementById('search-input')?.value || '';
    
    const params = new URLSearchParams();
    params.set('namespace', namespace);
    if (search) {
        params.set('search', search);
    }
    
    fetch('/api/pods?' + params.toString())
        .then(response => response.text())
        .then(html => {
            const podsTable = document.getElementById('pods-table');
            if (podsTable) {
                podsTable.innerHTML = html;
            }
        })
        .catch(error => {
            console.error('Error loading pods:', error);
            const podsTable = document.getElementById('pods-table');
            if (podsTable) {
                podsTable.innerHTML = '<div class="error">Failed to load pods</div>';
            }
        });
}
