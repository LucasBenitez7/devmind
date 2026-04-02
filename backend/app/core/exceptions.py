class DevMindException(Exception):
    status_code: int = 500
    user_message: str = "Algo salió mal. Inténtalo de nuevo en unos minutos."

    def __init__(self, user_message: str | None = None) -> None:
        if user_message is not None:
            self.user_message = user_message
        super().__init__(self.user_message)


class PlanLimitExceeded(DevMindException):
    status_code = 429

    def __init__(self, resource: str, limit: int) -> None:
        self.user_message = f"Has alcanzado el límite de {limit} {resource} de tu plan."
        super(DevMindException, self).__init__(self.user_message)


class InsufficientPermissions(DevMindException):
    status_code = 403
    user_message = (
        "No tienes permisos para realizar esta acción. Contacta al admin de tu organización."
    )


class ResourceNotFound(DevMindException):
    status_code = 404
    user_message = "El recurso solicitado no existe."


class InvalidToken(DevMindException):
    status_code = 401
    user_message = "Tu sesión ha expirado. Por favor inicia sesión de nuevo."


class DocumentProcessingError(DevMindException):
    status_code = 422
    user_message = "No pudimos procesar este documento. Verifica que el archivo no esté dañado."


class InvalidFileType(DevMindException):
    status_code = 400
    user_message = "Solo se permiten archivos PDF, Markdown y TXT."


class FileTooLarge(DevMindException):
    status_code = 413

    def __init__(self, limit_mb: int) -> None:
        self.user_message = f"El archivo supera el límite de {limit_mb} MB. Comprime el documento o actualiza tu plan."
        super(DevMindException, self).__init__(self.user_message)


class AgentError(DevMindException):
    status_code = 500
    user_message = "Hubo un problema al procesar tu consulta. Inténtalo de nuevo."


class ConversationNotFound(DevMindException):
    status_code = 404
    user_message = "Esta conversación no existe o fue eliminada."
