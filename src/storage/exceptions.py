from fastapi import HTTPException, status


class StorageException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class FileTooBigException(StorageException):
    def __init__(self, max_size_mb: float):
        super().__init__(
            detail=f"El tamaño del archivo excede el límite de {max_size_mb}MB"
        )
        self.status_code = status.HTTP_400_BAD_REQUEST


class InvalidFileTypeException(StorageException):
    def __init__(self, allowed_types: list):
        super().__init__(
            detail=f"Tipo de archivo no válido. Los tipos permitidos son: {', '.join(allowed_types)}"
        )
        self.status_code = status.HTTP_400_BAD_REQUEST


class UploadFailedException(StorageException):
    def __init__(self, detail: str = "Error al subir el archivo"):
        super().__init__(detail=detail)
        self.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR 