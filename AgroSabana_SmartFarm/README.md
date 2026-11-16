# AgroSabana Centro · Red Agroclimática IoT

Plataforma web en **Python + Flask** orientada a los agricultores y predios rurales de la provincia de **Sabana Centro (Cundinamarca)**: Sopó, Chía, Cajicá, Zipaquirá, Tocancipá, Gachancipá, Nemocón y Cogua.

## Estructura del Proyecto
- `app.py`: Backend Flask con catálogo georreferenciado de 12 torres por agricultor/finca y API REST `/api/telemetria`.
- `templates/base.html`: Plantilla maestra responsiva con identidad editorial agro-tecnológica.
- `templates/dashboard.html`: Centro de monitoreo en vivo filtrable por Municipio y por Agricultor/Torre.
- `templates/torres.html`: Mapa interactivo (Leaflet) y fichas técnicas de cada predio conectado.
- `templates/app_movil.html`: Módulo dedicado a la aplicación móvil del agricultor con simulador interactivo de parcela.
- `templates/documentacion.html`: Investigación sobre cercanía geográfica, corredores agroclimáticos e interconexión municipal.
- `templates/DashBoard_PowerBi.html`: Integración con Power BI.
- `Procfile` & `render.yaml`: Archivos listos para despliegue en la nube con certificado SSL gratuito.

## Despliegue Gratuito con Certificado SSL y Subdominio (Render.com)
1. Sube esta carpeta a un repositorio nuevo en **GitHub**.
2. Crea una cuenta gratuita en [Render.com](https://render.com) e inicia sesión con GitHub.
3. Haz clic en **New + > Web Service** y selecciona el repositorio.
4. Render detectará automáticamente `render.yaml` / `requirements.txt` (`gunicorn app:app`).
5. Selecciona el plan **Free** y haz clic en **Create Web Service**.
6. En 2 minutos tendrás tu URL pública `https://tu-proyecto.onrender.com` con **certificado SSL/TLS automático** y posibilidad de vincular un dominio propio en *Settings > Custom Domains*.
