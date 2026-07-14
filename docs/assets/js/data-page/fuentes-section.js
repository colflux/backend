(function configureFuentesSection(window) {
  window.COLFLUX_DATA = window.COLFLUX_DATA || {};

  function get(id) {
    return document.getElementById(id);
  }

  function render(items) {
    const { escapeHtml } = window.COLFLUX_DATA.dataPage;
    const body = get('fuentesTableBody');
    get('tableCount').textContent = `${items.length} registro${items.length !== 1 ? 's' : ''}`;
    get('sourcesPager').textContent = 'Página 1 de 1';

    if (items.length === 0) {
      body.innerHTML = '<tr><td colspan="7"><div class="state-box">No hay fuentes para mostrar en la tabla.</div></td></tr>';
      return;
    }

    body.innerHTML = items.map(f => {
      const proyecto = f.proyecto
        ? escapeHtml(f.proyecto.nombre)
        : '<span class="source-muted">Sin proyecto</span>';
      const fecha = f.fecha_datos ? escapeHtml(f.fecha_datos) : '<span class="source-muted">Sin fecha</span>';
      const responsable = f.responsable ? escapeHtml(f.responsable) : '<span class="source-muted">Sin responsable</span>';
      const cargaId = f.ultima_carga_importada_id;
      let etlLink;
      if (cargaId) {
        etlLink = `
          <a class="btn-table-action primary" href="etl-datos.html?fuente=${encodeURIComponent(f.id)}&carga=${encodeURIComponent(cargaId)}" title="Ver datos cargados" aria-label="Ver datos cargados">📊</a>
          <a class="btn-table-action" href="etl-mapeo.html?fuente=${encodeURIComponent(f.id)}&carga=${encodeURIComponent(cargaId)}" title="Ver mapeo de columnas" aria-label="Ver mapeo de columnas">🔗</a>
        `;
      } else if (window.COLFLUX_DATA.etlActions.canStartEtl(f)) {
        etlLink = `<a class="btn-table-action primary" href="etl-upload.html?fuente=${encodeURIComponent(f.id)}" title="Iniciar carga" aria-label="Iniciar carga">⬆</a>`;
      } else {
        etlLink = '<span class="source-muted">No aplica carga</span>';
      }

      const completa = f.estado === 'completo';
      const editBtn = completa
        ? '<span class="btn-table-action" title="Ya no se puede editar: la fuente y el archivo quedan bloqueados una vez cargados los datos" aria-label="Edición bloqueada" style="opacity:.4;cursor:not-allowed;">✎</span>'
        : `<button class="btn-table-action" onclick="editFuente(${Number(f.id)})" title="Editar fuente" aria-label="Editar fuente">✎</button>`;
      const puedeBorrar = !completa || window.COLFLUX_ROLE.isAdmin();
      const deleteBtn = puedeBorrar
        ? `<button class="btn-table-action danger" onclick="deleteFuente(${Number(f.id)})" title="Eliminar fuente" aria-label="Eliminar fuente">×</button>`
        : '<span class="btn-table-action" title="Solo un administrador de datos puede borrar una fuente con datos ya cargados" aria-label="Borrado restringido" style="opacity:.4;cursor:not-allowed;">×</span>';

      return `
        <tr>
          <td>
            <div class="source-title">${escapeHtml(f.nombre)}</div>
            <div class="source-muted">ID ${escapeHtml(f.id)}</div>
          </td>
          <td><span class="badge badge-tipo-${escapeHtml(f.tipo)}">${escapeHtml(f.tipo_label)}</span></td>
          <td><span class="badge badge-estado-${escapeHtml(f.estado)}">${escapeHtml(f.estado_label)}</span></td>
          <td>${proyecto}</td>
          <td>${responsable}</td>
          <td>${fecha}</td>
          <td>
            <div class="source-actions">
              ${etlLink}
              ${editBtn}
              ${deleteBtn}
            </div>
          </td>
        </tr>`;
    }).join('');
  }

  function editFuente(id) {
    const fuente = window.COLFLUX_DATA.dataPage.state.data.fuentes.find(f => Number(f.id) === Number(id));
    if (!fuente) return;
    if (fuente.estado === 'completo') {
      alert('Esta fuente ya tiene datos cargados: la fuente y el archivo quedan bloqueados para edición.');
      return;
    }
    openDrawer(fuente);
  }

  async function deleteFuente(id) {
    const dataPage = window.COLFLUX_DATA.dataPage;
    const fuente = dataPage.state.data.fuentes.find(f => Number(f.id) === Number(id));
    const nombre = fuente?.nombre || `ID ${id}`;
    if (fuente?.estado === 'completo' && !window.COLFLUX_ROLE.isAdmin()) {
      alert('Solo un administrador de datos puede borrar una fuente con datos ya cargados.');
      return;
    }
    if (!confirm(`¿Eliminar la fuente "${nombre}"? Esta acción no se puede deshacer.`)) return;

    try {
      const res = await fetch(`${dataPage.state.apiBase}/api/fuentes-datos-crud/${id}/`, {
        method: 'DELETE',
        signal: AbortSignal.timeout(window.COLFLUX_CONFIG.requestTimeoutMs),
      });
      if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
      dataPage.state.data.fuentes = dataPage.state.data.fuentes.filter(f => Number(f.id) !== Number(id));
      dataPage.render();
    } catch (e) {
      alert('No fue posible eliminar la fuente desde la API.');
    }
  }

  window.COLFLUX_DATA.fuentesSection = { render, editFuente, deleteFuente };
  window.editFuente = editFuente;
  window.deleteFuente = deleteFuente;

  window.addEventListener('colflux-rol-cambiado', () => {
    const dataPage = window.COLFLUX_DATA.dataPage;
    if (dataPage) dataPage.render();
  });
})(window);
