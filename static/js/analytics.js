// Payment Analytics JavaScript

document.addEventListener('DOMContentLoaded', () => {
    initRevenueChart();
    initStatusChart();
});

function initRevenueChart() {
    const ctx = document.getElementById('revenueChart');
    if (!ctx) return;
    
    // Parse revenue data from template
    const revenueData = {{ revenue_by_day | tojson | default('[]') }};
    
    // Prepare data for Chart.js
    const labels = [];
    const data = [];
    
    if (revenueData && revenueData.length > 0) {
        // Sort by date
        revenueData.sort((a, b) => new Date(a.date) - new Date(b.date));
        
        revenueData.forEach(item => {
            const date = new Date(item.date);
            labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
            data.push(parseFloat(item.revenue) || 0);
        });
    } else {
        // Generate empty 30-day chart
        for (let i = 29; i >= 0; i--) {
            const date = new Date();
            date.setDate(date.getDate() - i);
            labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
            data.push(0);
        }
    }
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Revenue (₦)',
                data: data,
                borderColor: '#6750A4',
                backgroundColor: 'rgba(103, 80, 164, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    titleFont: { size: 14 },
                    bodyFont: { size: 13 },
                    callbacks: {
                        label: function(context) {
                            return '₦ ' + context.parsed.y.toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: { size: 11 },
                        maxRotation: 45,
                        minRotation: 45
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        font: { size: 11 },
                        callback: function(value) {
                            return '₦' + value.toLocaleString('en-NG');
                        }
                    }
                }
            }
        }
    });
}

function initStatusChart() {
    const ctx = document.getElementById('statusChart');
    if (!ctx) return;
    
    // Parse status data from template
    const statusData = {{ status_distribution | tojson | default('[]') }};
    
    // Prepare data for Chart.js
    const labels = [];
    const data = [];
    const colors = {
        'verified': '#AAC7FF',
        'pending': '#C1C7D0',
        'expired': '#8B919F',
        'failed': '#FFB4AB'
    };
    
    if (statusData && statusData.length > 0) {
        statusData.forEach(item => {
            const status = item.status || 'pending';
            labels.push(status.charAt(0).toUpperCase() + status.slice(1));
            data.push(item.count || 0);
        });
    } else {
        // Empty data
        labels.push('No Data');
        data.push(1);
    }
    
    const backgroundColors = statusData && statusData.length > 0 
        ? statusData.map(item => colors[item.status] || '#C1C7D0')
        : ['#C1C7D0'];
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: backgroundColors,
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        font: { size: 12 },
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    titleFont: { size: 14 },
                    bodyFont: { size: 13 },
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((context.parsed / total) * 100).toFixed(1);
                            return context.label + ': ' + context.parsed + ' (' + percentage + '%)';
                        }
                    }
                }
            }
        }
    });
}
