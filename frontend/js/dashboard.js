/**
 * Smart LPG Leak Detection & Automatic Shut-Off System
 * Dashboard Client-Side Controller
 */

document.addEventListener("DOMContentLoaded", () => {
  // ---------------------------------------------------------------------------
  // State & DOM Elements
  // ---------------------------------------------------------------------------
  let isSimRunning = true;
  let chart = null;
  let activeModalAction = null;

  const riskCard = document.getElementById("risk-card");
  const riskLevelBadge = document.getElementById("risk-level-badge");
  const riskReasonText = document.getElementById("risk-reason-text");
  const filteredGasVal = document.getElementById("filtered-gas-val");
  const rawGasVal = document.getElementById("raw-gas-val");
  const rocVal = document.getElementById("roc-val");
  const rorBadge = document.getElementById("ror-badge");
  const tempVal = document.getElementById("temp-val");
  const humVal = document.getElementById("hum-val");

  const valveIcon = document.getElementById("valve-icon");
  const valveStateText = document.getElementById("valve-state-text");
  const valveAngleText = document.getElementById("valve-angle-text");
  const valveDescText = document.getElementById("valve-desc-text");
  const valveSourceBadge = document.getElementById("valve-source-badge");

  const sensorHealthBadge = document.getElementById("sensor-health-badge");
  const ledWarning = document.getElementById("led-warning");
  const ledDanger = document.getElementById("led-danger");
  const buzzerTag = document.getElementById("buzzer-tag");
  const mlStatusText = document.getElementById("ml-status-text");
  const mlScoreText = document.getElementById("ml-score-text");

  const simStatusDot = document.getElementById("sim-status-dot");
  const simStatusLabel = document.getElementById("sim-status-label");
  const btnToggleSim = document.getElementById("btn-toggle-sim");
  const btnResetScenario = document.getElementById("btn-reset-scenario");
  const scenarioSelect = document.getElementById("scenarioSelect");

  const btnValveOpen = document.getElementById("btn-valve-open");
  const btnValveClose = document.getElementById("btn-valve-close");
  const btnSystemReset = document.getElementById("btn-system-reset");

  const confirmModal = document.getElementById("confirmModal");
  const modalTitle = document.getElementById("modalTitle");
  const modalBody = document.getElementById("modalBody");
  const btnModalCancel = document.getElementById("btn-modal-cancel");
  const btnModalProceed = document.getElementById("btn-modal-proceed");

  const eventsTableBody = document.getElementById("eventsTableBody");
  const filterEventType = document.getElementById("filterEventType");
  const filterRiskLevel = document.getElementById("filterRiskLevel");
  const btnRefreshEvents = document.getElementById("btn-refresh-events");

  // ---------------------------------------------------------------------------
  // Chart Initialization (Chart.js)
  // ---------------------------------------------------------------------------
  function initChart() {
    const ctx = document.getElementById("gasChart")?.getContext("2d");
    if (!ctx) return;

    chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Raw Gas (ppm)",
            data: [],
            borderColor: "rgba(148, 163, 184, 0.4)",
            borderWidth: 1.5,
            borderDash: [2, 2],
            pointRadius: 0,
            fill: false,
            tension: 0.2
          },
          {
            label: "Filtered Gas (EMA)",
            data: [],
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.08)",
            borderWidth: 2.5,
            pointRadius: 2,
            pointHoverRadius: 5,
            fill: true,
            tension: 0.3
          },
          {
            label: "Warning Limit (200 ppm)",
            data: [],
            borderColor: "#f59e0b",
            borderWidth: 1.5,
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false
          },
          {
            label: "Danger Limit (400 ppm)",
            data: [],
            borderColor: "#f97316",
            borderWidth: 1.5,
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false
          },
          {
            label: "Critical Limit (700 ppm)",
            data: [],
            borderColor: "#ef4444",
            borderWidth: 2,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        scales: {
          x: {
            grid: { color: "#1e293b" },
            ticks: { color: "#64748b", font: { size: 10 } }
          },
          y: {
            min: 0,
            suggestedMax: 800,
            grid: { color: "#1e293b" },
            ticks: { color: "#94a3b8", font: { size: 11 } }
          }
        },
        plugins: {
          legend: {
            position: "top",
            labels: { color: "#cbd5e1", boxWidth: 12, font: { size: 11 } }
          },
          tooltip: {
            mode: "index",
            intersect: false,
            backgroundColor: "#1e293b",
            borderColor: "#334155",
            borderWidth: 1
          }
        }
      }
    });

    // Populate chart with recent historical points from backend
    fetch("/api/sensors?limit=30")
      .then(res => res.json())
      .then(data => {
        data.forEach(item => {
          const tLabel = item.timestamp ? item.timestamp.substring(11, 19) : "";
          chart.data.labels.push(tLabel);
          chart.data.datasets[0].data.push(item.raw_gas);
          chart.data.datasets[1].data.push(item.filtered_gas);
          chart.data.datasets[2].data.push(200.0);
          chart.data.datasets[3].data.push(400.0);
          chart.data.datasets[4].data.push(700.0);
        });
        chart.update("none");
      })
      .catch(() => {});
  }

  // ---------------------------------------------------------------------------
  // Status Polling (/api/status)
  // ---------------------------------------------------------------------------
  async function pollStatus() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) throw new Error("HTTP error " + res.status);
      const data = await res.json();
      updateDashboardUI(data);
    } catch (err) {
      simStatusDot.style.background = "#64748b";
      simStatusLabel.textContent = "OFFLINE";
    }
  }

  function updateDashboardUI(data) {
    // 1. Simulation status badge
    isSimRunning = data.simulation_running;
    if (isSimRunning) {
      simStatusDot.style.background = "var(--safe)";
      simStatusDot.className = "status-dot pulsing";
      simStatusLabel.textContent = `SIM RUNNING (${data.active_scenario})`;
      btnToggleSim.textContent = "⏸️ Pause Sim";
    } else {
      simStatusDot.style.background = "var(--warning)";
      simStatusDot.className = "status-dot";
      simStatusLabel.textContent = `SIM PAUSED (${data.active_scenario})`;
      btnToggleSim.textContent = "▶️ Resume Sim";
    }

    if (scenarioSelect.value !== data.active_scenario) {
      scenarioSelect.value = data.active_scenario;
    }

    // 2. Risk Level Card
    riskCard.className = `card risk-card ${data.risk_level}`;
    riskLevelBadge.textContent = data.risk_level;
    riskReasonText.textContent = data.sensor_health === "FAULT" 
      ? data.sensor_health_reason 
      : `${data.risk_level} condition active`;

    // 3. Gas Metrics
    filteredGasVal.textContent = data.filtered_gas.toFixed(1);
    rawGasVal.textContent = data.raw_gas.toFixed(1);
    rocVal.textContent = (data.rate_of_change >= 0 ? "+" : "") + data.rate_of_change.toFixed(1);
    
    // Rate of Rise surge badge
    const rorRate = data.rate_per_second;
    rorBadge.textContent = `RoR: ${(rorRate >= 0 ? "+" : "") + rorRate.toFixed(1)} ppm/s`;
    if (data.rapid_rise_detected) {
      rorBadge.className = "ror-badge surge";
      rorBadge.textContent = `⚠️ SURGE: +${rorRate.toFixed(1)} ppm/s`;
    } else {
      rorBadge.className = "ror-badge";
    }

    tempVal.textContent = data.temperature.toFixed(1);
    humVal.textContent = data.humidity.toFixed(1);

    // 4. Valve Actuator
    valveStateText.textContent = data.valve_state;
    valveIcon.className = `valve-icon-wrapper ${data.valve_state}`;
    valveAngleText.textContent = `Servo: ${data.valve_angle_deg.toFixed(1)}°`;
    valveSourceBadge.textContent = data.valve_last_source;

    if (data.valve_state === "OPEN") {
      valveStateText.style.color = "var(--safe)";
      valveDescText.textContent = "Gas supply open and operating";
    } else if (data.valve_state === "CLOSING") {
      valveStateText.style.color = "var(--warning)";
      valveDescText.textContent = "Shut-off in progress...";
    } else {
      valveStateText.style.color = "var(--critical)";
      valveDescText.textContent = "Gas supply isolated (Locked)";
    }

    // 5. Sensor Health & Peripherals
    sensorHealthBadge.textContent = data.sensor_health;
    if (data.sensor_health === "NORMAL") {
      sensorHealthBadge.style.color = "var(--safe)";
    } else if (data.sensor_health === "WARNING") {
      sensorHealthBadge.style.color = "var(--warning)";
    } else {
      sensorHealthBadge.style.color = "var(--critical)";
    }

    // LEDs
    ledWarning.className = data.warning_led ? "led warn active" : "led warn";
    if (data.danger_led) {
      ledDanger.className = data.risk_level === "CRITICAL" ? "led danger active pulsing" : "led danger active";
    } else {
      ledDanger.className = "led danger";
    }

    // Buzzer
    buzzerTag.textContent = data.buzzer_state;
    buzzerTag.className = `buzzer-state-tag ${data.buzzer_state}`;

    // ML Anomaly
    if (data.is_anomaly) {
      mlStatusText.textContent = "ANOMALY";
      mlStatusText.style.color = "var(--danger)";
    } else {
      mlStatusText.textContent = "NORMAL";
      mlStatusText.style.color = "var(--safe)";
    }

    // 6. Push to Chart (Rolling window of 35 points)
    if (chart) {
      const timeStr = data.timestamp ? data.timestamp.substring(11, 19) : "";
      chart.data.labels.push(timeStr);
      chart.data.datasets[0].data.push(data.raw_gas);
      chart.data.datasets[1].data.push(data.filtered_gas);
      chart.data.datasets[2].data.push(data.thresholds.warning_threshold);
      chart.data.datasets[3].data.push(data.thresholds.danger_threshold);
      chart.data.datasets[4].data.push(data.thresholds.critical_threshold);

      if (chart.data.labels.length > 35) {
        chart.data.labels.shift();
        chart.data.datasets.forEach(d => d.data.shift());
      }
      chart.update("none");
    }
  }

  // ---------------------------------------------------------------------------
  // Event Log Table (/api/events)
  // ---------------------------------------------------------------------------
  async function fetchEvents() {
    try {
      let url = "/api/events?limit=25";
      const evType = filterEventType.value;
      const rLevel = filterRiskLevel.value;
      if (evType) url += `&event_type=${encodeURIComponent(evType)}`;
      if (rLevel) url += `&risk_level=${encodeURIComponent(rLevel)}`;

      const res = await fetch(url);
      if (!res.ok) return;
      const events = await res.json();
      renderEvents(events);
    } catch (err) {}
  }

  function renderEvents(events) {
    if (!events || events.length === 0) {
      eventsTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim);">No events match the selected filter.</td></tr>`;
      return;
    }

    eventsTableBody.innerHTML = events.map(ev => {
      const timeFormatted = ev.timestamp ? ev.timestamp.replace("T", " ").substring(0, 19) : "";
      const badgeClass = ev.risk_level || "INFO";
      return `
        <tr>
          <td style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">${timeFormatted}</td>
          <td><span class="event-badge ${badgeClass}">${ev.event_type}</span></td>
          <td><strong style="color: var(--${(ev.risk_level||'SAFE').toLowerCase()});">${ev.risk_level}</strong></td>
          <td style="font-family: var(--font-mono);">${ev.gas_value.toFixed(1)}</td>
          <td><span style="font-family: var(--font-mono); font-size: 0.75rem;">${ev.valve_state}</span></td>
          <td style="color: var(--text-muted);">${escapeHtml(ev.description)}</td>
        </tr>
      `;
    }).join("");
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ---------------------------------------------------------------------------
  // Controls & Modal Confirmation
  // ---------------------------------------------------------------------------
  scenarioSelect.addEventListener("change", async (e) => {
    try {
      const res = await fetch("/api/scenario", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: e.target.value })
      });
      const data = await res.json();
      showToast(data.message || `Switched to ${e.target.value}`);
      fetchEvents();
    } catch (err) {
      showToast("Failed to switch scenario", "error");
    }
  });

  btnToggleSim.addEventListener("click", async () => {
    try {
      const endpoint = isSimRunning ? "/api/simulation/stop" : "/api/simulation/start";
      const res = await fetch(endpoint, { method: "POST" });
      const data = await res.json();
      showToast(data.message);
      pollStatus();
      fetchEvents();
    } catch (err) {
      showToast("Failed to toggle simulation", "error");
    }
  });

  btnResetScenario.addEventListener("click", async () => {
    try {
      await fetch("/api/scenario", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: "NORMAL" })
      });
      scenarioSelect.value = "NORMAL";
      showToast("Simulation reset to baseline clean air");
      fetchEvents();
    } catch (err) {
      showToast("Failed to reset scenario", "error");
    }
  });

  // Modal open helpers
  function openConfirmModal(action, title, bodyText) {
    activeModalAction = action;
    modalTitle.textContent = title;
    modalBody.textContent = bodyText;
    confirmModal.classList.add("active");
  }

  btnModalCancel.addEventListener("click", () => {
    confirmModal.classList.remove("active");
    activeModalAction = null;
  });

  btnModalProceed.addEventListener("click", async () => {
    confirmModal.classList.remove("active");
    if (!activeModalAction) return;

    try {
      let res;
      if (activeModalAction === "OPEN_VALVE") {
        res = await fetch("/api/valve/open", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmed: true })
        });
      } else if (activeModalAction === "CLOSE_VALVE") {
        res = await fetch("/api/valve/close", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmed: true })
        });
      } else if (activeModalAction === "RESET_SYSTEM") {
        res = await fetch("/api/system/reset", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmed: true })
        });
      }

      const data = await res.json();
      if (!res.ok) {
        showToast(data.detail || "Operation rejected by safety system", "error");
      } else {
        showToast(data.message || "Action executed successfully");
      }
      pollStatus();
      fetchEvents();
    } catch (err) {
      showToast("Network request failed", "error");
    } finally {
      activeModalAction = null;
    }
  });

  btnValveClose.addEventListener("click", () => {
    openConfirmModal(
      "CLOSE_VALVE",
      "Confirm Emergency Manual Shut-Off",
      "Are you sure you want to manually close the simulated safety valve? Gas supply will be isolated immediately."
    );
  });

  btnValveOpen.addEventListener("click", () => {
    openConfirmModal(
      "OPEN_VALVE",
      "Confirm Manual Valve Reopening",
      "WARNING: Opening the valve will restore gas supply. Ensure no hazardous gas concentrations or active leaks are present."
    );
  });

  btnSystemReset.addEventListener("click", () => {
    openConfirmModal(
      "RESET_SYSTEM",
      "Confirm System & Lockout Reset",
      "Resetting will clear the automatic safety latch, clear fault flags, and return the valve to normal OPEN state if the gas concentration has cleared."
    );
  });

  filterEventType.addEventListener("change", fetchEvents);
  filterRiskLevel.addEventListener("change", fetchEvents);
  btnRefreshEvents.addEventListener("click", fetchEvents);

  // ---------------------------------------------------------------------------
  // Toast Helper
  // ---------------------------------------------------------------------------
  function showToast(msg, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = "toast";
    if (type === "error") {
      toast.style.borderColor = "var(--critical)";
      toast.style.color = "#fca5a5";
    }
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  // ---------------------------------------------------------------------------
  // Start Periodic Polling Loops
  // ---------------------------------------------------------------------------
  initChart();
  pollStatus();
  fetchEvents();

  setInterval(pollStatus, 1000);   // Telemetry every 1 second
  setInterval(fetchEvents, 3000);  // Event log every 3 seconds
});
