// AICTE Integrated Complaint Monitoring & Overlap Dashboard SPA
// Real-time polling every 5 seconds, Government-grade UI, Role-based Access

const API_BASE = "http://" + window.location.host;

const DEMO_USERS = [
  { email: "management@aicte.gov.in", name: "Prof. T. G. Sitharam", role: "Senior Management", bureau: "All", region: "All" },
  { email: "rb_officer@aicte.gov.in", name: "Dr. Rajesh Sharma", role: "RB Officer", bureau: "RB", region: "All" },
  { email: "pgrc_officer@aicte.gov.in", name: "Smt. Sunita Rao", role: "PGRC Officer", bureau: "PGRC", region: "All" },
  { email: "regional_south@aicte.gov.in", name: "Shri K. Ramanathan", role: "Regional Officer", bureau: "RO", region: "Southern" },
  { email: "ab_officer@aicte.gov.in", name: "Dr. Anita Verma", role: "Approval Bureau Officer", bureau: "AB", region: "All" }
];

// App State
let state = {
  user: JSON.parse(localStorage.getItem("aicte_user")) || DEMO_USERS[0],
  token: localStorage.getItem("aicte_token") || "management@aicte.gov.in:Senior Management:1700000000",
  currentScreen: "dashboard", // dashboard, cases, case-detail, institution, overlaps, new-case, reports, login
  selectedCaseId: null,
  selectedInstitutionId: null,
  dashboardData: null,
  alertsData: [],
  casesList: [],
  currentCase: null,
  currentInstitution: null,
  overlapList: [],
  reportType: "bureau-wise",
  reportData: null,
  filters: {
    search: "",
    bureau: "All",
    category: "All",
    status: "All",
    region: "All",
    is_overdue: false,
    has_overlap: false
  },
  modal: null, // { type: 'action', caseId: 123 } or { type: 'overlap_result', data: {} }
  lastUpdated: new Date()
};

