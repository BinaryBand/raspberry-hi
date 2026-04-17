"""Prompt hints for MinIO pre-flight required variables."""

VAR_HINTS: dict[str, str] = {
    "minio_data_path": "storage path for MinIO data — run 'make mount' first if not yet mounted",
}
