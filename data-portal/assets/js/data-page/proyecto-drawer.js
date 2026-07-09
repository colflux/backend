(function configureProyectoDrawer(window) {
  window.COLFLUX_DATA = window.COLFLUX_DATA || {};

  let context = null;

  function get(id) {
    return document.getElementById(id);
  }

  function mountDrawer() {
    if (get('proyectoDrawer')) return;

    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
<div class="drawer-overlay" id="proyectoDrawerOverlay" onclick="closeProyectoDrawer()"></div>
<div class="drawer" id="proyectoDrawer">
  <div class="drawer-header">
    <h3>🗂 Nuevo proyecto</h3>
    <button class="drawer-close" onclick="closeProyectoDrawer()">✕</button>
  </div>
  <div class="drawer-body">
    <div class="field-row">
      <div class="field-group">
        <label>Código <span>*</span></label>
        <input type="text" id="pCodigo" placeholder="Ej: COLFLUX-01">
      </div>
      <div class="field-group">
        <label>Escala espacial</label>
        <select id="pEscala">
          <option value="">— Seleccionar —</option>
          <option value="Bioma">Bioma</option>
          <option value="Regional">Regional</option>
          <option value="Ecosistema">Ecosistema</option>
          <option value="Sitio">Sitio</option>
          <option value="Parcela">Parcela</option>
        </select>
      </div>
    </div>
    <div class="field-group">
      <label>Nombre <span>*</span></label>
      <input type="text" id="pNombre" placeholder="Nombre completo del proyecto">
    </div>
    <div class="field-row">
      <div class="field-group">
        <label>Fecha inicio</label>
        <input type="date" id="pFechaInicio">
      </div>
      <div class="field-group">
        <label>Fecha fin</label>
        <input type="date" id="pFechaFin">
      </div>
    </div>
    <div class="field-group">
      <label>Coordinador</label>
      <input type="text" id="pCoordinador" placeholder="Nombre del coordinador">
    </div>
    <div class="field-group">
      <label>Correo del coordinador</label>
      <input type="email" id="pCorreo" placeholder="coordinador@universidad.edu.co">
    </div>
    <div class="field-group">
      <label>Objetivo general</label>
      <textarea id="pObjetivo" placeholder="Describe el objetivo principal del proyecto…"></textarea>
    </div>
    <div id="pFormError" class="form-error" style="display:none;"></div>
  </div>
  <div class="drawer-footer">
    <button class="btn-cancel" onclick="closeProyectoDrawer()">Cancelar</button>
    <button class="btn-submit" id="pBtnSubmit" onclick="submitProyecto()">
      <span id="pSubmitLabel">Guardar proyecto</span>
    </button>
  </div>
</div>`;

    const footer = get('app-footer');
    document.body.insertBefore(wrapper, footer || null);
  }

  function resetForm() {
    ['pCodigo', 'pNombre', 'pCoordinador', 'pCorreo', 'pObjetivo', 'pFechaInicio', 'pFechaFin'].forEach(id => {
      get(id).value = '';
    });
    get('pEscala').value = '';
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

  function openProyectoDrawer() {
    mountDrawer();
    get('pFormError').style.display = 'none';
    get('proyectoDrawerOverlay').classList.add('open');
    get('proyectoDrawer').classList.add('open');
    get('pCodigo').focus();
  }

  function closeProyectoDrawer() {
    if (!get('proyectoDrawer')) return;
    get('proyectoDrawerOverlay').classList.remove('open');
    get('proyectoDrawer').classList.remove('open');
    resetForm();
  }

  async function submitProyecto() {
    const codigo = get('pCodigo').value.trim();
    const nombre = get('pNombre').value.trim();
    const errEl = get('pFormError');

    if (!codigo) {
      errEl.textContent = 'El código es obligatorio.';
      errEl.style.display = 'block';
      get('pCodigo').focus();
      return;
    }
    if (!nombre) {
      errEl.textContent = 'El nombre es obligatorio.';
      errEl.style.display = 'block';
      get('pNombre').focus();
      return;
    }
    errEl.style.display = 'none';

    const btn = get('pBtnSubmit');
    const lbl = get('pSubmitLabel');
    btn.disabled = true;
    lbl.textContent = 'Guardando…';

    try {
      const res = await fetch(`${context.getApiBase()}/api/proyectos/crear/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          codigo,
          nombre,
          coordinador: get('pCoordinador').value.trim(),
          correo_coordinador: get('pCorreo').value.trim(),
          escala_espacial: get('pEscala').value,
          objetivo_general: get('pObjetivo').value.trim(),
          fecha_inicio: get('pFechaInicio').value || null,
          fecha_fin: get('pFechaFin').value || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(errorMessage(data, `Error ${res.status}`));

      context.getData().proyectos.push({ id: data.id, codigo: data.codigo, nombre: data.nombre });
      closeProyectoDrawer();
      context.onRender();
    } catch (e) {
      errEl.textContent = e.message || 'Error al guardar. Intenta de nuevo.';
      errEl.style.display = 'block';
    } finally {
      btn.disabled = false;
      lbl.textContent = 'Guardar proyecto';
    }
  }

  window.COLFLUX_DATA.proyectoDrawer = {
    init(options) {
      context = options;
      mountDrawer();
      window.openProyectoDrawer = openProyectoDrawer;
      window.closeProyectoDrawer = closeProyectoDrawer;
      window.submitProyecto = submitProyecto;
    },
  };
})(window);
