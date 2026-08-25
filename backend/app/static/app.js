/**
 * Moodometer Frontend JavaScript
 * 
 * Handles user interactions, mood submission, authentication, and data visualization
 */

// Global state
let currentUser = null;
let authToken = null;

// API Base URL
const API_BASE = window.location.origin;

// ==================== Authentication Functions ====================

/**
 * Show/hide UI elements based on authentication state
 */
function updateUIForAuthState() {
    const loginSection = document.getElementById('login-section');
    const moodboardSection = document.getElementById('moodboard-section');
    const userInfo = document.getElementById('user-info');
    const historySection = document.getElementById('history-section');
    
    if (currentUser && authToken) {
        loginSection.style.display = 'none';
        moodboardSection.style.display = 'block';
        historySection.style.display = 'block';
        userInfo.innerHTML = `
            <span>${currentUser}</span>
            <button class="btn-logout" onclick="logout()">Logout</button>
        `;
    } else {
        loginSection.style.display = 'block';
        moodboardSection.style.display = 'none';
        historySection.style.display = 'none';
        userInfo.innerHTML = '';
    }
}

/**
 * Handle user login
 */
async function login() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('login-error');
    
    if (!username || !password) {
        errorDiv.textContent = 'Please enter username and password';
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);
        
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }
        
        const data = await response.json();
        authToken = data.access_token;
        currentUser = username;
        
        // Store in sessionStorage
        sessionStorage.setItem('authToken', authToken);
        sessionStorage.setItem('currentUser', currentUser);
        
        errorDiv.textContent = '';
        updateUIForAuthState();
        loadMoodHistory();
        loadEntries();
    } catch (error) {
        errorDiv.textContent = error.message;
    }
}

/**
 * Handle user logout
 */
async function logout() {
    try {
        await fetch(`${API_BASE}/auth/logout`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
    } catch (error) {
        console.error('Logout error:', error);
    }
    
    authToken = null;
    currentUser = null;
    sessionStorage.removeItem('authToken');
    sessionStorage.removeItem('currentUser');
    
    updateUIForAuthState();
}

/**
 * Handle user registration
 */
async function register() {
    const username = document.getElementById('reg-username').value;
    const password = document.getElementById('reg-password').value;
    const errorDiv = document.getElementById('register-error');
    
    if (!username || !password) {
        errorDiv.textContent = 'Please enter username and password';
        return;
    }
    
    if (password.length < 8) {
        errorDiv.textContent = 'Password must be at least 8 characters';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/users`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
        }
        
        errorDiv.textContent = '';
        errorDiv.style.color = 'green';
        errorDiv.textContent = 'Registration successful! Please login.';
        
        // Clear form
        document.getElementById('reg-username').value = '';
        document.getElementById('reg-password').value = '';
        
        // Switch to login tab
        setTimeout(() => {
            switchTab('login');
            errorDiv.textContent = '';
            errorDiv.style.color = 'red';
        }, 1500);
    } catch (error) {
        errorDiv.style.color = 'red';
        errorDiv.textContent = error.message;
    }
}

// ==================== Mood Submission Functions ====================

/**
 * Submit a mood entry
 */
async function submitMood(energy, valence, moodText) {
    if (!authToken || !currentUser) {
        alert('Please login first');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/users/${currentUser}/moods`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                energy: energy,
                valence: valence,
                timestamp: new Date().toISOString()
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to submit mood');
        }
        
        // Show success message
        showNotification(`Mood "${moodText}" recorded!`, 'success');
        
        // Reload mood history
        loadMoodHistory();
    } catch (error) {
        showNotification(error.message, 'error');
    }
}

/**
 * Handle mood zone clicks
 */
function setupMoodZoneHandlers() {
    // Map mood zones to energy/valence values
    const moodZones = {
        'top-left': { energy: 0.7, valence: -0.7, text: 'Fuck it we ball' },
        'top-right': { energy: 0.7, valence: 0.7, text: 'We are so fucking back' },
        'tr-child': { energy: 0.9, valence: 0.9, text: "Let's fucking goooo" },
        'bottom-left': { energy: -0.7, valence: -0.7, text: 'It is what it is' },
        'bl-child': { energy: -0.8, valence: -0.8, text: "It's so over" },
        'bl-grandchild': { energy: -0.9, valence: -0.9, text: 'Mom would be sad' },
        'bottom-right': { energy: -0.7, valence: 0.7, text: 'We vibing' }
    };
    
    Object.keys(moodZones).forEach(zoneId => {
        const element = document.getElementById(zoneId);
        if (element) {
            element.onclick = (e) => {
                e.stopPropagation();
                const zone = moodZones[zoneId];
                submitMood(zone.energy, zone.valence, zone.text);
            };
        }
    });
}