// API Helper
async function api(endpoint, method = "GET", data = null) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  
  const options = { method, headers };
  if (data && method !== "GET") options.body = JSON.stringify(data);
  
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, options);
    if (!res.ok) {
      if (res.status === 401) {
        state.user = null;
        state.token = null;
        localStorage.removeItem("aicte_user");
        localStorage.removeItem("aicte_token");
        navigateTo("login");
      }
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP Error ${res.status}`);
    }
    return await res.json();
  } catch (e) {
    console.error("API Call Failed:", endpoint, e);
    throw e;
  }
}

// Navigation
function navigateTo(screen, params = {}) {
  state.currentScreen = screen;
  if (params.caseId) state.selectedCaseId = params.caseId;
  if (params.institutionId) state.selectedInstitutionId = params.institutionId;
  render();
  loadScreenData();
}

// Data loaders
async function loadScreenData() {
  try {
    if (state.currentScreen === "dashboard") {
      const [dash, alerts] = await Promise.all([
        api("/api/dashboard/summary"),
        api("/api/alerts")
      ]);
      state.dashboardData = dash;
      state.alertsData = alerts;
      render();
      renderCharts();
    } else if (state.currentScreen === "cases") {
      let q = `/api/cases?bureau=${state.filters.bureau}&category=${state.filters.category}&status=${state.filters.status}&region=${state.filters.region}`;
      if (state.filters.search) q += `&search=${encodeURIComponent(state.filters.search)}`;
      if (state.filters.is_overdue) q += `&is_overdue=true`;
      if (state.filters.has_overlap) q += `&has_overlap=true`;
      state.casesList = await api(q);
      render();
    } else if (state.currentScreen === "case-detail" && state.selectedCaseId) {
      state.currentCase = await api(`/api/cases/${state.selectedCaseId}`);
      render();
    } else if (state.currentScreen === "institution" && state.selectedInstitutionId) {
      state.currentInstitution = await api(`/api/institutions/${state.selectedInstitutionId}`);
      render();
    } else if (state.currentScreen === "overlaps") {
      state.overlapList = await api("/api/overlaps");
      render();
    } else if (state.currentScreen === "reports") {
      state.reportData = await api(`/api/reports/${state.reportType}`);
      render();
      renderReportCharts();
    }
    state.lastUpdated = new Date();
  } catch (err) {
    console.warn("Screen data loading error:", err);
  }
}

// Real-Time Polling Engine (Every 5 seconds)
setInterval(async () => {
  if (state.currentScreen === "login") return;
  try {
    const alerts = await api("/api/alerts");
    state.alertsData = alerts;
    if (state.currentScreen === "dashboard") {
      state.dashboardData = await api("/api/dashboard/summary");
      render();
      renderCharts();
    } else if (state.currentScreen === "cases") {
      // Refresh cases list seamlessly
      let q = `/api/cases?bureau=${state.filters.bureau}&category=${state.filters.category}&status=${state.filters.status}&region=${state.filters.region}`;
      if (state.filters.search) q += `&search=${encodeURIComponent(state.filters.search)}`;
      if (state.filters.is_overdue) q += `&is_overdue=true`;
      if (state.filters.has_overlap) q += `&has_overlap=true`;
      state.casesList = await api(q);
      render();
    }
    state.lastUpdated = new Date();
    const updateEl = document.getElementById("last-updated-time");
    if (updateEl) updateEl.innerText = state.lastUpdated.toLocaleTimeString();
  } catch (e) {
    // Silent background poll error handler
  }
}, 5000);

// Switch user role (1-click for hackathon demo)
function switchUser(email) {
  const found = DEMO_USERS.find(u => u.email === email);
  if (found) {
    state.user = found;
    state.token = `${found.email}:${found.role}:9999999999`;
    localStorage.setItem("aicte_user", JSON.stringify(found));
    localStorage.setItem("aicte_token", state.token);
    navigateTo("dashboard");
  }
}

// Render Top Navbar
function renderNavbar() {
  const u = state.user || {};
  return `
    <header class="bg-[#0b2545] text-white shadow-lg sticky top-0 z-40 border-b border-amber-500/40">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          
          <!-- Logo & Brand -->
          <div class="flex items-center space-x-3 cursor-pointer" onclick="navigateTo('dashboard')">
            <div class="w-10 h-10 rounded-full bg-white flex items-center justify-center p-1 shadow-inner border border-amber-400">
              <svg viewBox="0 0 100 100" class="w-8 h-8">
                <circle cx="50" cy="50" r="45" fill="#0b2545" stroke="#ff9933" stroke-width="4"/>
                <circle cx="50" cy="50" r="28" fill="#fff"/>
                <circle cx="50" cy="50" r="20" fill="#138808"/>
                <path d="M50 20 L50 80 M20 50 L80 50" stroke="#ff9933" stroke-width="3"/>
                <text x="50" y="55" font-size="12" font-weight="bold" fill="#fff" text-anchor="middle">AICTE</text>
              </svg>
            </div>
            <div>
              <div class="text-xs font-semibold tracking-wider text-amber-400 uppercase">Government of India &bull; Ministry of Education</div>
              <div class="text-base font-bold tracking-tight text-white flex items-center gap-2">
                All India Council for Technical Education
                <span class="text-xs font-normal bg-blue-900/80 text-blue-200 px-2 py-0.5 rounded border border-blue-700">Central Portal</span>
              </div>
            </div>
          </div>

          <!-- Navigation Links -->
          <nav class="hidden md:flex space-x-1 font-medium text-sm">
            <button onclick="navigateTo('dashboard')" class="px-3 py-2 rounded-md ${state.currentScreen === 'dashboard' ? 'bg-amber-500 text-slate-900 font-bold' : 'hover:bg-slate-800 text-slate-200'}">
              Dashboard
            </button>
            <button onclick="navigateTo('cases')" class="px-3 py-2 rounded-md ${state.currentScreen === 'cases' ? 'bg-amber-500 text-slate-900 font-bold' : 'hover:bg-slate-800 text-slate-200'}">
              Grievance Cases
            </button>
            <button onclick="navigateTo('overlaps')" class="relative px-3 py-2 rounded-md ${state.currentScreen === 'overlaps' ? 'bg-amber-500 text-slate-900 font-bold' : 'hover:bg-slate-800 text-slate-200'}">
              Overlap Center
              ${state.dashboardData && state.dashboardData.open_overlaps_count > 0 ? `
                <span class="absolute -top-1 -right-1 bg-red-600 text-white font-bold text-xs px-1.5 py-0.2 rounded-full border border-white pulse-dot">
                  ${state.dashboardData.open_overlaps_count}
                </span>
              ` : ''}
            </button>
            <button onclick="navigateTo('new-case')" class="px-3 py-2 rounded-md ${state.currentScreen === 'new-case' ? 'bg-amber-500 text-slate-900 font-bold' : 'hover:bg-slate-800 text-slate-200'}">
              + Register Case
            </button>
            <button onclick="navigateTo('reports')" class="px-3 py-2 rounded-md ${state.currentScreen === 'reports' ? 'bg-amber-500 text-slate-900 font-bold' : 'hover:bg-slate-800 text-slate-200'}">
              Reports & Audit
            </button>
          </nav>

          <!-- User Role Switcher & Live Polling Indicator -->
          <div class="flex items-center space-x-3">
            <div class="hidden lg:flex items-center space-x-2 text-xs bg-slate-900/70 border border-slate-700 px-2.5 py-1.5 rounded-full text-slate-300">
              <span class="w-2 h-2 rounded-full bg-emerald-400 pulse-dot"></span>
              <span>5s Sync: <strong id="last-updated-time" class="text-white">${state.lastUpdated.toLocaleTimeString()}</strong></span>
            </div>

            <!-- Role Selector Dropdown -->
            <div class="relative inline-block text-left">
              <select onchange="switchUser(this.value)" class="bg-slate-900 border border-amber-500/50 text-white text-xs rounded-lg px-2.5 py-1.5 focus:ring-2 focus:ring-amber-400 font-medium">
                ${DEMO_USERS.map(u => `
                  <option value="${u.email}" ${state.user && state.user.email === u.email ? 'selected' : ''}>
                    ${u.role} (${u.name.split(' ')[0]})
                  </option>
                `).join('')}
              </select>
            </div>

            <button onclick="navigateTo('login')" class="text-xs bg-red-950/40 text-red-300 hover:bg-red-900 px-2.5 py-1.5 rounded border border-red-800">
              Logout
            </button>
          </div>
        </div>
      </div>
    </header>
  `;
}

// Screen 1: Dashboard
function renderDashboard() {
  const d = state.dashboardData || {
    total_cases: 0, received_count: 0, under_process_count: 0,
    pending_count: 0, transferred_count: 0, escalated_count: 0,
    disposed_count: 0, overdue_count: 0, due_soon_count: 0, open_overlaps_count: 0
  };

  const overlapAlerts = state.alertsData.filter(a => a.type === "OVERLAP");
  const urgentAlerts = state.alertsData.filter(a => a.type === "SLA_BREACHED" || a.type === "SLA_DUE_SOON" || a.type === "ESCALATED").slice(0, 5);

  return `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

      <!-- PROMINENT OVERLAP BANNER (Hackathon Core Feature) -->
      ${d.open_overlaps_count > 0 ? `
        <div class="bg-gradient-to-r from-amber-500/15 via-amber-500/10 to-orange-500/10 border-l-4 border-amber-500 p-4 rounded-r-xl shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div class="flex items-start space-x-3">
            <div class="p-2 bg-amber-500 text-white rounded-lg shadow mt-0.5">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
            </div>
            <div>
              <div class="text-sm font-bold text-amber-900 tracking-wide uppercase flex items-center gap-2">
                <span>Potential Overlapping Cases – Coordination Required</span>
                <span class="bg-amber-200 text-amber-900 px-2 py-0.5 rounded-full text-xs font-semibold">${d.open_overlaps_count} Active Conflict${d.open_overlaps_count > 1 ? 's' : ''}</span>
              </div>
              <p class="text-xs text-amber-800 mt-1 max-w-3xl leading-relaxed">
                The AICTE Layered Overlap Engine detected parallel open complaints across different bureaus (RB, PGRC, AB) targeting the same institution. Immediate inter-bureau coordination is required to prevent contradictory orders or duplicated inspections.
              </p>
            </div>
          </div>
          <button onclick="navigateTo('overlaps')" class="whitespace-nowrap px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-semibold text-xs rounded-lg shadow transition flex items-center gap-1.5">
            Resolve Overlaps Now &rarr;
          </button>
        </div>
      ` : ''}

      <!-- KPI Summary Cards -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
        <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200 border-t-4 border-t-blue-600">
          <div class="text-xs font-medium text-slate-500 uppercase">Total Complaints</div>
          <div class="text-2xl font-bold text-slate-800 mt-1">${d.total_cases}</div>
          <div class="text-[11px] text-slate-400 mt-1">Across all bureaus</div>
        </div>

        <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200 border-t-4 border-t-sky-500">
          <div class="text-xs font-medium text-slate-500 uppercase">Received</div>
          <div class="text-2xl font-bold text-sky-700 mt-1">${d.received_count}</div>
          <div class="text-[11px] text-slate-400 mt-1">Awaiting scrutiny</div>
        </div>

        <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200 border-t-4 border-t-indigo-500">
          <div class="text-xs font-medium text-slate-500 uppercase">Under Process</div>
          <div class="text-2xl font-bold text-indigo-700 mt-1">${d.under_process_count}</div>
          <div class="text-[11px] text-slate-400 mt-1">Active investigation</div>
        </div>

        <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200 border-t-4 border-t-yellow-500">
          <div class="text-xs font-medium text-slate-500 uppercase">Pending</div>
          <div class="text-2xl font-bold text-yellow-700 mt-1">${d.pending_count}</div>
          <div class="text-[11px] text-slate-400 mt-1">Institution reply due</div>
        </div>

        <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200 border-t-4 border-t-purple-500">
          <div class="text-xs font-medium text-slate-500 uppercase">Escalated</div>
          <div class="text-2xl font-bold text-purple-700 mt-1">${d.escalated_count}</div>
          <div class="text-[11px] text-slate-400 mt-1">Senior council review</div>
        </div>

        <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200 border-t-4 border-t-red-500">
          <div class="text-xs font-medium text-slate-500 uppercase">SLA Breached</div>
          <div class="text-2xl font-bold text-red-600 mt-1">${d.overdue_count}</div>
          <div class="text-[11px] text-red-500 font-semibold mt-1">Critical action needed</div>
        </div>

        <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200 border-t-4 border-t-emerald-600">
          <div class="text-xs font-medium text-slate-500 uppercase">Disposed</div>
          <div class="text-2xl font-bold text-emerald-700 mt-1">${d.disposed_count}</div>
          <div class="text-[11px] text-emerald-600 font-semibold mt-1">${d.total_cases > 0 ? Math.round((d.disposed_count/d.total_cases)*100) : 0}% disposal rate</div>
        </div>
      </div>

      <!-- Charts Section -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        <!-- Bureau Workload Bar Chart -->
        <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200 col-span-1 lg:col-span-2">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-base font-bold text-slate-800">Bureau-Wise Workload & Disposal Velocity</h3>
              <p class="text-xs text-slate-500">Active vs Disposed vs SLA Breached distribution per bureau</p>
            </div>
            <span class="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md font-medium">RB &bull; PGRC &bull; AB</span>
          </div>
          <div class="h-64">
            <canvas id="bureauWorkloadChart"></canvas>
          </div>
        </div>

        <!-- Status Distribution Donut Chart -->
        <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <h3 class="text-base font-bold text-slate-800 mb-1">Status Distribution</h3>
          <p class="text-xs text-slate-500 mb-4">Complaint life-cycle stage breakdown</p>
          <div class="h-64 flex items-center justify-center">
            <canvas id="statusChart"></canvas>
          </div>
        </div>
      </div>

      <!-- Second Row: Regional Grievance + SLA Urgent Feed -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        <!-- Regional Grievance Distribution -->
        <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200 col-span-1">
          <h3 class="text-base font-bold text-slate-800 mb-1">Region-Wise Grievance Load</h3>
          <p class="text-xs text-slate-500 mb-4">Northern, Southern, Western, Eastern, Central</p>
          <div class="h-64">
            <canvas id="regionChart"></canvas>
          </div>
        </div>

        <!-- SLA Alerts & Pending Reminders Feed -->
        <div class="bg-white p-5 rounded-xl shadow-sm border border-slate-200 col-span-1 lg:col-span-2 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-3">
              <div>
                <h3 class="text-base font-bold text-slate-800 flex items-center gap-2">
                  <span class="w-2.5 h-2.5 rounded-full bg-red-500 pulse-dot"></span>
                  High-Priority SLA & Escalation Alerts
                </h3>
                <p class="text-xs text-slate-500">Immediate action required before disciplinary breach</p>
              </div>
              <button onclick="navigateTo('cases', { is_overdue: true })" class="text-xs text-blue-600 hover:text-blue-800 font-semibold">
                View All Breaches (${d.overdue_count}) &rarr;
              </button>
            </div>

            <div class="space-y-2.5 overflow-y-auto max-h-64 pr-1">
              ${urgentAlerts.length === 0 ? `
                <div class="text-center py-8 text-slate-400 text-xs">No active SLA breach alerts at this moment.</div>
              ` : urgentAlerts.map(a => `
                <div class="p-3 rounded-lg border ${a.severity === 'high' ? 'bg-red-50/70 border-red-200' : 'bg-amber-50/70 border-amber-200'} flex items-start justify-between gap-3">
                  <div class="flex items-start space-x-2.5">
                    <span class="mt-0.5 px-2 py-0.5 text-[10px] font-bold rounded ${a.severity === 'high' ? 'bg-red-600 text-white' : 'bg-amber-600 text-white'}">
                      ${a.type.replace('_', ' ')}
                    </span>
                    <div>
                      <div class="text-xs font-bold text-slate-800">${a.title}</div>
                      <div class="text-[11px] text-slate-600 mt-0.5 line-clamp-1">${a.message}</div>
                    </div>
                  </div>
                  <button onclick="navigateTo('case-detail', { caseId: ${a.case_id} })" class="whitespace-nowrap text-xs bg-white hover:bg-slate-100 border border-slate-300 text-slate-700 px-2.5 py-1 rounded font-medium shadow-2xs">
                    Inspect &rarr;
                  </button>
                </div>
              `).join('')}
            </div>
          </div>

          <div class="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>SLA Category Standard: Fee (15d) &bull; Faculty (30d) &bull; Affiliation (45d) &bull; Infra (30d)</span>
            <span class="text-blue-600 font-medium">Logged in as: ${state.user.role}</span>
          </div>
        </div>

      </div>

    </div>
  `;
}

// Chart rendering helper
function renderCharts() {
  if (!state.dashboardData) return;
  const d = state.dashboardData;

  // Bureau Workload Chart
  const ctxWorkload = document.getElementById("bureauWorkloadChart");
  if (ctxWorkload) {
    if (window._bureauChart) window._bureauChart.destroy();
    window._bureauChart = new Chart(ctxWorkload, {
      type: "bar",
      data: {
        labels: d.bureau_workload.map(b => b.bureau),
        datasets: [
          { label: "Active", data: d.bureau_workload.map(b => b.active), backgroundColor: "#3b82f6" },
          { label: "Disposed", data: d.bureau_workload.map(b => b.disposed), backgroundColor: "#10b981" },
          { label: "Overdue", data: d.bureau_workload.map(b => b.overdue), backgroundColor: "#ef4444" }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } } },
        scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } }
      }
    });
  }

  // Status Doughnut Chart
  const ctxStatus = document.getElementById("statusChart");
  if (ctxStatus) {
    if (window._statusChart) window._statusChart.destroy();
    const colors = ["#10b981", "#8b5cf6", "#eab308", "#38bdf8", "#ec4899", "#6366f1"];
    window._statusChart = new Chart(ctxStatus, {
      type: "doughnut",
      data: {
        labels: d.status_distribution.map(s => s.name),
        datasets: [{
          data: d.status_distribution.map(s => s.value),
          backgroundColor: colors.slice(0, d.status_distribution.length),
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10 } } } }
      }
    });
  }

  // Region Bar Chart
  const ctxRegion = document.getElementById("regionChart");
  if (ctxRegion) {
    if (window._regionChart) window._regionChart.destroy();
    window._regionChart = new Chart(ctxRegion, {
      type: "bar",
      data: {
        labels: d.region_distribution.map(r => r.region),
        datasets: [{
          label: "Complaints",
          data: d.region_distribution.map(r => r.count),
          backgroundColor: "#f59e0b"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      }
    });
  }
}

// Screen 2: Cases List
function renderCasesList() {
  const cases = state.casesList || [];
  return `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-4">
      
      <!-- Top Title and Counter -->
      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 class="text-xl font-bold text-slate-800">Master Grievance Database</h2>
          <p class="text-xs text-slate-500">Real-time consolidated view of technical institution complaints across all bureaus</p>
        </div>
        <div class="flex items-center space-x-2">
          <button onclick="navigateTo('new-case')" class="px-3.5 py-2 bg-blue-700 hover:bg-blue-800 text-white text-xs font-semibold rounded-lg shadow transition flex items-center gap-1.5">
            + Register New Case
          </button>
          <a href="${API_BASE}/api/reports/export/csv" class="px-3.5 py-2 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold rounded-lg shadow transition flex items-center gap-1.5">
            Export CSV
          </a>
        </div>
      </div>

      <!-- Filter Controls Bar -->
      <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200 space-y-3">
        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-6 gap-3">
          
          <!-- Search input -->
          <div class="col-span-1 sm:col-span-2">
            <label class="block text-[11px] font-semibold text-slate-500 uppercase mb-1">Search Keywords</label>
            <input type="text" id="filter-search" value="${state.filters.search}" placeholder="Search case#, institution, city, description..." 
                   class="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500" 
                   oninput="state.filters.search = this.value">
          </div>

          <!-- Bureau filter -->
          <div>
            <label class="block text-[11px] font-semibold text-slate-500 uppercase mb-1">Bureau / Cell</label>
            <select id="filter-bureau" class="w-full text-xs px-2.5 py-2 border border-slate-300 rounded-lg" onchange="state.filters.bureau = this.value; loadScreenData();">
              <option value="All" ${state.filters.bureau === 'All' ? 'selected' : ''}>All Bureaus</option>
              <option value="RB" ${state.filters.bureau === 'RB' ? 'selected' : ''}>RB (Regulation)</option>
              <option value="PGRC" ${state.filters.bureau === 'PGRC' ? 'selected' : ''}>PGRC (Grievance)</option>
              <option value="AB" ${state.filters.bureau === 'AB' ? 'selected' : ''}>AB (Approval)</option>
            </select>
          </div>

          <!-- Category filter -->
          <div>
            <label class="block text-[11px] font-semibold text-slate-500 uppercase mb-1">Category</label>
            <select id="filter-category" class="w-full text-xs px-2.5 py-2 border border-slate-300 rounded-lg" onchange="state.filters.category = this.value; loadScreenData();">
              <option value="All" ${state.filters.category === 'All' ? 'selected' : ''}>All Categories</option>
              <option value="Fee" ${state.filters.category === 'Fee' ? 'selected' : ''}>Fee Violation</option>
              <option value="Faculty" ${state.filters.category === 'Faculty' ? 'selected' : ''}>Faculty Deficit</option>
              <option value="Affiliation" ${state.filters.category === 'Affiliation' ? 'selected' : ''}>Affiliation / Approval</option>
              <option value="Infrastructure" ${state.filters.category === 'Infrastructure' ? 'selected' : ''}>Infrastructure</option>
              <option value="Other" ${state.filters.category === 'Other' ? 'selected' : ''}>Other</option>
            </select>
          </div>

          <!-- Status filter -->
          <div>
            <label class="block text-[11px] font-semibold text-slate-500 uppercase mb-1">Status</label>
            <select id="filter-status" class="w-full text-xs px-2.5 py-2 border border-slate-300 rounded-lg" onchange="state.filters.status = this.value; loadScreenData();">
              <option value="All" ${state.filters.status === 'All' ? 'selected' : ''}>All Statuses</option>
              <option value="Received" ${state.filters.status === 'Received' ? 'selected' : ''}>Received</option>
              <option value="Under Process" ${state.filters.status === 'Under Process' ? 'selected' : ''}>Under Process</option>
              <option value="Pending" ${state.filters.status === 'Pending' ? 'selected' : ''}>Pending</option>
              <option value="Transferred" ${state.filters.status === 'Transferred' ? 'selected' : ''}>Transferred</option>
              <option value="Escalated" ${state.filters.status === 'Escalated' ? 'selected' : ''}>Escalated</option>
              <option value="Disposed" ${state.filters.status === 'Disposed' ? 'selected' : ''}>Disposed</option>
            </select>
          </div>

          <!-- Region filter -->
          <div>
            <label class="block text-[11px] font-semibold text-slate-500 uppercase mb-1">Region</label>
            <select id="filter-region" class="w-full text-xs px-2.5 py-2 border border-slate-300 rounded-lg" onchange="state.filters.region = this.value; loadScreenData();">
              <option value="All" ${state.filters.region === 'All' ? 'selected' : ''}>All Regions</option>
              <option value="Northern" ${state.filters.region === 'Northern' ? 'selected' : ''}>Northern</option>
              <option value="Southern" ${state.filters.region === 'Southern' ? 'selected' : ''}>Southern</option>
              <option value="Western" ${state.filters.region === 'Western' ? 'selected' : ''}>Western</option>
              <option value="Eastern" ${state.filters.region === 'Eastern' ? 'selected' : ''}>Eastern</option>
              <option value="Central" ${state.filters.region === 'Central' ? 'selected' : ''}>Central</option>
            </select>
          </div>
        </div>

        <!-- Filter Toggles & Action Buttons -->
        <div class="flex flex-wrap items-center justify-between pt-2 border-t border-slate-100 text-xs">
          <div class="flex items-center space-x-4">
            <label class="inline-flex items-center space-x-1.5 cursor-pointer font-medium text-red-700">
              <input type="checkbox" ${state.filters.is_overdue ? 'checked' : ''} onchange="state.filters.is_overdue = this.checked; loadScreenData();" class="rounded text-red-600 focus:ring-red-500">
              <span>Show Overdue Cases Only</span>
            </label>
            <label class="inline-flex items-center space-x-1.5 cursor-pointer font-medium text-amber-700">
              <input type="checkbox" ${state.filters.has_overlap ? 'checked' : ''} onchange="state.filters.has_overlap = this.checked; loadScreenData();" class="rounded text-amber-600 focus:ring-amber-500">
              <span>Show Cross-Bureau Overlaps Only</span>
            </label>
          </div>

          <div class="flex items-center space-x-2 mt-2 sm:mt-0">
            <button onclick="loadScreenData()" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium">
              Apply Filters
            </button>
            <button onclick="state.filters = { search: '', bureau: 'All', category: 'All', status: 'All', region: 'All', is_overdue: false, has_overlap: false }; loadScreenData();" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded font-medium">
              Reset
            </button>
          </div>
        </div>
      </div>

      <!-- Cases Data Table -->
      <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead class="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider">
              <tr>
                <th class="px-4 py-3">Case No & Bureau</th>
                <th class="px-4 py-3">Institution & Region</th>
                <th class="px-4 py-3">Category</th>
                <th class="px-4 py-3">Received / SLA Due</th>
                <th class="px-4 py-3">Status</th>
                <th class="px-4 py-3">Flags / Alerts</th>
                <th class="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 bg-white">
              ${cases.length === 0 ? `
                <tr><td colspan="7" class="text-center py-10 text-slate-400">No cases found matching the selected filters.</td></tr>
              ` : cases.map(c => `
                <tr class="hover:bg-slate-50 transition ${c.is_overdue ? 'bg-red-50/30' : ''} ${c.has_overlap ? 'bg-amber-50/20' : ''}">
                  
                  <!-- Case No & Bureau -->
                  <td class="px-4 py-3 whitespace-nowrap">
                    <div class="font-bold text-blue-900 cursor-pointer hover:underline" onclick="navigateTo('case-detail', { caseId: ${c.id} })">
                      ${c.case_no}
                    </div>
                    <div class="flex items-center gap-1.5 mt-0.5">
                      <span class="px-1.5 py-0.2 rounded font-bold text-[10px] ${c.bureau === 'RB' ? 'bg-blue-100 text-blue-800' : c.bureau === 'PGRC' ? 'bg-green-100 text-green-800' : 'bg-purple-100 text-purple-800'}">
                        ${c.bureau}
                      </span>
                      <span class="text-[11px] text-slate-500">${c.officer}</span>
                    </div>
                  </td>

                  <!-- Institution & Region -->
                  <td class="px-4 py-3">
                    <div class="font-semibold text-slate-800 hover:text-blue-700 cursor-pointer line-clamp-1" onclick="navigateTo('institution', { institutionId: ${c.institution_id} })">
                      ${c.institution_name}
                    </div>
                    <div class="text-[11px] text-slate-500">
                      ID: <span class="font-mono text-slate-700">${c.aicte_permanent_id}</span> &bull; ${c.city} (${c.region})
                    </div>
                  </td>

                  <!-- Category -->
                  <td class="px-4 py-3 whitespace-nowrap">
                    <span class="px-2 py-0.5 rounded font-medium text-[11px] bg-slate-100 text-slate-700">
                      ${c.category}
                    </span>
                  </td>

                  <!-- Received / SLA -->
                  <td class="px-4 py-3 whitespace-nowrap">
                    <div class="text-slate-700">${c.received_date.substring(0, 10)}</div>
                    <div class="text-[11px] ${c.is_overdue ? 'text-red-600 font-bold' : 'text-slate-500'}">
                      ${c.is_overdue ? `Overdue by ${Math.abs(c.days_remaining)}d` : `Due in ${c.days_remaining}d`}
                    </div>
                  </td>

                  <!-- Status -->
                  <td class="px-4 py-3 whitespace-nowrap">
                    <span class="px-2 py-0.5 rounded-full font-bold text-[10px] ${
                      c.status === 'Disposed' ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' :
                      c.status === 'Escalated' ? 'bg-purple-100 text-purple-800 border border-purple-300' :
                      c.status === 'Pending' ? 'bg-yellow-100 text-yellow-800 border border-yellow-300' :
                      c.status === 'Transferred' ? 'bg-indigo-100 text-indigo-800 border border-indigo-300' :
                      'bg-blue-100 text-blue-800 border border-blue-300'
                    }">
                      ${c.status}
                    </span>
                  </td>

                  <!-- Flags & Alerts -->
                  <td class="px-4 py-3 whitespace-nowrap">
                    <div class="flex items-center gap-1.5">
                      ${c.has_overlap ? `
                        <span class="px-2 py-0.5 rounded font-bold text-[10px] badge-overlap flex items-center gap-1 cursor-pointer" onclick="navigateTo('case-detail', { caseId: ${c.id} })">
                          <svg class="w-3 h-3 text-amber-600" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>
                          OVERLAP (${c.overlap_count})
                        </span>
                      ` : ''}

                      ${c.is_overdue ? `
                        <span class="px-2 py-0.5 rounded font-bold text-[10px] badge-overdue">
                          BREACHED
                        </span>
                      ` : ''}

                      ${!c.has_overlap && !c.is_overdue ? `
                        <span class="text-slate-400 text-[11px]">&mdash;</span>
                      ` : ''}
                    </div>
                  </td>

                  <!-- Action button -->
                  <td class="px-4 py-3 whitespace-nowrap text-right">
                    <button onclick="navigateTo('case-detail', { caseId: ${c.id} })" class="px-2.5 py-1 bg-slate-100 hover:bg-blue-600 hover:text-white text-slate-700 font-medium rounded transition">
                      Details &rarr;
                    </button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
        <div class="bg-slate-50 px-4 py-3 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
          <span>Showing <strong>${cases.length}</strong> complaints registered across AICTE bureaus</span>
          <span>Red = SLA Deadline Breached &bull; Amber = Active Cross-Bureau Overlap</span>
        </div>
      </div>

    </div>
  `;
}

// Screen 3: Case Detail
function renderCaseDetail() {
  const c = state.currentCase;
  if (!c) return `<div class="p-8 text-center text-slate-500">Loading case details...</div>`;

  const overlaps = (c.links || []).filter(l => l.status !== "Dismissed");

  return `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

      <!-- Breadcrumbs & Quick Back -->
      <div class="flex items-center justify-between">
        <button onclick="navigateTo('cases')" class="text-xs text-blue-700 hover:underline flex items-center gap-1 font-semibold">
          &larr; Back to Grievance Cases
        </button>
        <div class="flex items-center space-x-2">
          <button onclick="openActionModal('Update', ${c.id})" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow">
            Update Status
          </button>
          <button onclick="openActionModal('Transfer', ${c.id})" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow">
            Transfer Bureau
          </button>
          <button onclick="openActionModal('Escalate', ${c.id})" class="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold rounded-lg shadow">
            Escalate
          </button>
          <button onclick="openActionModal('Dispose', ${c.id})" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow">
            Dispose / Close
          </button>
        </div>
      </div>

      <!-- PROMINENT OVERLAP ALERT (If any active overlaps exist for this case) -->
      ${overlaps.length > 0 ? overlaps.map(l => `
        <div class="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-xl shadow-sm space-y-3">
          <div class="flex items-start justify-between">
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 bg-amber-500 text-white text-xs font-bold rounded">
                ${l.link_type} ALERT
              </span>
              <span class="text-xs font-bold text-amber-900 uppercase">
                Potential Overlapping Cases – Coordination Required
              </span>
              <span class="text-xs bg-amber-200 text-amber-800 px-2 py-0.2 rounded-full font-semibold">
                Confidence: ${l.confidence_score}%
              </span>
            </div>
            <div class="flex items-center space-x-2">
              <button onclick="resolveOverlap(${l.id}, 'Linked')" class="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded shadow">
                Mark as Linked & Coordinated
              </button>
              <button onclick="resolveOverlap(${l.id}, 'Dismissed')" class="px-3 py-1 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-medium rounded">
                Dismiss False Positive
              </button>
            </div>
          </div>
          <p class="text-xs text-amber-800 leading-relaxed">
            ${l.reason}
          </p>
          <div class="bg-white/80 p-3 rounded-lg border border-amber-200 text-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
            <div>
              <span class="text-slate-500 font-medium">Conflicting Case:</span>
              <strong class="text-blue-900 ml-1 cursor-pointer hover:underline" onclick="navigateTo('case-detail', { caseId: ${l.other_case_id} })">
                ${l.other_case_no || 'Case Reference'} (${l.other_bureau})
              </strong>
              <span class="ml-2 px-1.5 py-0.2 text-[10px] bg-slate-100 rounded">${l.other_category}</span>
              <span class="ml-1 px-1.5 py-0.2 text-[10px] bg-blue-100 text-blue-800 rounded">${l.other_status}</span>
            </div>
            <button onclick="navigateTo('overlaps')" class="text-blue-700 hover:underline font-semibold text-xs">
              Open in Overlap Center &rarr;
            </button>
          </div>
        </div>
      `).join('') : ''}

      <!-- Case Header Card -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
        <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <div class="flex items-center gap-2">
              <h1 class="text-2xl font-bold text-slate-900">${c.case_no}</h1>
              <span class="px-2.5 py-0.5 rounded-full font-bold text-xs ${c.status === 'Disposed' ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800'}">
                ${c.status}
              </span>
              ${c.is_overdue ? `
                <span class="px-2.5 py-0.5 rounded-full font-bold text-xs bg-red-100 text-red-700 border border-red-300">
                  SLA Breached (${Math.abs(c.days_remaining)} days)
                </span>
              ` : `
                <span class="px-2.5 py-0.5 rounded-full font-semibold text-xs bg-slate-100 text-slate-600">
                  ${c.days_remaining} days remaining
                </span>
              `}
            </div>
            <div class="text-xs text-slate-500 mt-1">
              Received on: <strong>${c.received_date}</strong> &bull; Target Disposal Date: <strong>${c.expected_disposal_date}</strong>
            </div>
          </div>

          <div class="text-right">
            <div class="text-xs text-slate-500">Handling Bureau / Cell</div>
            <div class="text-lg font-bold text-blue-900">${c.bureau} Bureau</div>
            <div class="text-xs text-slate-600">Officer In-Charge: <strong>${c.officer}</strong></div>
          </div>
        </div>

        <!-- Meta Details Grid -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 pt-4 text-xs">
          <div>
            <span class="text-slate-400 block uppercase font-medium">Institution</span>
            <span class="font-bold text-slate-800 hover:text-blue-600 cursor-pointer text-sm" onclick="navigateTo('institution', { institutionId: c.institution_id })">
              ${c.institution_name}
            </span>
            <div class="text-[11px] text-slate-500">AICTE ID: ${c.aicte_permanent_id}</div>
          </div>
          <div>
            <span class="text-slate-400 block uppercase font-medium">Category</span>
            <span class="font-bold text-slate-800 text-sm">${c.category}</span>
            <div class="text-[11px] text-slate-500">SLA: ${c.category === 'Fee' ? '15 Days' : c.category === 'Affiliation' ? '45 Days' : '30 Days'}</div>
          </div>
          <div>
            <span class="text-slate-400 block uppercase font-medium">Location</span>
            <span class="font-bold text-slate-800 text-sm">${c.city}, ${c.region}</span>
            <div class="text-[11px] text-slate-500">Regional Jurisdiction</div>
          </div>
          <div>
            <span class="text-slate-400 block uppercase font-medium">Last / Next Action</span>
            <span class="font-bold text-slate-800 line-clamp-1">${c.last_action || 'N/A'}</span>
            <div class="text-[11px] text-indigo-700 font-semibold line-clamp-1">Next: ${c.next_action || 'Awaiting Action'}</div>
          </div>
        </div>

        <!-- Complaint Full Description -->
        <div class="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
          <div class="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1">Grievance Description / Petition Details:</div>
          <p class="text-xs text-slate-700 leading-relaxed">${c.description}</p>
        </div>
      </div>

      <!-- Chronological Append-Only Audit Trail -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h3 class="text-base font-bold text-slate-900">Append-Only Case Movement & Audit Trail</h3>
            <p class="text-xs text-slate-500">Tamper-evident legal ledger recording every state change, transfer, and escalation</p>
          </div>
          <span class="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded font-mono">${(c.actions || []).length} Recorded Actions</span>
        </div>

        <div class="relative border-l-2 border-slate-200 ml-4 space-y-6">
          ${(c.actions || []).map((a, idx) => `
            <div class="relative pl-6">
              <!-- Timeline node circle -->
              <span class="absolute -left-[9px] top-1 w-4 h-4 rounded-full border-2 border-white ${
                a.action_type === 'Register' ? 'bg-sky-500' :
                a.action_type === 'Transfer' ? 'bg-indigo-600' :
                a.action_type === 'Escalate' ? 'bg-purple-600' :
                a.action_type === 'Dispose' ? 'bg-emerald-600' : 'bg-blue-600'
              }"></span>

              <div class="bg-slate-50 p-3.5 rounded-lg border border-slate-200 shadow-2xs">
                <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-1 text-xs mb-1">
                  <div class="flex items-center gap-2">
                    <span class="px-2 py-0.5 rounded font-bold text-[10px] ${
                      a.action_type === 'Register' ? 'bg-sky-100 text-sky-800' :
                      a.action_type === 'Transfer' ? 'bg-indigo-100 text-indigo-800' :
                      a.action_type === 'Escalate' ? 'bg-purple-100 text-purple-800' :
                      a.action_type === 'Dispose' ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800'
                    }">
                      ${a.action_type}
                    </span>
                    <strong class="text-slate-800">${a.officer}</strong>
                    <span class="text-slate-400">(${a.bureau})</span>
                    ${a.from_bureau && a.to_bureau ? `
                      <span class="text-indigo-600 font-semibold">[Transferred ${a.from_bureau} &rarr; ${a.to_bureau}]</span>
                    ` : ''}
                  </div>
                  <span class="text-slate-400 font-mono text-[11px]">${a.timestamp}</span>
                </div>
                <p class="text-xs text-slate-700 mt-1">${a.remarks}</p>
                ${a.document_reference ? `
                  <div class="mt-2 text-[11px] text-slate-500 flex items-center gap-1">
                    <svg class="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/></svg>
                    Official Document Ref: <strong class="font-mono text-slate-700">${a.document_reference}</strong>
                  </div>
                ` : ''}
              </div>
            </div>
          `).join('')}
        </div>
      </div>

    </div>
  `;
}

