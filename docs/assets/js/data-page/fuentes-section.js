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
      const startLink = window.COLFLUX_DATA.etlActions.canStartEtl(f)
        ? `<a class="btn-table-action primary" href="etl-upload.html?fuente=${encodeURIComponent(f.id)}" title="Iniciar carga" aria-label="Iniciar carga">⬆</a>`
        : '<span class="source-muted">No aplica carga</span>';

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
              ${startLink}
              <button class="btn-table-action" onclick="editFuente(${Number(f.id)})" title="Editar fuente" aria-label="Editar fuente">✎</button>
              <button class="btn-table-action danger" onclick="deleteFuente(${Number(f.id)})" title="Eliminar fuente" aria-label="Eliminar fuente">×</button>
            </div>
          </td>
        </tr>`;
    }).join('');
  }

  function editFuente(id) {
    const fuente = window.COLFLUX_DATA.dataPage.state.data.fuentes.find(f => Number(f.id) === Number(id));
    if (!fuente) return;
    openDrawer(fuente);
  }

  async function deleteFuente(id) {
    const dataPage = window.COLFLUX_DATA.dataPage;
    const fuente = dataPage.state.data.fuentes.find(f => Number(f.id) === Number(id));
    const nombre = fuente?.nombre || `ID ${id}`;
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
})(window);
