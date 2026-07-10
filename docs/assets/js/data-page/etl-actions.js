(function configureEtlActions(window) {
  window.COLFLUX_DATA = window.COLFLUX_DATA || {};

  function canStartEtl(fuente) {
    return fuente.tipo === 'excel' || fuente.tipo === 'csv';
  }

  function renderStartLink(fuente) {
    if (!canStartEtl(fuente)) return '';
    const fuenteId = encodeURIComponent(fuente.id);
    return `<a class="card-link card-link-etl" href="etl-upload.html?fuente=${fuenteId}">Iniciar carga →</a>`;
  }

  window.COLFLUX_DATA.etlActions = {
    canStartEtl,
    renderStartLink,
  };
})(window);
