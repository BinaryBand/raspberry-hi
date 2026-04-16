from pydantic import BaseModel, ConfigDict


class MinioConfig(BaseModel):
    """Effective MinIO configuration: role defaults merged with host_vars overrides."""

    minio_data_path: str = "/srv/minio/data"
    minio_require_external_mount: bool = True

    model_config = ConfigDict(extra="allow")
