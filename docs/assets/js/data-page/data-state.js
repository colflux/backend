(function configureDataState(window) {
  window.COLFLUX_DATA = window.COLFLUX_DATA || {};

  const state = {
    apiBase: window.COLFLUX_CONFIG.apiBaseUrl,
    data: { fuentes: [], proyectos: [] },
    activeProyecto: null,
  };

  function get(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[ch]));
  }

  function setStatus(online) {
    get('statusDot').className = `status-dot ${online ? 'online' : 'offline'}`;
    get('statusLabel').textContent = online ? 'API activa' : 'API no disponible';

    const card = get('apiStatusCard');
    card.classList.toggle('offline', !online);
    get('apiStatusIcon').textContent = online ? '✅' : '⚠️';
    get('apiStatusTitle').textContent = online ? 'API activa' : 'API no disponible';
    get('apiStatusUrl').textContent = state.apiBase;
  }

  function filteredFuentes() {
    let items = state.data.fuentes;
    const projectValue = get('projectFilter').value;

    if (projectValue === 'sin-proyecto') {
      items = items.filter(f => !f.proyecto);
    } else if (projectValue) {
      items = items.filter(f => Number(f.proyecto?.id) === Number(projectValue));
    }

    state.activeProyecto = projectValue && projectValue !== 'sin-proyecto' ? Number(projectValue) : null;

    const q = get('searchInput').value.toLowerCase();
    if (q) items = items.filter(f =>
      (f.nombre || '').toLowerCase().includes(q) ||
      (f.descripcion || '').toLowerCase().includes(q) ||
      (f.responsable || '').toLowerCase().includes(q) ||
      (f.proyecto?.codigo || '').toLowerCase().includes(q) ||
      (f.proyecto?.nombre || '').toLowerCase().includes(q)
    );

    const tipo = get('tipoFilter').value;
    if (tipo) items = items.filter(f => f.tipo === tipo);

    const estado = get('estadoFilter').value;
    if (estado) items = items.filter(f => f.estado === estado);

    return items;
  }

  function filteredProyectos() {
    const q = get('projectSearchInput').value.trim().toLowerCase();
    if (!q) return state.data.proyectos;
    return state.data.proyectos.filter(p =>
      (p.codigo || '').toLowerCase().includes(q) ||
      (p.nombre || '').toLowerCase().includes(q)
    );
  }

  function renderStats(items) {
    const total = items.length;
    const completos = items.filter(f => f.estado === 'completo').length;
    const pendientes = items.filter(f => f.estado === 'pendiente').length;
    const errores = items.filter(f => f.estado === 'con_errores').length;
    get('statsBar').innerHTML = `
      <div class="stat-chip"><strong>${total}</strong><span>Fuentes totales</span></div>
      <div class="stat-chip"><strong style="color:#166534">${completos}</strong><span>Completas</span></div>
      <div class="stat-chip"><strong style="color:var(--amber)">${pendientes}</strong><span>Pendientes</span></div>
      <div class="stat-chip"><strong style="color:var(--red)">${errores}</strong><span>Con errores</span></div>
    `;
  }

  function renderOffline() {
    get('statsBar').innerHTML = '';
    get('proyectosTableBody').innerHTML = '<tr><td colspan="4"><div class="state-box">API no disponible.</div></td></tr>';
    get('fuentesTableBody').innerHTML = '<tr><td colspan="7"><div class="state-box">API no disponible.</div></td></tr>';
    get('projectsCount').textContent = '0 proyectos';
    get('tableCount').textContent = '0 registros';
  }

  function render() {
    const items = filteredFuentes();
    renderStats(items);
    window.COLFLUX_DATA.proyectosSection.render();
    window.COLFLUX_DATA.fuentesSection.render(items);
  }

  async function fetchData() {
    try {
      const res = await fetch(`${state.apiBase}/api/fuentes-datos/`, {
        signal: AbortSignal.timeout(window.COLFLUX_CONFIG.requestTimeoutMs),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      state.data = await res.json();
      setStatus(true);
      render();
    } catch (e) {
      setStatus(false);
      renderOffline();
    }
  }

  window.COLFLUX_DATA.dataPage = {
    state,
    escapeHtml,
    fetchData,
    filteredFuentes,
    filteredProyectos,
    render,
  };
})(window);
