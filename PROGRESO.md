# PROGRESO · PMS hotelero (Prototipo diseñado para ATm Consulting)
Actualizado el 28 oct 2026.
- [x] 1 Esquema SQL (17 tablas pms_, RLS) + datos semilla ficticios (3 hoteles × 18 habitaciones)
- [x] 2 Capa de datos y lógica + 51 pruebas que pasan
- [x] 3 Interfaz Streamlit (fondo blanco, 4 roles, aviso de datos ficticios, marca ATm)
- [x] 4 Pruebas en navegador (6/6 flujos, sesión tras recargar) + capturas en docs/capturas/
- [x] 5 Repo privado Fredchars/pms-hoteles; Actions: pruebas (verde), Supabase (tablas pms_ + RLS + semilla + verificación: todo correcto), respaldo semanal cifrado (probado, artefacto creado); secretos del repo puestos sin imprimirlos
- [ ] 5b Despliegue en Streamlit Community Cloud: PASO MANUAL pendiente (docs/despliegue-streamlit-cloud.md; secretos listos en /workspace/.secrets/pms_streamlit_secrets.toml)
- [x] 6 Documentos: instructivo por rol (Word+PDF), guía de pruebas (Word+PDF), checklist Excel, README
- [x] 7 Subida a Google Drive: carpetas «PMS piloto · Documentos de uso y pruebas» y «PMS piloto · Código» dentro de la carpeta indicada (sin contraseñas ni respaldos)
## Bloqueos
- Streamlit Cloud requiere iniciar sesión de la persona (no se puede hacer sin ella).
