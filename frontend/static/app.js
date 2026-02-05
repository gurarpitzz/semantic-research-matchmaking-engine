const API_URL = ""; // Assuming relative path if served by FastAPI

// Tab Switching Logic
const tabBtns = document.querySelectorAll('.tab-btn');
const sections = document.querySelectorAll('.section');

tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const tabId = btn.getAttribute('data-tab');

        tabBtns.forEach(b => b.classList.remove('active'));
        sections.forEach(s => s.classList.remove('active'));

        btn.classList.add('active');
        document.getElementById(tabId).classList.add('active');
    });
});

// UI Updates for Sliders
const limitRange = document.getElementById('limit-range');
const limitVal = document.getElementById('limit-val');
limitRange.addEventListener('input', () => {
    limitVal.textContent = limitRange.value;
});

const scoreThreshold = document.getElementById('score-threshold');
const scoreVal = document.getElementById('score-val');
scoreThreshold.addEventListener('input', () => {
    scoreVal.textContent = (scoreThreshold.value / 100).toFixed(2);
});

// Search Logic
const searchBtn = document.getElementById('search-btn');
const profileText = document.getElementById('profile-text');
const resultsContainer = document.getElementById('results-container');
const searchLoading = document.getElementById('search-loading');

searchBtn.addEventListener('click', async () => {
    const text = profileText.value.trim();
    if (!text) {
        alert("Please describe your research interests.");
        return;
    }

    resultsContainer.innerHTML = '';
    searchLoading.style.display = 'block';

    try {
        const response = await fetch(`${API_URL}/match`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_text: text,
                limit: parseInt(limitRange.value),
                min_score: parseFloat((scoreThreshold.value / 100).toFixed(2))
            })
        });

        const data = await response.json();

        if (!data || data.length === 0) {
            resultsContainer.innerHTML = '<div class="card" style="text-align: center;">No matches found. Try ingesting more data.</div>';
        } else {
            renderResults(data);
        }
    } catch (error) {
        console.error("Search failed:", error);
        resultsContainer.innerHTML = `<div class="card" style="border-color: #ef4444; color: #ef4444;">Error connecting to API. Ensure backend is running.</div>`;
    } finally {
        searchLoading.style.display = 'none';
    }
});

function renderResults(matches) {
    resultsContainer.innerHTML = matches.map(match => `
        <div class="match-item">
            <div class="match-header">
                <div class="prof-info">
                    <h3>👤 ${match.professor}</h3>
                    <p class="prof-meta">${match.university} ${match.email ? `• <a href="mailto:${match.email}" class="email-link">${match.email}</a>` : ''}</p>
                </div>
                <div class="score-badge">SCORE ${match.max_score.toFixed(2)}</div>
            </div>
            
            <div class="papers-list">
                <h4>Top Matching Papers</h4>
                ${match.papers.map(p => `
                    <div class="paper-item">
                        <p><strong>${p.url ? `<a href="${p.url}" target="_blank" class="paper-link">📄 ${p.title}</a>` : `📄 ${p.title}`}</strong></p>
                        <p class="paper-meta">Year: ${p.year} • Similarity: ${p.score.toFixed(4)}</p>
                    </div>
                `).join('')}
            </div>
            
            <div class="reasoning">
                <strong>Match Insight:</strong> High semantic overlap detected in research domains. 
                Full LLM justification is being computed in the background.
            </div>
        </div>
    `).join('');
}

// Ingest Logic
const ingestBtn = document.getElementById('ingest-btn');
const uniName = document.getElementById('uni-name');
const deptUrl = document.getElementById('dept-url');
const ingestStatus = document.getElementById('ingest-status');

ingestBtn.addEventListener('click', async () => {
    const university = uniName.value.trim();
    const url = deptUrl.value.trim();

    if (!university || !url) {
        alert("Please provide both University Name and Directory URL.");
        return;
    }

    ingestStatus.textContent = "⚙️ Triggering ingestion worker...";
    ingestStatus.style.color = "var(--accent-color)";

    try {
        const response = await fetch(`${API_URL}/ingest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ university, dept_url: url })
        });
        const data = await response.json();
        ingestStatus.textContent = `✅ Successfully queued.`;

        // Start polling for progress
        startProgressPolling(data.task_id);
    } catch (error) {
        ingestStatus.textContent = "❌ Failed to queue ingestion job.";
        ingestStatus.style.color = "#ef4444";
    }
});

let pollingTimer = null;
let activeJobId = null;

function startProgressPolling(jobId) {
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');
    const progressStatus = document.getElementById('progress-status');
    const progressDetail = document.getElementById('progress-detail');

    // Atomic Lock: Only this jobId is allowed to update the UI from now on
    activeJobId = jobId;
    if (pollingTimer) clearTimeout(pollingTimer);

    progressContainer.style.display = 'block';
    // Reset bar for new job
    progressBar.style.width = '0%';
    progressBar.style.background = 'var(--primary)';
    progressPercent.textContent = '0%';

    const poll = async () => {
        // Ghost Loop Prevention: Stop if this job is no longer active
        if (jobId !== activeJobId) return;

        try {
            const response = await fetch(`${API_URL}/job/${jobId}`);
            if (!response.ok) throw new Error("Job not found");

            const data = await response.json();

            // Calculate percentage
            const percent = data.total_faculty > 0 ? Math.round((data.processed_faculty / data.total_faculty) * 100) : 0;
            progressBar.style.width = `${percent}%`;
            progressPercent.textContent = `${percent}%`;

            if (data.status === 'processing' || data.status === 'queued') {
                progressStatus.textContent = data.status === 'queued' ? '🕒 Job Queued...' : `Processing ${data.university}...`;
                progressDetail.innerHTML = `
                    Analyzing ${data.processed_faculty} of ${data.total_faculty} faculty members. 
                    <br><strong style="color:#10b981">✨ ${data.processed_faculty} researchers are already indexed and searchable!</strong>
                    <br><button class="secondary" onclick="document.querySelector('[data-tab=search]').click()" style="margin-top:0.5rem; font-size:0.75rem; padding:4px 8px;">🔍 Search Partial Results Now</button>
                `;
                pollingTimer = setTimeout(poll, 3000);
            } else if (data.status === 'completed') {
                progressStatus.textContent = `✅ Ingestion Complete!`;
                progressDetail.textContent = `All ${data.total_faculty} faculty members and their papers have been indexed.`;
                progressBar.style.background = '#10b981';
                progressBar.style.width = '100%';
                progressPercent.textContent = '100%';
                pollingTimer = null;
            } else if (data.status === 'failed') {
                progressStatus.textContent = `⚠️ Ingestion Interrupted (Partially Indexed)`;
                progressDetail.innerHTML = `
                    The process hit a snag at ${data.processed_faculty}/${data.total_faculty}. 
                    <br>Don't worry, the researchers already processed are saved and searchable.
                    <br><button class="primary" onclick="document.querySelector('[data-tab=search]').click()" style="margin-top:0.5rem;">Go to Search</button>
                `;
                progressBar.style.background = '#f59e0b';
                pollingTimer = null;
            }
        } catch (e) {
            console.error("Polling error:", e);
            pollingTimer = setTimeout(poll, 5000);
        }
    };

    poll();
}