// Screen 4: Overlap Center
function renderOverlapCenter() {
  const overlaps = state.overlapList || [];
  return `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      
      <!-- Overlap Center Header -->
      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 class="text-xl font-bold text-slate-900 flex items-center gap-2">
            Inter-Bureau Overlap & Coordination Center
            <span class="bg-amber-100 text-amber-800 px-2.5 py-0.5 rounded-full text-xs font-bold border border-amber-300">Core Innovation</span>
          </h2>
          <p class="text-xs text-slate-500">Autonomous detection of cross-bureau duplications and overlapping complaints targeting the same technical institution</p>
        </div>
        <div class="text-xs bg-slate-100 text-slate-600 px-3 py-1.5 rounded-lg border border-slate-200">
          Thresholds: TokenSetRatio &ge; 85% &bull; Duplicate &ge; 75% Text Match
        </div>
      </div>

      <!-- Overlaps List -->
      <div class="space-y-4">
        ${overlaps.length === 0 ? `
          <div class="bg-white p-12 text-center rounded-xl shadow-sm border border-slate-200">
            <div class="text-slate-400 text-base font-semibold">No cross-bureau conflicts detected.</div>
            <p class="text-xs text-slate-400 mt-1">All complaints are isolated to single bureaus.</p>
          </div>
        ` : overlaps.map(o => `
          <div class="bg-white rounded-xl shadow-sm border ${o.status === 'Open' ? 'border-amber-400 ring-1 ring-amber-400/30' : 'border-slate-200'} p-5 space-y-4">
            
            <!-- Top Alert Badge & Resolution Actions -->
            <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-3 border-b border-slate-100 gap-3">
              <div class="flex items-center space-x-2">
                <span class="px-2.5 py-1 text-xs font-bold rounded ${o.link_type === 'DUPLICATE' ? 'bg-red-600 text-white' : 'bg-amber-500 text-white'}">
                  ${o.link_type}
                </span>
                <span class="text-sm font-bold text-slate-800">
                  ${o.link_type === 'DUPLICATE' ? 'Potential Duplicate Case – Same Issue in Multiple Bureaus' : 'Potential Overlapping Cases – Coordination Required'}
                </span>
                <span class="text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded font-mono font-bold">
                  Score: ${o.confidence_score}%
                </span>
                <span class="text-xs px-2 py-0.5 rounded-full font-bold ${o.status === 'Open' ? 'bg-amber-100 text-amber-800' : o.status === 'Linked' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'}">
                  Status: ${o.status}
                </span>
              </div>

              ${o.status === 'Open' ? `
                <div class="flex items-center space-x-2">
                  <button onclick="resolveOverlap(${o.id}, 'Linked')" class="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-lg shadow">
                    Link & Coordinate Bureaus
                  </button>
                  <button onclick="resolveOverlap(${o.id}, 'Dismissed')" class="px-3.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium rounded-lg border border-slate-300">
                    Dismiss (Unrelated)
                  </button>
                </div>
              ` : `
                <div class="text-xs text-slate-400 font-medium italic">
                  Resolved as: <strong>${o.status}</strong>
                </div>
              `}
            </div>

            <!-- Explainable Rationale Callout -->
            <div class="p-3 bg-amber-50/70 border border-amber-200 rounded-lg text-xs text-amber-900 leading-relaxed font-medium">
              <span class="font-bold">Explainable AI Rationale:</span> ${o.reason}
            </div>

            <!-- Side-by-Side Comparison of the Two Conflicting Cases -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              
              <!-- Case A -->
              <div class="p-4 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
                <div class="flex items-center justify-between">
                  <span class="px-2 py-0.5 bg-blue-100 text-blue-900 rounded font-bold text-xs">${o.case_a.bureau} Bureau</span>
                  <span class="text-xs font-bold text-blue-700 cursor-pointer hover:underline" onclick="navigateTo('case-detail', { caseId: ${o.case_a.id} })">
                    ${o.case_a.case_no} &rarr;
                  </span>
                </div>
                <div class="text-xs font-bold text-slate-800">${o.case_a.institution_name}</div>
                <div class="text-[11px] text-slate-500">ID: ${o.case_a.aicte_permanent_id} &bull; Category: <strong>${o.case_a.category}</strong></div>
                <p class="text-xs text-slate-600 line-clamp-3 bg-white p-2.5 rounded border border-slate-200">${o.case_a.description}</p>
                <div class="text-[11px] text-slate-500 flex justify-between">
                  <span>Officer: ${o.case_a.officer}</span>
                  <span class="font-bold text-slate-700">${o.case_a.status}</span>
                </div>
              </div>

              <!-- Case B -->
              <div class="p-4 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
                <div class="flex items-center justify-between">
                  <span class="px-2 py-0.5 bg-green-100 text-green-900 rounded font-bold text-xs">${o.case_b.bureau} Bureau</span>
                  <span class="text-xs font-bold text-blue-700 cursor-pointer hover:underline" onclick="navigateTo('case-detail', { caseId: ${o.case_b.id} })">
                    ${o.case_b.case_no} &rarr;
                  </span>
                </div>
                <div class="text-xs font-bold text-slate-800">${o.case_b.institution_name}</div>
                <div class="text-[11px] text-slate-500">ID: ${o.case_b.aicte_permanent_id} &bull; Category: <strong>${o.case_b.category}</strong></div>
                <p class="text-xs text-slate-600 line-clamp-3 bg-white p-2.5 rounded border border-slate-200">${o.case_b.description}</p>
                <div class="text-[11px] text-slate-500 flex justify-between">
                  <span>Officer: ${o.case_b.officer}</span>
                  <span class="font-bold text-slate-700">${o.case_b.status}</span>
                </div>
              </div>

            </div>

          </div>
        `).join('')}
      </div>

    </div>
  `;
}

