# PROGRESO · PMS hotelero (Prototipo diseñado para ATm Consulting)
Actualizado el 28 oct 2026.
- [x] 1 Esquema SQL (17 tablas pms_, RLS) + datos semilla ficticios (3 hoteles × 18 habitaciones)
- [x] 2 Capa de datos y lógica + 51 pruebas que pasan
- [x] 3 Interfaz Streamlit (fondo blanco, 4 roles, aviso de datos ficticios, marca ATm)
- [x] 4 Pruebas en navegador (6/6 flujos, sesión tras recargar) + capturas en docs/capturas/
- [x] 5 Repo privado Fredchars/pms-hoteles; Actions: pruebas (verde), Supabase (tablas pms_ + RLS + semilla + verificación: todo correcto), respaldo semanal cifrado (probado, artefacto creado); secretos del repo puestos sin imprimirlos
- [x] 5b Despliegue en Streamlit Community Cloud: https://pms-hoteles-atm.streamlit.app/ (repo público; se redespliega al hacer push a main)
- [x] 6 Documentos: instructivo por rol (Word+PDF), guía de pruebas (Word+PDF), checklist Excel, README
- [x] 7 Subida a Google Drive: carpetas «PMS piloto · Documentos de uso y pruebas» y «PMS piloto · Código» dentro de la carpeta indicada (sin contraseñas ni respaldos)
- [x] 8 Primer ingreso seguro (29 oct 2026): columna `debe_cambiar_clave`, pantalla «Crea tu contraseña nueva» que bloquea toda la app, botón «Generar contraseña temporal» (administrador), cierre de sesiones al cambiar la clave, pruebas nuevas (`test_clave_inicial.py`, `test_interfaz_clave.py`); los 19 usuarios de prueba quedan obligados a crear su contraseña.
- [x] 9 Corrección (29 oct 2026): tras un push, Streamlit Cloud dejaba en memoria el `pms/*.py` viejo (sin reiniciar) y el ingreso mostraba «No se pudo conectar con la base de datos (AttributeError)». Ahora `Inicio.py` recarga `pms/` si cambió, y los errores se clasifican: conexión vs «Error inesperado (Tipo)» con traceback en los registros. Prueba de regresión en `tests/test_modulos_y_errores.py`.
## Bloqueos
- (ninguno; app desplegada en https://pms-hoteles-atm.streamlit.app/)
