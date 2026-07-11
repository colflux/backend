(function configureFuenteDrawer(window) {
  window.COLFLUX_DATA = window.COLFLUX_DATA || {};

  let context = null;
  let editingFuente = null;
  let reportadores = [];

  function get(id) {
    return document.getElementById(id);
  }

  function mountDrawer() {
    if (get('drawer')) return;

    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
<div class="drawer-overlay" id="drawerOverlay" onclick="closeDrawer()"></div>
  <div class="drawer" id="drawer">
  <div class="drawer-header">
    <h3 id="fuenteDrawerTitle">📂 Nueva fuente de datos</h3>
    <button class="drawer-close" onclick="closeDrawer()">✕</button>
  </div>
  <div class="drawer-body">
    <div class="field-group">
      <label>Proyecto</label>
      <select id="fProyecto">
        <option value="">— Sin proyecto —</option>
      </select>
    </div>
    <div class="field-group">
      <label>Nombre <span>*</span></label>
      <input type="text" id="fNombre" placeholder="Ej: SWAP Turbera La Cocha 2023">
    </div>
    <div class="field-group">
      <label>Enlace o ruta al archivo</label>
      <input type="text" id="fUrl" placeholder="https://docs.google.com/spreadsheets/… o ./data/test.xlsx">
      <span class="field-hint">Acepta URL remota o ruta local para pruebas. Las rutas locales solo se guardan como referencia.</span>
    </div>
    <div class="field-group">
      <label>Descripción</label>
      <textarea id="fDescripcion" placeholder="¿Qué contiene este archivo? ¿De qué campaña de campo es?"></textarea>
    </div>
    <div class="field-row">
      <div class="field-group">
        <label>Tipo</label>
        <select id="fTipo">
          <option value="excel">Excel</option>
          <option value="csv">CSV</option>
          <option value="shapefile">Shapefile</option>
          <option value="geojson">GeoJSON</option>
          <option value="api">API externa</option>
          <option value="base_de_datos">Base de datos</option>
          <option value="otro">Otro</option>
        </select>
      </div>
      <div class="field-group">
        <label>Estado</label>
        <select id="fEstado">
          <option value="pendiente">Pendiente</option>
          <option value="en_proceso">En proceso</option>
          <option value="completo">Completo</option>
          <option value="con_errores">Con errores</option>
        </select>
      </div>
    </div>
    <div class="field-group">
      <label>Responsable</label>
      <select id="fResponsable">
        <option value="">— Sin responsable —</option>
      </select>
    </div>
    <div id="formError" class="form-error" style="display:none;"></div>
  </div>
  <div class="drawer-footer">
    <button class="btn-cancel" onclick="closeDrawer()">Cancelar</button>
    <button class="btn-submit" id="btnSubmit" onclick="submitFuente()">
      <span id="submitLabel">Guardar fuente</span>
    </button>
  </div>
</div>`;

    const footer = get('app-footer');
    document.body.insertBefore(wrapper, footer || null);
  }

  function populateProjectSelect() {
    const sel = get('fProyecto');
    sel.innerHTML = '';

    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = '— Sin proyecto —';
    sel.appendChild(emptyOption);

    for (const p of context.getData().proyectos) {
      const option = document.createElement('option');
      option.value = p.id;
      option.textContent = p.nombre;
      sel.appendChild(option);
    }

    const activeProyecto = context.getActiveProyecto();
    if (activeProyecto) sel.value = activeProyecto;
  }

  async function loadReportadores() {
    const timeout = window.COLFLUX_CONFIG?.requestTimeoutMs || 8000;
    const res = await fetch(`${context.getApiBase()}/api/responsables/`, {
      signal: AbortSignal.timeout(timeout),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    reportadores = Array.isArray(data) ? data : data.results || [];
    populateReportadorSelect();
  }

  function populateReportadorSelect() {
    const sel = get('fResponsable');
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '';

    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = '— Sin responsable —';
    sel.appendChild(emptyOption);

    for (const usuario of reportadores) {
      const option = document.createElement('option');
      option.value = usuario.id;
      option.textContent = usuario.institucion_nombre
        ? `${usuario.nombre} — ${usuario.institucion_nombre}`
        : usuario.nombre;
      sel.appendChild(option);
    }

    sel.value = current;
  }

  function resetForm() {
    editingFuente = null;
    ['fProyecto', 'fNombre', 'fUrl', 'fDescripcion', 'fResponsable'].forEach(id => {
      const el = get(id);
      if (el) el.value = '';
    });
    get('fTipo').value = 'excel';
    get('fEstado').value = 'pendiente';
    get('fuenteDrawerTitle').textContent = '📂 Nueva fuente de datos';
    get('submitLabel').textContent = 'Guardar fuente';
  }

  function errorMessage(data, fallback) {
    if (data?.error) return data.error;
    if (data && typeof data === 'object') {
      const firstValue = Object.values(data)[0];
      if (Array.isArray(firstValue)) return firstValue[0];
      if (typeof firstValue === 'string') return firstValue;
    }
    return fallback;
  }

  function setFormValues(fuente) {
    get('fProyecto').value = fuente?.proyecto?.id || '';
    get('fNombre').value = fuente?.nombre || '';
    get('fUrl').value = fuente?.url || '';
    get('fDescripcion').value = fuente?.descripcion || '';
    get('fTipo').value = fuente?.tipo || 'excel';
    get('fEstado').value = fuente?.estado || 'pendiente';
    get('fResponsable').value = fuente?.responsable_id || '';
  }

  async function openDrawer(fuente = null) {
    mountDrawer();
    editingFuente = fuente;
    populateProjectSelect();
    get('formError').style.display = 'none';
    get('fuenteDrawerTitle').textContent = fuente ? '📂 Editar fuente de datos' : '📂 Nueva fuente de datos';
    get('submitLabel').textContent = fuente ? 'Guardar cambios' : 'Guardar fuente';
    try {
      await loadReportadores();
    } catch (e) {
      get('formError').textContent = 'No fue posible cargar usuarios reportadores.';
      get('formError').style.display = 'block';
    }
    if (fuente) setFormValues(fuente);
    get('drawerOverlay').classList.add('open');
    get('drawer').classList.add('open');
    get('fNombre').focus();
  }

  function closeDrawer() {
    if (!get('drawer')) return;
    get('drawerOverlay').classList.remove('open');
    get('drawer').classList.remove('open');
    resetForm();
  }

  async function submitFuente() {
    const nombre = get('fNombre').value.trim();
    const errEl = get('formError');

    if (!nombre) {
      errEl.textContent = 'El nombre es obligatorio.';
      errEl.style.display = 'block';
      get('fNombre').focus();
      return;
    }
    errEl.style.display = 'none';

    const btn = get('btnSubmit');
    const lbl = get('submitLabel');
    btn.disabled = true;
    lbl.textContent = 'Guardando…';

    const body = {
      nombre,
      descripcion: get('fDescripcion').value.trim(),
      url: get('fUrl').value.trim(),
      tipo: get('fTipo').value,
      estado: get('fEstado').value,
      responsable_id_write: get('fResponsable').value || null,
      proyecto_id: get('fProyecto').value || null,
    };

    try {
      const url = editingFuente
        ? `${context.getApiBase()}/api/fuentes-datos-crud/${editingFuente.id}/`
        : `${context.getApiBase()}/api/fuentes-datos-crud/`;
      const res = await fetch(url, {
        method: editingFuente ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(errorMessage(data, `Error ${res.status}`));

      if (editingFuente) {
        const idx = context.getData().fuentes.findIndex(f => Number(f.id) === Number(editingFuente.id));
        if (idx >= 0) context.getData().fuentes.splice(idx, 1, data);
      } else {
        context.getData().fuentes.unshift(data);
      }
      closeDrawer();
      context.onRender();
    } catch (e) {
      errEl.textContent = e.message || 'Error al guardar. Intenta de nuevo.';
      errEl.style.display = 'block';
    } finally {
      btn.disabled = false;
      lbl.textContent = 'Guardar fuente';
    }
  }

  window.COLFLUX_DATA.fuenteDrawer = {
    init(options) {
      context = options;
      mountDrawer();
      window.openDrawer = openDrawer;
      window.closeDrawer = closeDrawer;
      window.submitFuente = submitFuente;
    },
  };
})(window);
