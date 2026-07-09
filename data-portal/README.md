# COLFLUX Data Portal

Prototipos de interfaz para consultar y administrar los datos servidos por el
backend Django.

## Estructura

- `index.html`: entrada y plan de trabajo.
- `pages/`: vistas funcionales del prototipo.
- `assets/css/`: estilos compartidos.
- `assets/js/`: comportamiento compartido.
- `config/services.js`: URLs publicas y opciones de conexion a servicios.

## Desarrollo local

1. Inicia Django en `http://localhost:8000`.
2. Sirve esta carpeta con un servidor HTTP estatico; no abras los HTML con
   `file://`, porque el navegador puede restringir las solicitudes a la API.

Por ejemplo, desde la raiz del repositorio:

```bash
python -m http.server 8080 --directory data-portal
```

Luego abre `http://localhost:8080`. En localhost el portal consume
`http://localhost:8000`; en otros hosts usa el backend desplegado configurado
en `config/services.js`.

## Seguridad

Todo archivo de esta carpeta es publico para el navegador. Las credenciales y
cadenas de conexion deben permanecer en variables de entorno del backend.
