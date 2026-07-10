(function initDataPage(window) {
  const dataPage = window.COLFLUX_DATA.dataPage;
  const { state } = dataPage;

  document.getElementById('apiStatusUrl').textContent = state.apiBase;

  window.COLFLUX_DATA.fuenteDrawer.init({
    getData: () => state.data,
    getActiveProyecto: () => state.activeProyecto,
    getApiBase: () => state.apiBase,
    onRender: dataPage.render,
  });

  window.COLFLUX_DATA.proyectoDrawer.init({
    getData: () => state.data,
    getApiBase: () => state.apiBase,
    onRender: dataPage.render,
  });

  window.COLFLUX_DATA.responsableDrawer.init({
    getApiBase: () => state.apiBase,
    onSaved: () => dataPage.fetchData(),
  });

  document.getElementById('searchInput').addEventListener('input', dataPage.render);
  document.getElementById('projectSearchInput').addEventListener('input', dataPage.render);
  document.getElementById('projectFilter').addEventListener('change', dataPage.render);
  document.getElementById('tipoFilter').addEventListener('change', dataPage.render);
  document.getElementById('estadoFilter').addEventListener('change', dataPage.render);

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      closeDrawer();
      closeProyectoDrawer();
      closeResponsableDrawer();
    }
  });

  dataPage.fetchData();
})(window);
