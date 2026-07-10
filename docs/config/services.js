/**
 * Configuracion publica de servicios del prototipo.
 *
 * Este archivo se ejecuta en el navegador: no agregues contrasenas, tokens,
 * llaves privadas ni cadenas de conexion a bases de datos.
 */
(function configureServices(window) {
  const isLocal =
    window.location.protocol === "file:" ||
    ["localhost", "127.0.0.1"].includes(window.location.hostname);

  window.COLFLUX_CONFIG = Object.freeze({
    apiBaseUrl: isLocal
      ? "http://localhost:8000"
      : "https://backend-143s.onrender.com",
    requestTimeoutMs: 5000,
  });
})(window);
