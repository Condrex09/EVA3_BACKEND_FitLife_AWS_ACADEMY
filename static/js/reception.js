/**
 * FitLife - Validación de Pases QR en Recepción
 * Integra cámara web en vivo (html5-qrcode) + simulador manual por token
 * Autor: Benjamin Gomez · Sección AP-N4-C1 · INACAP
 */

let html5QrScanner = null;
let isProcessingScan = false;

async function sendQRValidation(qrToken) {
  if (isProcessingScan) return;
  isProcessingScan = true;

  const resultContainer = document.getElementById('qrResultCard');
  const resultTitle = document.getElementById('qrResultTitle');
  const resultMessage = document.getElementById('qrResultMessage');
  const resultMember = document.getElementById('qrResultMember');
  const resultMeta = document.getElementById('qrResultMeta');

  // Mostrar estado de carga
  if (resultContainer) {
    resultContainer.style.display = 'block';
    resultContainer.style.borderColor = '#FFC400';
    resultTitle.textContent = 'VALIDANDO...';
    resultTitle.style.color = '#FFC400';
    resultMessage.textContent = 'Consultando antecedentes en la base de datos...';
  }

  try {
    const csrftoken = getCookie('csrftoken');
    const response = await fetch('/api/access/validate/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrftoken,
      },
      body: JSON.stringify({ qr_token: qrToken })
    });

    const data = await response.json();

    if (data.allowed) {
      // ACCESO PERMITIDO (Verde)
      resultContainer.style.borderColor = '#28A745';
      resultContainer.style.backgroundColor = 'rgba(40, 167, 69, 0.15)';
      resultTitle.textContent = `✓ ACCESO PERMITIDO (${data.direction_display.toUpperCase()})`;
      resultTitle.style.color = '#28A745';
      resultMessage.textContent = data.message;
      resultMember.innerHTML = `<strong>Socio:</strong> ${data.member_name} · <strong>RUT:</strong> ${data.rut}`;
      resultMeta.innerHTML = `<strong>Plan:</strong> ${data.plan_name} · <strong>Vence:</strong> ${data.end_date} · <strong>Hora:</strong> ${data.timestamp}`;
    } else {
      // ACCESO DENEGADO (Rojo)
      resultContainer.style.borderColor = '#DC3545';
      resultContainer.style.backgroundColor = 'rgba(220, 53, 69, 0.15)';
      resultTitle.textContent = '✗ ACCESO DENEGADO';
      resultTitle.style.color = '#DC3545';
      resultMessage.textContent = data.message || 'Motivo de rechazo de acceso.';
      resultMember.innerHTML = data.member_name ? `<strong>Socio:</strong> ${data.member_name} · <strong>RUT:</strong> ${data.rut || '-'}` : 'Código QR no asociado a socio.';
      resultMeta.innerHTML = `<strong>Motivo:</strong> ${data.reason || 'DENEGADO'} · <strong>Hora:</strong> ${data.timestamp}`;
    }

    // Agregar fila a la tabla histórica en vivo
    prependLogToTable(data);

  } catch (error) {
    console.error("Error en validación QR:", error);
    if (resultContainer) {
      resultTitle.textContent = 'ERROR DE CONEXIÓN';
      resultTitle.style.color = '#DC3545';
      resultMessage.textContent = 'No fue posible comunicar con el servidor backend.';
    }
  } finally {
    // Pausa breve para evitar lecturas consecutivas idénticas
    setTimeout(() => {
      isProcessingScan = false;
    }, 2000);
  }
}

function prependLogToTable(data) {
  const tableBody = document.getElementById('recentLogsTableBody');
  if (!tableBody) return;

  const row = document.createElement('tr');
  const isAllowed = data.allowed;
  const resultBadge = isAllowed 
    ? `<span class="badge badge-low">PERMITIDO</span>`
    : `<span class="badge badge-high">DENEGADO</span>`;
  const dirBadge = data.direction_display 
    ? `<span class="badge ${data.direction === 'IN' ? 'badge-low' : 'badge-medium'}">${data.direction_display}</span>`
    : `<span class="badge badge-medium">Intento</span>`;

  row.innerHTML = `
    <td><strong>${data.timestamp}</strong></td>
    <td>${data.member_name || 'Desconocido'}</td>
    <td>${dirBadge}</td>
    <td>${resultBadge}</td>
    <td><small>${data.message || data.reason || '-'}</small></td>
  `;

  tableBody.insertBefore(row, tableBody.firstChild);

  // Mantener máximo 10 filas visibles
  if (tableBody.children.length > 10) {
    tableBody.removeChild(tableBody.lastChild);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // 1. Detección de contexto seguro para la cámara web (Tarea 9.2)
  const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
  const isSecure = window.isSecureContext || isLocal;
  const warningEl = document.getElementById('insecureContextWarning');
  if (!isSecure && warningEl) {
    warningEl.style.display = 'block';
  }

  // 2. Manejo del formulario manual de simulación y selector demo (Tarea 9.3)
  const manualForm = document.getElementById('manualQrForm');
  const manualInput = document.getElementById('manualQrInput');
  const demoSelect = document.getElementById('demoTokenSelect');

  if (demoSelect && manualInput) {
    demoSelect.addEventListener('change', () => {
      if (demoSelect.value) {
        manualInput.value = demoSelect.value;
        manualInput.focus();
      }
    });
  }

  if (manualForm && manualInput) {
    manualForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const token = manualInput.value.trim();
      if (token) {
        sendQRValidation(token);
        manualInput.value = '';
        if (demoSelect) demoSelect.value = '';
      }
    });
  }

  // 3. Inicialización del escáner por cámara web (html5-qrcode) si el contexto es seguro
  const qrReaderContainer = document.getElementById('qr-reader');
  if (qrReaderContainer && typeof Html5QrcodeScanner !== 'undefined') {
    try {
      html5QrScanner = new Html5QrcodeScanner(
        "qr-reader",
        { fps: 10, qrbox: { width: 250, height: 250 } },
        /* verbose= */ false
      );
      html5QrScanner.render((decodedText) => {
        sendQRValidation(decodedText);
      }, (error) => {
        // Ignorar errores de frame vacío
      });
    } catch (err) {
      console.warn("No se pudo iniciar el escáner de cámara:", err);
      if (warningEl) warningEl.style.display = 'block';
    }
  }
});

