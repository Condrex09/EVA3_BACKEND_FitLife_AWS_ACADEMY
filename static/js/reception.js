/**
 * FitLife - Validación de Pases QR en Recepción
 * Integra lector de código USB con autofocus + cámara web en vivo (html5-qrcode) + simulador
 * Autor: Benjamin Gomez · Sección AP-N4-C1 · INACAP
 */

let html5QrScanner = null;
let isProcessingScan = false;

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

async function sendQRValidation(qrToken) {
  if (isProcessingScan) return;
  isProcessingScan = true;

  const resultContainer = document.getElementById('qrResultCard');
  const resultTitle = document.getElementById('qrResultTitle');
  const resultMessage = document.getElementById('qrResultMessage');
  const resultMember = document.getElementById('qrResultMember');
  const resultMeta = document.getElementById('qrResultMeta');
  const manualInput = document.getElementById('manualQrInput');

  // Mostrar estado de carga
  if (resultContainer) {
    resultContainer.style.display = 'block';
    resultContainer.style.borderColor = '#FFC400';
    resultContainer.style.backgroundColor = 'rgba(255, 196, 0, 0.1)';
    resultTitle.textContent = 'VALIDANDO...';
    resultTitle.style.color = '#FFC400';
    resultMessage.textContent = 'Consultando antecedentes en la base de datos...';
    resultMember.innerHTML = '';
    resultMeta.innerHTML = '';
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
      resultTitle.textContent = `✓ ACCESO PERMITIDO (${(data.direction_display || 'ENTRADA').toUpperCase()})`;
      resultTitle.style.color = '#28A745';
      resultMessage.textContent = data.message;
      
      const initial = (data.member_name || 'S').charAt(0).toUpperCase();
      let alertBanner = '';
      if (data.expiring_soon) {
        alertBanner = `
          <div style="margin-top: 14px; background: #332600; border: 1.5px solid #FFC107; color: #FFE082; padding: 12px; border-radius: 8px; font-weight: 800; font-size: 0.95rem;">
            <i class="fa-solid fa-triangle-exclamation"></i> AVISAR AL SOCIO: Su membresía vence en ${data.days_remaining} días (${data.end_date}). Sugerir renovación en caja.
          </div>
        `;
      }

      resultMember.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 6px;">
          <div style="width: 48px; height: 48px; border-radius: 50%; background: #28A745; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 1.4rem; font-weight: 900;">
            ${initial}
          </div>
          <div style="text-align: left;">
            <div style="font-size: 1.3rem; font-weight: 800; color: #fff;">${data.member_name}</div>
            <div style="font-size: 0.85rem; color: #ccc;">RUT: ${data.rut}</div>
          </div>
        </div>
        ${alertBanner}
      `;
      resultMeta.innerHTML = `<strong>Plan:</strong> ${data.plan_name} &middot; <strong>Vencimiento:</strong> ${data.end_date} &middot; <strong>Hora:</strong> ${data.timestamp}`;
    } else {
      // ACCESO DENEGADO (Rojo)
      resultContainer.style.borderColor = '#DC3545';
      resultContainer.style.backgroundColor = 'rgba(220, 53, 69, 0.15)';
      resultTitle.textContent = '✗ ACCESO DENEGADO';
      resultTitle.style.color = '#DC3545';
      resultMessage.textContent = data.message || 'El socio no cumple con los requisitos de acceso.';
      
      const memberInfo = data.member_name ? `<strong>Socio:</strong> ${data.member_name} &middot; <strong>RUT:</strong> ${data.rut || '-'}` : 'Código QR no reconocido o sin socio asociado.';
      resultMember.innerHTML = `<div style="font-size: 1.1rem; color: #ff8b8b; margin-bottom: 4px;">${memberInfo}</div>`;
      resultMeta.innerHTML = `<strong>Motivo:</strong> ${data.reason || 'DENEGADO'} &middot; <strong>Hora:</strong> ${data.timestamp}`;
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
    // Reenfocar automáticamente para el siguiente escaneo (lector USB)
    if (manualInput) {
      manualInput.value = '';
      manualInput.focus();
    }
    setTimeout(() => {
      isProcessingScan = false;
    }, 1500);
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

  if (tableBody.children.length > 10) {
    tableBody.removeChild(tableBody.lastChild);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
  const isSecure = window.isSecureContext || isLocal;
  const warningEl = document.getElementById('insecureContextWarning');
  if (!isSecure && warningEl) {
    warningEl.style.display = 'block';
  }

  const manualForm = document.getElementById('manualQrForm');
  const manualInput = document.getElementById('manualQrInput');
  const demoSelect = document.getElementById('demoTokenSelect');

  // Autofocus en el input para lector de código de barras USB
  if (manualInput) {
    manualInput.focus();
  }

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
        if (demoSelect) demoSelect.value = '';
      }
    });
  }

  // Cámara web si el contexto es seguro
  const qrReaderContainer = document.getElementById('qr-reader');
  if (qrReaderContainer && typeof Html5QrcodeScanner !== 'undefined' && isSecure) {
    try {
      html5QrScanner = new Html5QrcodeScanner(
        "qr-reader",
        { fps: 10, qrbox: { width: 250, height: 250 } },
        /* verbose= */ false
      );
      html5QrScanner.render((decodedText) => {
        sendQRValidation(decodedText);
      }, (error) => {
        // Ignorar frame vacío
      });
    } catch (err) {
      console.warn("No se pudo iniciar el escáner de cámara:", err);
    }
  }
});
