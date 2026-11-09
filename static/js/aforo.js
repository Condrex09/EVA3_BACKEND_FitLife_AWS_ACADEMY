/**
 * FitLife - Dashboard de Aforo en Tiempo Real
 * Consume /api/aforo/ mediante fetch cada 5 segundos
 * Autor: Benjamin Gomez · Sección AP-N4-C1 · INACAP
 */

let aforoChart = null;

function initAforoChart(labels, data) {
  const ctx = document.getElementById('aforoChart');
  if (!ctx) return;

  aforoChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Ingresos por Hora',
        data: data,
        backgroundColor: '#FFC400',
        borderColor: '#E0AB00',
        borderWidth: 1,
        borderRadius: 4,
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
          backgroundColor: '#111111',
          titleColor: '#FFC400',
          bodyColor: '#FFFFFF',
          borderColor: '#383838',
          borderWidth: 1
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            color: '#AAAAAA',
            precision: 0
          },
          grid: {
            color: 'rgba(255, 255, 255, 0.05)'
          }
        },
        x: {
          ticks: {
            color: '#AAAAAA'
          },
          grid: {
            display: false
          }
        }
      }
    }
  });
}

async function fetchAforoData() {
  try {
    const response = await fetch('/api/aforo/', {
      headers: {
        'Accept': 'application/json',
      }
    });
    if (!response.ok) return;

    const data = await response.json();

    // 1. Actualizar números principales
    const currentCountEl = document.getElementById('aforoCurrentCount');
    const maxCapacityEl = document.getElementById('aforoMaxCapacity');
    const percentageEl = document.getElementById('aforoPercentage');
    const statusPillEl = document.getElementById('aforoStatusPill');
    const progressBarEl = document.getElementById('aforoProgressBar');

    if (currentCountEl) currentCountEl.textContent = data.current_count;
    if (maxCapacityEl) maxCapacityEl.textContent = data.max_capacity;
    if (percentageEl) percentageEl.textContent = `${data.percentage}%`;

    // 2. Colores semáforo y banner de alerta crítica
    const dangerBanner = document.getElementById('aforoDangerBanner');
    if (dangerBanner) {
      dangerBanner.style.display = (data.status_color === 'red') ? 'flex' : 'none';
    }

    if (progressBarEl) {
      progressBarEl.style.width = `${Math.min(100, data.percentage)}%`;
      progressBarEl.className = 'progress-bar-fill';
      if (data.status_color === 'red') {
        progressBarEl.classList.add('progress-fill-red');
      } else if (data.status_color === 'yellow') {
        progressBarEl.classList.add('progress-fill-yellow');
      } else {
        progressBarEl.classList.add('progress-fill-green');
      }
    }

    if (statusPillEl) {
      statusPillEl.textContent = data.status_text;
      statusPillEl.className = 'badge';
      if (data.status_color === 'red') {
        statusPillEl.classList.add('badge-high');
      } else if (data.status_color === 'yellow') {
        statusPillEl.classList.add('badge-medium');
      } else {
        statusPillEl.classList.add('badge-low');
      }
    }

    // 3. Actualizar gráfico Chart.js
    if (aforoChart && data.hourly_labels && data.hourly_data) {
      aforoChart.data.labels = data.hourly_labels;
      aforoChart.data.datasets[0].data = data.hourly_data;
      aforoChart.update();
    }

    // 4. Actualizar lista de personas adentro
    const insideTableBody = document.getElementById('peopleInsideTableBody');
    if (insideTableBody && data.people_inside) {
      if (data.people_inside.length === 0) {
        insideTableBody.innerHTML = `<tr><td colspan="3" class="text-center" style="color: #888;">No hay socios registrados dentro en este momento.</td></tr>`;
      } else {
        insideTableBody.innerHTML = data.people_inside.map((p, idx) => `
          <tr>
            <td><strong>#${idx + 1}</strong></td>
            <td>${p.name} <small style="color: #888;">(${p.rut})</small></td>
            <td><span class="badge badge-low">${p.entry_time}</span></td>
          </tr>
        `).join('');
      }
    }

  } catch (error) {
    console.error("Error al actualizar aforo:", error);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Inicialización inicial
  const chartCanvas = document.getElementById('aforoChart');
  if (chartCanvas) {
    initAforoChart([], []);
    fetchAforoData();
    // Polling regular cada 5 segundos
    setInterval(fetchAforoData, 5000);
  }
});