// Screen 5: Institution Profile View
function renderInstitutionProfile() {
  const inst = state.currentInstitution;
  if (!inst) return `<div class="p-8 text-center text-slate-500">Loading institution profile...</div>`;

  return `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

      <button onclick="navigateTo('cases')" class="text-xs text-blue-700 hover:underline flex items-center gap-1 font-semibold">
        &larr; Back to Master Grievance List
      </button>

      <!-- Coordination Banner if Overlap exists -->
      ${inst.has_active_overlap ? `
        <div class="bg-amber-500 text-white p-4 rounded-xl shadow-md flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <svg class="w-6 h-6 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
            <div>
              <div class="font-bold text-sm tracking-wide uppercase">Active Inter-Bureau Overlap Advisory</div>
              <div class="text-xs text-amber-100">Multiple active complaints are currently undergoing inquiry in different bureaus for this institution. Coordinate regulatory responses.</div>
            </div>
          </div>
          <button onclick="navigateTo('overlaps')" class="px-3 py-1.5 bg-white text-amber-900 font-bold text-xs rounded-lg shadow whitespace-nowrap">
            View Overlaps &rarr;
          </button>
        </div>
      ` : ''}

      <!-- Institution Master Card -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
        <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <span class="text-xs font-bold text-amber-600 uppercase tracking-wider">${inst.type}</span>
            <h1 class="text-2xl font-bold text-slate-900 mt-1">${inst.name}</h1>
            <div class="text-xs text-slate-500 mt-1">
              Permanent AICTE ID: <strong class="font-mono text-slate-800">${inst.aicte_permanent_id}</strong> &bull; Location: <strong>${inst.city}, ${inst.region} Region</strong>
            </div>
            <div class="text-xs text-slate-400 mt-0.5">${inst.address || ''}</div>
          </div>

          <div class="flex items-center space-x-3">
            <div class="bg-slate-50 px-4 py-2 rounded-lg border border-slate-200 text-center">
              <div class="text-xs text-slate-500">Total Cases</div>
              <div class="text-xl font-bold text-slate-800">${inst.total_cases}</div>
            </div>
            <div class="bg-blue-50 px-4 py-2 rounded-lg border border-blue-200 text-center">
              <div class="text-xs text-blue-700">Open Cases</div>
              <div class="text-xl font-bold text-blue-800">${inst.open_cases}</div>
            </div>
            <div class="bg-emerald-50 px-4 py-2 rounded-lg border border-emerald-200 text-center">
              <div class="text-xs text-emerald-700">Disposed</div>
              <div class="text-xl font-bold text-emerald-800">${inst.disposed_cases}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Consolidated Cross-Bureau History Table -->
      <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div class="p-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <h3 class="font-bold text-sm text-slate-800">Consolidated Case History Across All Bureaus (RB, PGRC, AB)</h3>
          <span class="text-xs text-slate-500">Single-Window Unified View</span>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead class="bg-slate-50 text-slate-600 font-semibold uppercase">
              <tr>
                <th class="px-4 py-3">Case No</th>
                <th class="px-4 py-3">Bureau</th>
                <th class="px-4 py-3">Category</th>
                <th class="px-4 py-3">Received Date</th>
                <th class="px-4 py-3">Status</th>
                <th class="px-4 py-3">Assigned Officer</th>
                <th class="px-4 py-3 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 bg-white">
              ${(inst.cases || []).map(c => `
                <tr class="hover:bg-slate-50">
                  <td class="px-4 py-3 font-bold text-blue-900">${c.case_no}</td>
                  <td class="px-4 py-3">
                    <span class="px-2 py-0.5 rounded font-bold text-[10px] ${c.bureau === 'RB' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'}">
                      ${c.bureau}
                    </span>
                  </td>
                  <td class="px-4 py-3 font-medium text-slate-700">${c.category}</td>
                  <td class="px-4 py-3 text-slate-500">${c.received_date.substring(0, 10)}</td>
                  <td class="px-4 py-3">
                    <span class="px-2 py-0.5 rounded-full font-bold text-[10px] ${c.status === 'Disposed' ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800'}">
                      ${c.status}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-slate-600">${c.officer}</td>
                  <td class="px-4 py-3 text-right">
                    <button onclick="navigateTo('case-detail', { caseId: ${c.id} })" class="text-blue-600 hover:underline font-semibold">
                      View &rarr;
                    </button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  `;
}

// Screen 6: New Complaint Registration
function renderNewCase() {
  return `
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      
      <div>
        <h2 class="text-xl font-bold text-slate-900">Register New Technical Grievance / Complaint</h2>
        <p class="text-xs text-slate-500">Auto-resolves institution identity and triggers real-time cross-bureau overlap detection</p>
      </div>

      <!-- Quick Demo Preset Buttons -->
      <div class="bg-amber-50/70 border border-amber-200 p-4 rounded-xl space-y-2">
        <div class="text-xs font-bold text-amber-900 uppercase">Quick Demo Presets (1-Click Test Scenarios):</div>
        <div class="flex flex-wrap gap-2 text-xs">
          <button onclick="fillDemoForm('overlap')" class="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded font-medium shadow-2xs">
            Trigger Overlap Alert (Delhi Inst. of Tech)
          </button>
          <button onclick="fillDemoForm('abbrev')" class="px-3 py-1.5 bg-blue-700 hover:bg-blue-800 text-white rounded font-medium shadow-2xs">
            Fuzzy Abbreviation ("PSG Coll. of Tech.")
          </button>
          <button onclick="fillDemoForm('duplicate')" class="px-3 py-1.5 bg-red-700 hover:bg-red-800 text-white rounded font-medium shadow-2xs">
            True Duplicate Test (VJTI Mumbai Fee)
          </button>
        </div>
      </div>

      <!-- Registration Form -->
      <form id="new-case-form" onsubmit="handleCreateCase(event)" class="bg-white p-6 rounded-xl shadow-sm border border-slate-200 space-y-4">
        
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Institution AICTE Permanent ID (Optional)</label>
            <input type="text" id="case-aicte-id" placeholder="e.g. 1-104928171" class="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg font-mono">
            <span class="text-[10px] text-slate-400">Layer 1 Exact Match trigger</span>
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Institution Name <span class="text-red-500">*</span></label>
            <input type="text" id="case-name" required placeholder="e.g. Delhi Institute of Technology & Management" class="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg">
            <span class="text-[10px] text-slate-400">Supports abbreviations: Instt., Engg., Tech., Coll.</span>
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">City</label>
            <input type="text" id="case-city" placeholder="e.g. New Delhi" class="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg">
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Region</label>
            <select id="case-region" class="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg">
              <option value="Northern">Northern</option>
              <option value="Southern">Southern</option>
              <option value="Western">Western</option>
              <option value="Eastern">Eastern</option>
              <option value="Central">Central</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Complaint Category <span class="text-red-500">*</span></label>
            <select id="case-category" required class="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg">
              <option value="Fee">Fee Regulatory Violation (SLA: 15d)</option>
              <option value="Faculty">Faculty Ratio & Payroll (SLA: 30d)</option>
              <option value="Affiliation">Affiliation & Approval (SLA: 45d)</option>
              <option value="Infrastructure">Infrastructure Deficit (SLA: 30d)</option>
              <option value="Other">Other Statutory Violation (SLA: 30d)</option>
            </select>
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Assigned Bureau</label>
            <select id="case-bureau" class="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg">
              <option value="RB" ${state.user && state.user.bureau === 'RB' ? 'selected' : ''}>Regulation Bureau (RB)</option>
              <option value="PGRC" ${state.user && state.user.bureau === 'PGRC' ? 'selected' : ''}>Public Grievance Redressal Cell (PGRC)</option>
              <option value="AB">Approval Bureau (AB)</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Scrutiny Officer</label>
            <input type="text" id="case-officer" value="${state.user ? state.user.name : 'Duty Officer'}" class="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg">
          </div>
        </div>

        <div>
          <label class="block text-xs font-semibold text-slate-700 mb-1">Grievance Petition & Detailed Allegations <span class="text-red-500">*</span></label>
          <textarea id="case-desc" rows="4" required placeholder="Describe the violation, evidence provided, student/faculty representations, etc." class="w-full text-xs p-3 border border-slate-300 rounded-lg leading-relaxed"></textarea>
        </div>

        <div class="pt-2 flex items-center justify-end space-x-3">
          <button type="button" onclick="navigateTo('cases')" class="px-4 py-2 border border-slate-300 text-slate-700 text-xs font-semibold rounded-lg hover:bg-slate-50">
            Cancel
          </button>
          <button type="submit" class="px-5 py-2 bg-blue-700 hover:bg-blue-800 text-white text-xs font-semibold rounded-lg shadow">
            Register Complaint & Run Overlap Engine
          </button>
        </div>

      </form>

    </div>
  `;
}

// Preset form filler for demo
function fillDemoForm(type) {
  if (type === 'overlap') {
    document.getElementById("case-aicte-id").value = "1-104928171";
    document.getElementById("case-name").value = "Delhi Institute of Technology & Management";
    document.getElementById("case-city").value = "New Delhi";
    document.getElementById("case-region").value = "Northern";
    document.getElementById("case-category").value = "Infrastructure";
    document.getElementById("case-bureau").value = "RB"; // Opposite of PGRC case
    document.getElementById("case-desc").value = "Regulation Bureau petition regarding unapproved alterations in student workshops, library infrastructure deficits, and safety compliance failures.";
  } else if (type === 'abbrev') {
    document.getElementById("case-aicte-id").value = "";
    document.getElementById("case-name").value = "PSG Coll. of Tech.";
    document.getElementById("case-city").value = "Coimbatore";
    document.getElementById("case-region").value = "Southern";
    document.getElementById("case-category").value = "Fee";
    document.getElementById("case-bureau").value = "RB";
    document.getElementById("case-desc").value = "Grievance received from students of PSG Coll. of Tech. Coimbatore complaining of unilateral hostel fine levies.";
  } else if (type === 'duplicate') {
    document.getElementById("case-aicte-id").value = "1-222918401";
    document.getElementById("case-name").value = "Veermata Jijabai Technological Institute";
    document.getElementById("case-city").value = "Mumbai";
    document.getElementById("case-region").value = "Western";
    document.getElementById("case-category").value = "Fee";
    document.getElementById("case-bureau").value = "RB";
    document.getElementById("case-desc").value = "Grievance regarding non-refund of capitation and examination advance fee to M.Tech admission withdrawal candidates within statutory 15 days.";
  }
}

async function handleCreateCase(e) {
  e.preventDefault();
  const payload = {
    institution_aicte_id: document.getElementById("case-aicte-id").value.trim() || null,
    institution_name: document.getElementById("case-name").value.trim(),
    city: document.getElementById("case-city").value.trim() || null,
    region: document.getElementById("case-region").value,
    category: document.getElementById("case-category").value,
    bureau: document.getElementById("case-bureau").value,
    officer: document.getElementById("case-officer").value.trim(),
    description: document.getElementById("case-desc").value.trim()
  };

  try {
    const res = await api("/api/cases", "POST", payload);
    state.modal = {
      type: "new_case_result",
      data: res
    };
    render();
  } catch (err) {
    alert("Error registering case: " + err.message);
  }
}

// Screen 7: Reports
function renderReports() {
  const r = state.reportData;
  return `
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 class="text-xl font-bold text-slate-900">Statutory Reports & Regulatory Analytics</h2>
          <p class="text-xs text-slate-500">Comprehensive audits on disposal velocity, regional workloads, and cross-bureau overlap telemetry</p>
        </div>
        <a href="${API_BASE}/api/reports/export/csv" class="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold rounded-lg shadow flex items-center gap-1.5">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
          Export Master CSV
        </a>
      </div>

      <!-- Report Type Selector Tabs -->
      <div class="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        ${[
          { id: "bureau-wise", label: "Bureau Performance" },
          { id: "region-wise", label: "Regional Grievance Analysis" },
          { id: "institution-wise", label: "High-Grievance Institutions" },
          { id: "ageing", label: "Pending Case Ageing Buckets" },
          { id: "overlaps", label: "Overlap & Duplicate Telemetry" },
          { id: "performance", label: "6-Month Disposal Trends" }
        ].map(tab => `
          <button onclick="state.reportType = '${tab.id}'; loadScreenData();" class="px-3.5 py-2 text-xs font-semibold rounded-lg ${state.reportType === tab.id ? 'bg-blue-800 text-white shadow-sm' : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'}">
            ${tab.label}
          </button>
        `).join('')}
      </div>

      <!-- Report View Body -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
        ${!r ? `<div class="text-center py-10 text-slate-400 text-xs">Generating report data...</div>` : renderReportContent(r)}
      </div>

    </div>
  `;
}

function renderReportContent(r) {
  if (r.report_type === "bureau-wise") {
    return `
      <div class="space-y-4">
        <h3 class="text-sm font-bold text-slate-800">Bureau-Wise Case Disposal Velocity & SLA Compliance</h3>
        <table class="min-w-full divide-y divide-slate-200 text-left text-xs">
          <thead class="bg-slate-50 text-slate-600 font-semibold uppercase">
            <tr>
              <th class="px-4 py-2.5">Bureau / Cell</th>
              <th class="px-4 py-2.5">Total Registered</th>
              <th class="px-4 py-2.5">Active Cases</th>
              <th class="px-4 py-2.5">Disposed Cases</th>
              <th class="px-4 py-2.5">SLA Breached</th>
              <th class="px-4 py-2.5">Disposal Efficiency Rate</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            ${r.data.map(b => `
              <tr>
                <td class="px-4 py-2.5 font-bold text-blue-900">${b.bureau} Bureau</td>
                <td class="px-4 py-2.5 font-semibold text-slate-800">${b.total}</td>
                <td class="px-4 py-2.5 text-blue-700 font-semibold">${b.active}</td>
                <td class="px-4 py-2.5 text-emerald-700 font-semibold">${b.disposed}</td>
                <td class="px-4 py-2.5 text-red-600 font-bold">${b.overdue}</td>
                <td class="px-4 py-2.5 font-bold text-slate-800">
                  <div class="flex items-center gap-2">
                    <div class="w-24 bg-slate-200 rounded-full h-2">
                      <div class="bg-emerald-600 h-2 rounded-full" style="width: ${b.disposal_rate}%"></div>
                    </div>
                    <span>${b.disposal_rate}%</span>
                  </div>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } else if (r.report_type === "institution-wise") {
    return `
      <div class="space-y-4">
        <h3 class="text-sm font-bold text-slate-800">Institutions with Highest Grievance Frequencies Across AICTE</h3>
        <table class="min-w-full divide-y divide-slate-200 text-left text-xs">
          <thead class="bg-slate-50 text-slate-600 font-semibold uppercase">
            <tr>
              <th class="px-4 py-2.5">Institution Name</th>
              <th class="px-4 py-2.5">Permanent ID</th>
              <th class="px-4 py-2.5">Region</th>
              <th class="px-4 py-2.5">Total Grievances</th>
              <th class="px-4 py-2.5">Active</th>
              <th class="px-4 py-2.5">Disposed</th>
              <th class="px-4 py-2.5 text-right">Profile</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            ${r.data.map(inst => `
              <tr>
                <td class="px-4 py-2.5 font-semibold text-slate-800">${inst.name}</td>
                <td class="px-4 py-2.5 font-mono text-slate-600">${inst.aicte_id}</td>
                <td class="px-4 py-2.5 text-slate-600">${inst.city} (${inst.region})</td>
                <td class="px-4 py-2.5 font-bold text-blue-900">${inst.total_cases}</td>
                <td class="px-4 py-2.5 text-amber-700 font-semibold">${inst.active_cases}</td>
                <td class="px-4 py-2.5 text-emerald-700 font-semibold">${inst.disposed_cases}</td>
                <td class="px-4 py-2.5 text-right">
                  <button onclick="navigateTo('institution', { institutionId: ${inst.institution_id} })" class="text-blue-600 hover:underline font-semibold">
                    Inspect &rarr;
                  </button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } else if (r.report_type === "ageing") {
    return `
      <div class="space-y-4">
        <h3 class="text-sm font-bold text-slate-800">Pending Case Ageing Distribution</h3>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          ${r.data.map(b => `
            <div class="p-4 bg-slate-50 rounded-lg border border-slate-200 text-center">
              <div class="text-xs text-slate-500 font-medium">${b.age_bucket}</div>
              <div class="text-2xl font-bold text-slate-800 mt-1">${b.count} cases</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  } else if (r.report_type === "overlaps") {
    const d = r.data;
    return `
      <div class="space-y-6">
        <h3 class="text-sm font-bold text-slate-800">Autonomous Overlap Detection Performance Telemetry</h3>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div class="p-4 bg-amber-50 rounded-lg border border-amber-200 text-center">
            <div class="text-xs text-amber-800">Total Inter-Bureau Conflicts Detected</div>
            <div class="text-2xl font-bold text-amber-900 mt-1">${d.total_detected}</div>
          </div>
          <div class="p-4 bg-blue-50 rounded-lg border border-blue-200 text-center">
            <div class="text-xs text-blue-800">Active Conflicts Requiring Action</div>
            <div class="text-2xl font-bold text-blue-900 mt-1">${d.open_pending_action}</div>
          </div>
          <div class="p-4 bg-emerald-50 rounded-lg border border-emerald-200 text-center">
            <div class="text-xs text-emerald-800">Coordinated Across Bureaus</div>
            <div class="text-2xl font-bold text-emerald-900 mt-1">${d.coordinated_linked}</div>
          </div>
        </div>
      </div>
    `;
  } else {
    return `<div class="text-xs text-slate-600 font-mono">${JSON.stringify(r.data, null, 2)}</div>`;
  }
}

function renderReportCharts() {}

// Action Modal (Update, Transfer, Escalate, Dispose)
function openActionModal(actionType, caseId) {
  state.modal = {
    type: "action",
    actionType,
    caseId
  };
  render();
}

async function handleActionSubmit(e) {
  e.preventDefault();
  const modal = state.modal;
  const remarks = document.getElementById("action-remarks").value.trim();
  const to_bureau = document.getElementById("action-to-bureau") ? document.getElementById("action-to-bureau").value : null;
  const document_reference = document.getElementById("action-doc-ref") ? document.getElementById("action-doc-ref").value.trim() : null;
  const next_action = document.getElementById("action-next") ? document.getElementById("action-next").value.trim() : null;

  try {
    await api(`/api/cases/${modal.caseId}/actions`, "POST", {
      action_type: modal.actionType,
      remarks,
      to_bureau,
      document_reference,
      next_action
    });
    state.modal = null;
    loadScreenData();
  } catch (err) {
    alert("Failed to submit action: " + err.message);
  }
}

async function resolveOverlap(linkId, status) {
  const remarks = prompt(`Enter optional remarks for marking this overlap as ${status}:`);
  try {
    await api(`/api/overlaps/${linkId}/resolve`, "POST", { status, remarks });
    alert(`Overlap link marked as ${status} successfully.`);
    loadScreenData();
  } catch (err) {
    alert("Error: " + err.message);
  }
}

// Render Active Modal
function renderModal() {
  if (!state.modal) return '';
  const m = state.modal;

  if (m.type === "action") {
    return `
      <div class="fixed inset-0 bg-slate-900/60 z-50 flex items-center justify-center p-4">
        <div class="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6 space-y-4">
          <div class="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 class="font-bold text-base text-slate-900">
              Record Case Movement: <span class="text-blue-700">${m.actionType}</span>
            </h3>
            <button onclick="state.modal = null; render();" class="text-slate-400 hover:text-slate-600">&times;</button>
          </div>

          <form onsubmit="handleActionSubmit(event)" class="space-y-4 text-xs">
            ${m.actionType === 'Transfer' ? `
              <div>
                <label class="block font-semibold text-slate-700 mb-1">Transfer Destination Bureau <span class="text-red-500">*</span></label>
                <select id="action-to-bureau" required class="w-full p-2 border border-slate-300 rounded-lg">
                  <option value="RB">Regulation Bureau (RB)</option>
                  <option value="PGRC">Public Grievance Redressal Cell (PGRC)</option>
                  <option value="AB">Approval Bureau (AB)</option>
                  <option value="Legal Cell">Legal Cell</option>
                </select>
              </div>
            ` : ''}

            <div>
              <label class="block font-semibold text-slate-700 mb-1">Action Remarks & Statutory Findings <span class="text-red-500">*</span></label>
              <textarea id="action-remarks" rows="3" required placeholder="Detailed notes for append-only audit trail..." class="w-full p-2.5 border border-slate-300 rounded-lg"></textarea>
            </div>

            <div>
              <label class="block font-semibold text-slate-700 mb-1">Official Document / Notice Reference (Optional)</label>
              <input type="text" id="action-doc-ref" placeholder="e.g. AICTE/RB/NOT/2026/042" class="w-full p-2 border border-slate-300 rounded-lg font-mono">
            </div>

            <div>
              <label class="block font-semibold text-slate-700 mb-1">Next Expected Action</label>
              <input type="text" id="action-next" placeholder="e.g. Scrutiny of compliance affidavit" class="w-full p-2 border border-slate-300 rounded-lg">
            </div>

            <div class="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button type="button" onclick="state.modal = null; render();" class="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50">
                Cancel
              </button>
              <button type="submit" class="px-5 py-2 bg-blue-700 hover:bg-blue-800 text-white font-semibold rounded-lg shadow">
                Save to Audit Trail
              </button>
            </div>
          </form>
        </div>
      </div>
    `;
  } else if (m.type === "new_case_result") {
    const res = m.data;
    return `
      <div class="fixed inset-0 bg-slate-900/60 z-50 flex items-center justify-center p-4">
        <div class="bg-white rounded-xl shadow-2xl max-w-xl w-full p-6 space-y-4">
          <div class="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 class="font-bold text-base text-emerald-700 flex items-center gap-1.5">
              <span>&#10003;</span> Complaint Registered Successfully!
            </h3>
            <button onclick="state.modal = null; navigateTo('cases');" class="text-slate-400 hover:text-slate-600">&times;</button>
          </div>

          <div class="p-3 bg-slate-50 rounded-lg text-xs space-y-1">
            <div>Case Reference: <strong class="text-blue-900 font-mono">${res.case.case_no}</strong></div>
            <div>Institution Resolved: <strong>${res.resolution_info.institution_name}</strong> (${res.resolution_info.confidence}% confidence)</div>
            <div class="text-slate-500 text-[11px]">${res.resolution_info.reason}</div>
          </div>

          <!-- OVERLAP WARNING IF DETECTED -->
          ${res.overlaps_detected ? `
            <div class="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-lg space-y-2">
              <div class="text-xs font-bold text-amber-900 flex items-center gap-1">
                <span>&#9888;</span> Potential Overlapping Cases – Coordination Required
              </div>
              <p class="text-xs text-amber-800">${res.overlaps[0].reason}</p>
              <div class="pt-1">
                <button onclick="state.modal = null; navigateTo('overlaps')" class="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded shadow">
                  Inspect Conflict in Overlap Center &rarr;
                </button>
              </div>
            </div>
          ` : `
            <div class="p-3 bg-emerald-50 text-emerald-800 text-xs rounded-lg border border-emerald-200">
              Zero overlapping cases detected. This complaint has been routed solely to ${res.case.bureau} Bureau.
            </div>
          `}

          <div class="flex justify-end pt-2">
            <button onclick="state.modal = null; navigateTo('case-detail', { caseId: res.case.id })" class="px-4 py-2 bg-blue-700 text-white text-xs font-semibold rounded-lg shadow">
              Open Case Detail &rarr;
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

// Screen 8: Login
function renderLogin() {
  return `
    <div class="min-h-screen flex items-center justify-center bg-slate-100 py-12 px-4 sm:px-6 lg:px-8">
      <div class="max-w-md w-full space-y-6 bg-white p-8 rounded-2xl shadow-xl border border-slate-200">
        
        <div class="text-center">
          <div class="w-16 h-16 rounded-full bg-white flex items-center justify-center p-2 shadow-inner border-2 border-amber-400 mx-auto mb-3">
            <svg viewBox="0 0 100 100" class="w-12 h-12">
              <circle cx="50" cy="50" r="45" fill="#0b2545" stroke="#ff9933" stroke-width="4"/>
              <circle cx="50" cy="50" r="28" fill="#fff"/>
              <circle cx="50" cy="50" r="20" fill="#138808"/>
              <path d="M50 20 L50 80 M20 50 L80 50" stroke="#ff9933" stroke-width="3"/>
              <text x="50" y="55" font-size="12" font-weight="bold" fill="#fff" text-anchor="middle">AICTE</text>
            </svg>
          </div>
          <h2 class="text-lg font-bold text-slate-900 tracking-tight">AICTE Official Grievance Portal</h2>
          <p class="text-xs text-slate-500 mt-1">Integrated Institution Complaint Monitoring & Overlap Dashboard</p>
        </div>

        <div class="bg-amber-50 border border-amber-200 p-4 rounded-xl text-xs space-y-2">
          <div class="font-bold text-amber-900 uppercase tracking-wider">1-Click Demo Logins for SIH Evaluators:</div>
          <div class="space-y-1.5">
            ${DEMO_USERS.map(u => `
              <button onclick="switchUser('${u.email}')" class="w-full text-left px-3 py-2 bg-white hover:bg-amber-100 border border-amber-300 rounded-lg flex items-center justify-between text-xs font-semibold text-slate-800 shadow-2xs">
                <span>${u.role}</span>
                <span class="text-[11px] text-amber-800 font-mono font-normal">${u.email.split('@')[0]}</span>
              </button>
            `).join('')}
          </div>
        </div>

        <div class="text-center text-[11px] text-slate-400">
          Smart India Hackathon Prototype &bull; Centralized AICTE Inter-Bureau Telemetry
        </div>

      </div>
    </div>
  `;
}

// Master Render Function
function render() {
  const app = document.getElementById("app");
  if (!app) return;

  if (state.currentScreen === "login") {
    app.innerHTML = renderLogin();
    return;
  }

  app.innerHTML = `
    ${renderNavbar()}
    <main class="flex-1 pb-12">
      ${
        state.currentScreen === "dashboard" ? renderDashboard() :
        state.currentScreen === "cases" ? renderCasesList() :
        state.currentScreen === "case-detail" ? renderCaseDetail() :
        state.currentScreen === "institution" ? renderInstitutionProfile() :
        state.currentScreen === "overlaps" ? renderOverlapCenter() :
        state.currentScreen === "new-case" ? renderNewCase() :
        state.currentScreen === "reports" ? renderReports() : renderDashboard()
      }
    </main>
    <footer class="bg-white border-t border-slate-200 py-4 text-center text-xs text-slate-500">
      All India Council for Technical Education (AICTE) &bull; Integrated Institution Complaint Monitoring System &bull; SIH 2026
    </footer>
    ${renderModal()}
  `;
}

// Initial Boot
document.addEventListener("DOMContentLoaded", () => {
  render();
  loadScreenData();
});
