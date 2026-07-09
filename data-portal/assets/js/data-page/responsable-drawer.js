(function configureResponsableDrawer(window) {
  window.COLFLUX_DATA = window.COLFLUX_DATA || {};

  let context = null;
  let instituciones = [];
  let roles = [];
  let editingUser = null;

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
    <h3 id="responsableDrawerTitle">👤 Nuevo usuario</h3>
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
      <label>Institución</label>
      <select id="rInstitucion">
        <option value="">Sin institución</option>
      </select>
    </div>
    <div class="field-group">
      <label>Roles</label>
      <div id="rRoles" class="roles-checklist">
        <label><input type="checkbox" value="reportador" checked> Reportador</label>
      </div>
    </div>
    <div class="form-error" id="rFormError" style="display:none;"></div>
  </div>
  <div class="drawer-footer">
    <button class="btn-cancel" onclick="closeResponsableDrawer()">Cancelar</button>
    <button class="btn-submit" id="rBtnSubmit" onclick="submitResponsable()">
      <span id="rSubmitLabel">Guardar usuario</span>
    </button>
  </div>
</div>`;

    const footer = get('app-footer');
    document.body.insertBefore(wrapper, footer || null);
  }

  function resetForm() {
    editingUser = null;
    ['rNombre', 'rCorreo', 'rCargo'].forEach(id => {
      get(id).value = '';
    });
    get('rInstitucion').value = '';
    document.querySelectorAll('#rRoles input[type="checkbox"]').forEach(input => {
      input.checked = input.value === 'reportador';
    });
    get('responsableDrawerTitle').textContent = '👤 Nuevo usuario';
    get('rSubmitLabel').textContent = 'Guardar usuario';
  }

  function renderInstitucionesSelect() {
    const select = get('rInstitucion');
    if (!select) return;
    select.innerHTML = '<option value="">Sin institución</option>';
    instituciones.forEach(inst => {
      const opt = document.createElement('option');
      opt.value = inst.id;
      opt.textContent = inst.nombre;
      select.appendChild(opt);
    });
  }

  function renderRoles() {
    const container = get('rRoles');
    if (!container) return;
    const items = roles.length ? roles : [{ codigo: 'reportador', nombre: 'Reportador' }];
    container.innerHTML = '';
    items.forEach(rol => {
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.value = rol.codigo;
      input.checked = rol.codigo === 'reportador';
      label.appendChild(input);
      label.appendChild(document.createTextNode(` ${rol.nombre}`));
      container.appendChild(label);
    });
  }

  function setFormValues(user) {
    get('rNombre').value = user?.nombre || '';
    get('rCorreo').value = user?.correo || user?.correo_institucional || '';
    get('rCargo').value = user?.cargo || '';
    get('rInstitucion').value = user?.institucion || '';

    const userRoles = new Set(user?.roles || []);
    document.querySelectorAll('#rRoles input[type="checkbox"]').forEach(input => {
      input.checked = userRoles.has(input.value);
    });
  }

  async function loadCatalogos() {
    const base = context.getApiBase();
    const timeout = window.COLFLUX_CONFIG?.requestTimeoutMs || 8000;
    const [instRes, rolesRes] = await Promise.all([
      fetch(`${base}/api/instituciones/`, { signal: AbortSignal.timeout(timeout) }),
      fetch(`${base}/api/roles-usuario/`, { signal: AbortSignal.timeout(timeout) }),
    ]);
    if (instRes.ok) {
      const data = await instRes.json();
      instituciones = Array.isArray(data) ? data : data.results || [];
      renderInstitucionesSelect();
    }
    if (rolesRes.ok) {
      const data = await rolesRes.json();
      roles = Array.isArray(data) ? data : data.results || [];
      renderRoles();
    }
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

  async function openResponsableDrawer(user = null) {
    mountDrawer();
    editingUser = user;
    get('rFormError').style.display = 'none';
    get('responsableDrawerTitle').textContent = user ? '👤 Editar usuario' : '👤 Nuevo usuario';
    get('rSubmitLabel').textContent = user ? 'Guardar cambios' : 'Guardar usuario';
    get('responsableDrawerOverlay').classList.add('open');
    get('responsableDrawer').classList.add('open');
    try {
      await loadCatalogos();
    } catch (e) {
      // El usuario puede seguir editando datos básicos aunque fallen catálogos auxiliares.
    }
    if (user) {
      setFormValues(user);
    }
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
      const url = editingUser
        ? `${context.getApiBase()}/api/usuarios/${editingUser.id}/`
        : `${context.getApiBase()}/api/usuarios/`;
      const res = await fetch(url, {
        method: editingUser ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nombre,
          cargo: get('rCargo').value.trim(),
          correo: get('rCorreo').value.trim(),
          institucion: get('rInstitucion').value || null,
          roles: Array.from(document.querySelectorAll('#rRoles input[type="checkbox"]:checked')).map(input => input.value),
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
      lbl.textContent = 'Guardar usuario';
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
