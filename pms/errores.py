"""Errores de negocio con mensajes en español sencillo (se muestran tal cual al usuario)."""


class ErrorNegocio(Exception):
    """Una regla del negocio no se cumple (por ejemplo: no hay disponibilidad)."""


class PermisoDenegado(ErrorNegocio):
    """El rol del usuario no tiene permiso para esta acción."""
