/**
 * Smart LPG Leak Detection & Automatic Shut-Off System
 * Analytics & Historical Incident Reporting
 */

document.addEventListener("DOMContentLoaded", () => {
  let hourlyChart = null;

  const kpiMaxGas = document.getElementById("kpi-max-gas");
  const kpiAvgGas = document.getElementById("kpi-avg-gas");
  const kpiWarnings = document.getElementById("kpi-warnings");
  const kpiDangers = document.getElementById("kpi-dangers");
  const kpiShutoffs = document.getElementById("kpi-shutoffs");
  const kpiFaults = document.getElementById("kpi-faults");
  const kpiTime = document.getElementById("kpi-time");
  const btnRefresh = document.getElementById("btn-refresh-analytics");
  const tableBody = document.getElementById("analyticsEventsTableBody");

  function initHourlyChart() {
    const ctx = document.getElementById("hourlyChart")?.getContext("2d");
    if (!ctx) return;

    hourlyChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: [],
        datasets: [
          {
            label: "Max Peak Gas (ppm)",
            data: [],
            backgroundColor: "rgba(249, 115, 22, 0.6)",
            borderColor: "#f97316",
            borderWidth: 1.5,
            borderRadius: 4
          },
          {
            label: "Average Gas (ppm)",
            data: [],
            backgroundColor: "rgba(56, 189, 248, 0.4)",
            borderColor: "#38bdf8",
            borderWidth: 1.5,
            borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            grid: { color: "#1e293b" },
            ticks: { color: "#94a3b8", font: { size: 10 } }
          },
          y: {
            min: 0,
            grid: { color: "#1e293b" },
            ticks: { color: "#94a3b8", font: { size: 11 } }
          }
        },
        plugins: {
          legend: {
            position: "top",
            labels: { color: "#cbd5e1", boxWidth: 12, font: { size: 11 } }
          }
        }
      }
    });
  }

  async function loadAnalytics() {
    try {
      const res = await fetch("/api/analytics");
      if (!res.ok) throw new Error("HTTP error " + res.status);
      const data = await res.json();

      // KPIs
      kpiMaxGas.textContent = data.max_gas_ppm.toFixed(1);
      kpiAvgGas.textContent = data.avg_gas_ppm.toFixed(1);
      kpiWarnings.textContent = data.warning_count;
      kpiDangers.textContent = data.danger_count + data.critical_count;
      kpiShutoffs.textContent = data.shutoff_count;
      kpiFaults.textContent = data.sensor_fault_count;

      // Format monitoring time
      const secs = Math.round(data.total_monitoring_seconds);
      const m = Math.floor(secs / 60);
      const s = secs % 60;
      const h = Math.floor(m / 60);
      if (h > 0) {
        kpiTime.textContent = `${h}h ${m % 60}m`;
      } else {
        kpiTime.textContent = `${m}m ${s}s`;
      }

      // Update Chart
      if (hourlyChart && data.hourly_trends) {
        hourlyChart.data.labels = data.hourly_trends.map(t => t.hour ? t.hour.substring(5) : "");
        hourlyChart.data.datasets[0].data = data.hourly_trends.map(t => t.max_gas);
        hourlyChart.data.datasets[1].data = data.hourly_trends.map(t => t.avg_gas);
        hourlyChart.update();
      }

      // Render recent events
      if (tableBody && data.recent_events) {
        if (data.recent_events.length === 0) {
          tableBody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-dim);">No incident events recorded yet.</td></tr>`;
        } else {
          tableBody.innerHTML = data.recent_events.map(ev => {
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
      }

    } catch (err) {
      console.error("Failed to load analytics", err);
    }
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  initHourlyChart();
  loadAnalytics();

  if (btnRefresh) {
    btnRefresh.addEventListener("click", loadAnalytics);
  }
});

