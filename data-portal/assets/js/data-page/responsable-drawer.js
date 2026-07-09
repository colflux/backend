(function configureResponsableDrawer(window) {
  window.COLFLUX_DATA = window.COLFLUX_DATA || {};

  let context = null;

  function get(id) {
    return document.getElementById(id);
  }

  function mountDrawer() {
    if (get('responsableDrawer')) return;

    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
<div class="drawer-overlay" id="responsableDrawerOverlay" onclick="closeResponsableDrawer()"></div>
<div class="drawer" id="responsableDrawer">
  <div class="drawer-header">
    <h3>👤 Nuevo responsable</h3>
    <button class="drawer-close" onclick="closeResponsableDrawer()">✕</button>
  </div>
  <div class="drawer-body">
    <div class="field-group">
      <label>Nombre <span>*</span></label>
      <input type="text" id="rNombre" placeholder="Nombre del responsable">
    </div>
    <div class="field-group">
      <label>Correo</label>
      <input type="email" id="rCorreo" placeholder="responsable@universidad.edu.co">
    </div>
    <div class="field-group">
      <label>Cargo</label>
      <input type="text" id="rCargo" placeholder="Coordinador, analista, investigador...">
    </div>
    <div class="field-group">
      <label>Institución asociada</label>
      <input type="text" id="rInstitucion" placeholder="Universidad, grupo o entidad">
    </div>
    <div class="form-error" id="rFormError" style="display:none;"></div>
  </div>
  <div class="drawer-footer">
    <button class="btn-cancel" onclick="closeResponsableDrawer()">Cancelar</button>
    <button class="btn-submit" id="rBtnSubmit" onclick="submitResponsable()">
      <span id="rSubmitLabel">Guardar responsable</span>
    </button>
  </div>
</div>`;

    const footer = get('app-footer');
    document.body.insertBefore(wrapper, footer || null);
  }

  function resetForm() {
    ['rNombre', 'rCorreo', 'rCargo', 'rInstitucion'].forEach(id => {
      get(id).value = '';
    });
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

  function openResponsableDrawer() {
    mountDrawer();
    get('rFormError').style.display = 'none';
    get('responsableDrawerOverlay').classList.add('open');
    get('responsableDrawer').classList.add('open');
    get('rNombre').focus();
  }

  function closeResponsableDrawer() {
    if (!get('responsableDrawer')) return;
    get('responsableDrawerOverlay').classList.remove('open');
    get('responsableDrawer').classList.remove('open');
    resetForm();
  }

  async function submitResponsable() {
    const nombre = get('rNombre').value.trim();
    const errEl = get('rFormError');

    if (!nombre) {
      errEl.textContent = 'El nombre es obligatorio.';
      errEl.style.display = 'block';
      get('rNombre').focus();
      return;
    }
    errEl.style.display = 'none';

    const btn = get('rBtnSubmit');
    const lbl = get('rSubmitLabel');
    btn.disabled = true;
    lbl.textContent = 'Guardando…';

    try {
      const res = await fetch(`${context.getApiBase()}/api/responsables/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nombre,
          cargo: get('rCargo').value.trim(),
          correo: get('rCorreo').value.trim(),
          institucion_asociada: get('rInstitucion').value.trim(),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(errorMessage(data, `Error ${res.status}`));

      closeResponsableDrawer();
      context.onSaved(data);
    } catch (e) {
      errEl.textContent = e.message || 'Error al guardar. Intenta de nuevo.';
      errEl.style.display = 'block';
    } finally {
      btn.disabled = false;
      lbl.textContent = 'Guardar responsable';
    }
  }

  window.COLFLUX_DATA.responsableDrawer = {
    init(options) {
      context = options;
      mountDrawer();
      window.openResponsableDrawer = openResponsableDrawer;
      window.closeResponsableDrawer = closeResponsableDrawer;
      window.submitResponsable = submitResponsable;
    },
  };
})(window);