// ==================== History Functions ====================

/**
 * Load and display mood history
 */
async function loadMoodHistory() {
    if (!authToken || !currentUser) return;
    
    try {
        const response = await fetch(`${API_BASE}/users/${currentUser}/moods?limit=10`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (!response.ok) throw new Error('Failed to load mood history');
        
        const moods = await response.json();
        displayMoodHistory(moods);
    } catch (error) {
        console.error('Error loading mood history:', error);
    }
}

/**
 * Display mood history in the UI
 */
function displayMoodHistory(moods) {
    const container = document.getElementById('mood-history');
    if (!container) return;
    
    if (moods.length === 0) {
        container.innerHTML = '<p>No mood entries yet. Click on the mood board to record your first mood!</p>';
        return;
    }
    
    container.innerHTML = moods.map(mood => {
        const date = new Date(mood.timestamp).toLocaleString();
        const quadrant = getMoodQuadrant(mood.energy, mood.valence);
        return `
            <div class="mood-entry">
                <div class="mood-date">${date}</div>
                <div class="mood-quadrant">${quadrant}</div>
                <div class="mood-values">Energy: ${mood.energy.toFixed(2)}, Valence: ${mood.valence.toFixed(2)}</div>
            </div>
        `;
    }).join('');
}

/**
 * Get mood quadrant name from energy/valence values
 */
function getMoodQuadrant(energy, valence) {
    if (energy > 0 && valence > 0) return '🚀 High Energy + Pleasant';
    if (energy > 0 && valence < 0) return '⚡ High Energy + Unpleasant';
    if (energy < 0 && valence > 0) return '😌 Low Energy + Pleasant';
    if (energy < 0 && valence < 0) return '😔 Low Energy + Unpleasant';
    return '😐 Neutral';
}

// ==================== Journal Entry Functions ====================

/**
 * Submit a journal entry
 */
async function submitEntry() {
    const content = document.getElementById('entry-content').value;
    const errorDiv = document.getElementById('entry-error');
    
    if (!content.trim()) {
        errorDiv.textContent = 'Please enter some text';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/users/${currentUser}/entries`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                content: content,
                timestamp: new Date().toISOString()
            })
        });
        
        if (!response.ok) throw new Error('Failed to submit entry');
        
        document.getElementById('entry-content').value = '';
        errorDiv.textContent = '';
        showNotification('Journal entry saved!', 'success');
        loadEntries();
    } catch (error) {
        errorDiv.textContent = error.message;
    }
}

/**
 * Load and display journal entries
 */
async function loadEntries() {
    if (!authToken || !currentUser) return;
    
    try {
        const response = await fetch(`${API_BASE}/users/${currentUser}/entries?limit=5`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (!response.ok) throw new Error('Failed to load entries');
        
        const entries = await response.json();
        displayEntries(entries);
    } catch (error) {
        console.error('Error loading entries:', error);
    }
}

/**
 * Display journal entries in the UI
 */
function displayEntries(entries) {
    const container = document.getElementById('entries-list');
    if (!container) return;
    
    if (entries.length === 0) {
        container.innerHTML = '<p>No journal entries yet.</p>';
        return;
    }
    
    container.innerHTML = entries.map(entry => {
        const date = new Date(entry.timestamp).toLocaleString();
        return `
            <div class="entry-item">
                <div class="entry-date">${date}</div>
                <div class="entry-content">${escapeHtml(entry.content)}</div>
            </div>
        `;
    }).join('');
}

// ==================== Utility Functions ====================

/**
 * Show notification message
 */
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Switch between login/register tabs
 */
function switchTab(tabName) {
    const tabs = document.querySelectorAll('.tab-content');
    const buttons = document.querySelectorAll('.tab-button');
    
    tabs.forEach(tab => {
        tab.classList.remove('active');
    });
    
    buttons.forEach(button => {
        button.classList.remove('active');
    });
    
    document.getElementById(`${tabName}-tab`).classList.add('active');
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
}

// ==================== Initialization ====================

/**
 * Initialize the application
 */
function init() {
    // Check for existing session
    const storedToken = sessionStorage.getItem('authToken');
    const storedUser = sessionStorage.getItem('currentUser');
    
    if (storedToken && storedUser) {
        authToken = storedToken;
        currentUser = storedUser;
    }
    
    updateUIForAuthState();
    setupMoodZoneHandlers();
    
    if (currentUser && authToken) {
        loadMoodHistory();
        loadEntries();
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Made with Bob

// ==================== Data Visualization with Chart.js ====================

// Chart instances
let moodTrendChart = null;
let moodDistributionChart = null;
let moodScatterChart = null;

/**
 * Initialize all charts
 */
function initializeCharts() {
    // Create trend chart
    const trendCtx = document.getElementById('mood-trend-chart');
    if (trendCtx) {
        moodTrendChart = new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Energy',
                    data: [],
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255, 107, 107, 0.1)',
                    tension: 0.4
                }, {
                    label: 'Valence',
                    data: [],
                    borderColor: '#4ecdc4',
                    backgroundColor: 'rgba(78, 205, 196, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    title: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 10,
                        title: {
                            display: true,
                            text: 'Score'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Date'
                        }
                    }
                }
            }
        });
    }

    // Create distribution chart
    const distCtx = document.getElementById('mood-distribution-chart');
    if (distCtx) {
        moodDistributionChart = new Chart(distCtx, {
            type: 'bar',
            data: {
                labels: ['Stressed', 'Sad', 'Tired', 'Calm', 'Content', 'Relaxed', 'Happy', 'Excited', 'Energized'],
                datasets: [{
                    label: 'Mood Count',
                    data: [0, 0, 0, 0, 0, 0, 0, 0, 0],
                    backgroundColor: [
                        '#e74c3c', '#c0392b', '#95a5a6',
                        '#3498db', '#2ecc71', '#27ae60',
                        '#f39c12', '#e67e22', '#d35400'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        },
                        title: {
                            display: true,
                            text: 'Frequency'
                        }
                    }
                }
            }
        });
    }

    // Create scatter chart
    const scatterCtx = document.getElementById('mood-scatter-chart');
    if (scatterCtx) {
        moodScatterChart = new Chart(scatterCtx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Mood Points',
                    data: [],
                    backgroundColor: 'rgba(78, 205, 196, 0.6)',
                    borderColor: '#4ecdc4',
                    pointRadius: 6,
                    pointHoverRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Energy: ${context.parsed.y}, Valence: ${context.parsed.x}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        min: 0,
                        max: 10,
                        title: {
                            display: true,
                            text: 'Valence (Negative ← → Positive)'
                        }
                    },
                    y: {
                        min: 0,
                        max: 10,
                        title: {
                            display: true,
                            text: 'Energy (Low ← → High)'
                        }
                    }
                }
            }
        });
    }
}

/**
 * Update all charts with mood data
 */
async function updateCharts() {
    const username = localStorage.getItem('username');
    const token = localStorage.getItem('token');
    
    if (!username || !token) {
        return;
    }

    try {
        // Get selected date range
        const rangeSelect = document.getElementById('chart-range');
        const days = rangeSelect ? rangeSelect.value : '30';
        
        // Fetch mood history
        const response = await fetch(`${API_BASE}/users/${username}/moods`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error('Failed to fetch mood data');
        }

        const moods = await response.json();
        
        // Filter by date range
        let filteredMoods = moods;
        if (days !== 'all') {
            const cutoffDate = new Date();
            cutoffDate.setDate(cutoffDate.getDate() - parseInt(days));
            filteredMoods = moods.filter(mood => new Date(mood.timestamp) >= cutoffDate);
        }

        // Sort by timestamp
        filteredMoods.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        // Update trend chart
        if (moodTrendChart) {
            const labels = filteredMoods.map(m => new Date(m.timestamp).toLocaleDateString());
            const energyData = filteredMoods.map(m => m.energy);
            const valenceData = filteredMoods.map(m => m.valence);

            moodTrendChart.data.labels = labels;
            moodTrendChart.data.datasets[0].data = energyData;
            moodTrendChart.data.datasets[1].data = valenceData;
            moodTrendChart.update();
        }

        // Update distribution chart
        if (moodDistributionChart) {
            const moodCounts = {
                'Stressed': 0, 'Sad': 0, 'Tired': 0,
                'Calm': 0, 'Content': 0, 'Relaxed': 0,
                'Happy': 0, 'Excited': 0, 'Energized': 0
            };

            filteredMoods.forEach(mood => {
                if (moodCounts.hasOwnProperty(mood.mood)) {
                    moodCounts[mood.mood]++;
                }
            });

            moodDistributionChart.data.datasets[0].data = Object.values(moodCounts);
            moodDistributionChart.update();
        }

        // Update scatter chart
        if (moodScatterChart) {
            const scatterData = filteredMoods.map(m => ({
                x: m.valence,
                y: m.energy
            }));

            moodScatterChart.data.datasets[0].data = scatterData;
            moodScatterChart.update();
        }

    } catch (error) {
        console.error('Error updating charts:', error);
    }
}

// Initialize charts when page loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => {
            initializeCharts();
            updateCharts();
        }, 1000);
    });
} else {
    setTimeout(() => {
        initializeCharts();
        updateCharts();
    }, 1000);
}
