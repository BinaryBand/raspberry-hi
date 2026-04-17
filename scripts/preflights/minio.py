"""Pre-flight spec for MinIO: host_var hints and vault secret definitions."""

from bootstrap import SecretSpec

VAR_HINTS: dict[str, str] = {
    "minio_data_path": "storage path for MinIO data — run 'make mount' first if not yet mounted",
}

VAULT_SECRETS: list[SecretSpec] = [
    {"key": "minio_root_user", "label": "MinIO root username", "hidden": False},
    {"key": "minio_root_password", "label": "MinIO root password", "hidden": True},
]
