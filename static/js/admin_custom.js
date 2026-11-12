/**
 * FitLife Django Admin Enhancements
 * Auto-cierre de mensajes tras 6 segundos, traducciones visuales y accesibilidad.
 * Desarrollado por Benjamin Gomez · Sección AP-N4-C1 · INACAP · EVA 3
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Mensajes del sistema: agregar botón de cerrar y auto-ocultar a los 6 segundos
  const messageItems = document.querySelectorAll('ul.messagelist li');
  messageItems.forEach(function (msg) {
    if (!msg.querySelector('.fitlife-msg-close')) {
      const closeBtn = document.createElement('button');
      closeBtn.className = 'fitlife-msg-close';
      closeBtn.innerHTML = '&times;';
      closeBtn.setAttribute('aria-label', 'Cerrar notificación');
      closeBtn.onclick = function () {
        msg.style.opacity = '0';
        msg.style.transform = 'translateY(-10px)';
        setTimeout(() => msg.remove(), 400);
      };
      msg.appendChild(closeBtn);
    }

    setTimeout(function () {
      if (msg && msg.parentNode) {
        msg.style.opacity = '0';
        msg.style.transform = 'translateY(-10px)';
        setTimeout(function () {
          if (msg && msg.parentNode) {
            msg.remove();
          }
        }, 500);
      }
    }, 6000);
  });

  // 2. Barra de acciones: traducción de opción por defecto y estilo de peligro al seleccionar eliminar
  const actionSelect = document.querySelector('.actions select[name="action"]');
  const actionSubmitBtn = document.querySelector('.actions button[type="submit"]');

  if (actionSelect) {
    const firstOption = actionSelect.options[0];
    if (firstOption && (firstOption.text.includes('---') || firstOption.text.toLowerCase().includes('select'))) {
      firstOption.text = 'Seleccione una acción...';
    }

    actionSelect.addEventListener('change', function () {
      if (actionSubmitBtn) {
        if (this.value && this.value.includes('delete')) {
          actionSubmitBtn.style.background = '#DC3545';
          actionSubmitBtn.style.borderColor = '#DC3545';
          actionSubmitBtn.style.color = '#FFFFFF';
          actionSubmitBtn.innerText = '⚠️ Eliminar';
        } else {
          actionSubmitBtn.style.background = '#FFC400';
          actionSubmitBtn.style.borderColor = '#FFC400';
          actionSubmitBtn.style.color = '#111111';
          actionSubmitBtn.innerText = 'Ejecutar';
        }
      }
    });
  }

  // 3. Traducción en tiempo real de la nota de selección ("X de Y seleccionados")
  const counterSpan = document.querySelector('.action-counter');
  if (counterSpan) {
    const formatCounter = function () {
      const text = counterSpan.innerText;
      if (text.includes('selected') || text.includes('of')) {
        const match = text.match(/(\d+)\s+(?:of|de)\s+(\d+)/);
        if (match) {
          counterSpan.innerText = `${match[1]} de ${match[2]} seleccionados`;
        }
      }
    };
    formatCounter();
    const observer = new MutationObserver(formatCounter);
    observer.observe(counterSpan, { childList: true, characterData: true, subtree: true });
  }

  // 4. Mejoras en filtros laterales (#changelist-filter): colapsable en móvil
  const filterBlock = document.getElementById('changelist-filter');
  if (filterBlock) {
    const filterTitle = filterBlock.querySelector('h2');
    if (filterTitle && window.innerWidth <= 768) {
      filterTitle.style.cursor = 'pointer';
      filterTitle.innerHTML += ' <span style="font-size: 11px; float: right;">[Alternar]</span>';
      const filterUl = filterBlock.querySelectorAll('h3, ul');
      filterUl.forEach(el => el.style.display = 'none');
      let isOpen = false;
      filterTitle.addEventListener('click', function () {
        isOpen = !isOpen;
        filterUl.forEach(el => el.style.display = isOpen ? 'block' : 'none');
      });
    }
  }
});
