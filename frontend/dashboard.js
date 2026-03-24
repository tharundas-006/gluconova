const API_URL = 'http://localhost:5000/api';
let glucoseChart = null;

// Check authentication
const token = localStorage.getItem('token');
if (!token) {
    window.location.href = 'index.html';
}

// Display user name
const user = JSON.parse(localStorage.getItem('user'));
document.getElementById('userName').textContent = `Hello, ${user.name}`;

// Logout handler
document.getElementById('logoutBtn').addEventListener('click', () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = 'index.html';
});

// Fetch and display glucose readings
async function fetchGlucoseReadings() {
    try {
        const response = await fetch(`${API_URL}/glucose`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const readings = await response.json();
        updateChart(readings);
        updateRecentReadings(readings);

        if (readings.length > 0) {
            const latest = readings[0];
            document.getElementById('currentGlucose').textContent = latest.value;
            document.getElementById('lastSync').textContent = `Last sync: ${new Date(latest.timestamp).toLocaleTimeString()}`;

            // Calculate 7-day average
            const last7 = readings.slice(0, 7);
            const avg = last7.reduce((sum, r) => sum + r.value, 0) / last7.length;
            document.getElementById('avgGlucose').textContent = avg.toFixed(1);
        }
    } catch (error) {
        console.error('Error fetching readings:', error);
    }
}

// Update chart
function updateChart(readings) {
    const ctx = document.getElementById('glucoseChart').getContext('2d');
    const labels = readings.slice().reverse().map(r => new Date(r.timestamp).toLocaleDateString());
    const data = readings.slice().reverse().map(r => r.value);

    if (glucoseChart) {
        glucoseChart.data.labels = labels;
        glucoseChart.data.datasets[0].data = data;
        glucoseChart.update();
    } else {
        glucoseChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Glucose (mg/dL)',
                    data: data,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        min: 40,
                        max: 250,
                        title: { display: true, text: 'mg/dL' }
                    }
                }
            }
        });
    }
}

// Update recent readings list
function updateRecentReadings(readings) {
    const container = document.getElementById('recentReadings');
    container.innerHTML = readings.slice(0, 10).map(r => `
        <div class="reading-item">
            <span class="reading-value ${getGlucoseClass(r.value)}">${r.value} mg/dL</span>
            <span class="reading-time">${new Date(r.timestamp).toLocaleString()}</span>
        </div>
    `).join('');
}

function getGlucoseClass(value) {
    if (value > 140) return 'high';
    if (value < 70) return 'low';
    return 'normal';
}

// Simulate ESP32 reading
document.getElementById('simulateEsp32').addEventListener('click', async () => {
    try {
        const response = await fetch(`${API_URL}/esp32/simulate`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
            fetchGlucoseReadings();
            fetchInsights();
            fetchWeeklyReport();

            // Animation feedback
            const btn = document.getElementById('simulateEsp32');
            btn.style.transform = 'scale(0.95)';
            setTimeout(() => btn.style.transform = '', 200);
        }
    } catch (error) {
        console.error('Error simulating ESP32:', error);
    }
});

// Predict food impact
document.getElementById('predictFoodBtn').addEventListener('click', async () => {
    const foodName = document.getElementById('foodInput').value.trim();
    if (!foodName) {
        alert('Please enter a food name');
        return;
    }

    try {
        // First predict
        const predictResponse = await fetch(`${API_URL}/food/predict`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ food_name: foodName })
        });

        const prediction = await predictResponse.json();

        // Show prediction
        const resultDiv = document.getElementById('predictionResult');
        resultDiv.innerHTML = `
            <i class="fas fa-chart-line"></i>
            <strong>${foodName}</strong><br>
            Predicted impact: +${prediction.predicted_impact} mg/dL<br>
            <small>Logging to track actual effect...</small>
        `;
        resultDiv.classList.remove('hidden');

        // Log the food
        await fetch(`${API_URL}/food/log`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                food_name: foodName,
                predicted_impact: prediction.predicted_impact
            })
        });

        document.getElementById('foodInput').value = '';
        fetchWeeklyReport();

    } catch (error) {
        console.error('Error predicting food:', error);
    }
});

// Fetch weekly report
async function fetchWeeklyReport() {
    try {
        const response = await fetch(`${API_URL}/food/weekly-report`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const report = await response.json();
        const container = document.getElementById('weeklyReport');

        if (report.length === 0) {
            container.innerHTML = '<p class="text-muted">No meals logged this week. Use the food predictor above!</p>';
            return;
        }

        container.innerHTML = report.map(item => `
            <div class="report-item">
                <span class="report-food">${item.food}</span>
                <span class="report-impact">
                    ${item.avg_actual_impact ?
                `Actual: +${item.avg_actual_impact} mg/dL` :
                `Predicted: +${item.avg_predicted_impact} mg/dL`}
                </span>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error fetching weekly report:', error);
    }
}

// Fetch AI insights
async function fetchInsights() {
    try {
        const response = await fetch(`${API_URL}/insights`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        const data = await response.json();
        const container = document.getElementById('aiInsights');

        if (data.insights && data.insights.length > 0) {
            container.innerHTML = data.insights.map(insight => `
                <div class="insight-item">
                    <i class="fas fa-brain"></i> ${insight}
                </div>
            `).join('');
        } else {
            container.innerHTML = '<p class="text-muted">Collecting data for insights...</p>';
        }
    } catch (error) {
        console.error('Error fetching insights:', error);
    }
}

// Auto-refresh every 30 seconds
setInterval(() => {
    fetchGlucoseReadings();
    fetchInsights();
}, 30000);

// Initial load
fetchGlucoseReadings();
fetchInsights();
fetchWeeklyReport();