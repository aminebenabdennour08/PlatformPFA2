// Global utility functions
function formatDate(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('fr-FR');
}

function formatConfidence(confidence) {
    if (!confidence) return '-';
    return (confidence * 100).toFixed(1) + '%';
}

function getClassLabel(classId) {
    const labels = {
        'adenocarcinoma': 'Adénocarcinome',
        'large.cell.carcinoma': 'Carcinome à grandes cellules',
        'squamous.cell.carcinoma': 'Carcinome épidermoïde',
        'normal': 'Normal'
    };
    return labels[classId] || classId;
}

// Auto-refresh data every 30 seconds if on dashboard
if (window.location.pathname === '/dashboard') {
    setInterval(() => {
        location.reload();
    }, 30000);
}