// Guardia de rol temporal: mientras no exista login/sesión real, el rol
// "actual" se guarda en localStorage y solo sirve para mostrar/ocultar
// acciones sensibles en la UI (no hay validación de rol en el backend).
(function (window) {
  const STORAGE_KEY = 'colflux_rol_actual';
  const ROLES = [
    { codigo: '', nombre: 'Sin rol asignado' },
    { codigo: 'reportador', nombre: 'Reportador' },
    { codigo: 'investigador', nombre: 'Investigador' },
    { codigo: 'coordinador', nombre: 'Coordinador' },
    { codigo: 'admin_datos', nombre: 'Administrador de datos' },
  ];
  const ROL_ADMIN = 'admin_datos';

  function getRol() {
    try { return localStorage.getItem(STORAGE_KEY) || ''; } catch (e) { return ''; }
  }

  function setRol(codigo) {
    try { localStorage.setItem(STORAGE_KEY, codigo); } catch (e) { /* no-op */ }
  }

  function isAdmin() {
    return getRol() === ROL_ADMIN;
  }

  function renderSelector() {
    const el = document.getElementById('role-guard-selector');
    if (!el) return;
    const actual = getRol();
    el.innerHTML = `
      <select id="rolActualSelect" title="Rol actual (temporal — todavía no hay login)">
        ${ROLES.map(r => `<option value="${r.codigo}" ${r.codigo === actual ? 'selected' : ''}>${r.nombre}</option>`).join('')}
      </select>
    `;
    document.getElementById('rolActualSelect').addEventListener('change', (e) => {
      setRol(e.target.value);
      window.dispatchEvent(new CustomEvent('colflux-rol-cambiado'));
    });
  }

  window.COLFLUX_ROLE = { getRol, setRol, isAdmin, renderSelector, ROLES, ROL_ADMIN };
  renderSelector();
})(window);
