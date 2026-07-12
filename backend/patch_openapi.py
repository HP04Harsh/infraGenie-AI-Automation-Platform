"""Patch provisioning_api to make _UserCreate (defined inside create_router) accessible
for OpenAPI schema generation. Pydantic cannot resolve forward references to local
classes with `from __future__ import annotations`."""
import provisioning_api as pa

_captured_models: dict[str, type] = {}


class _CaptureBaseModel(pa.BaseModel):
    """Drop-in BaseModel replacement that captures locally-defined models."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__.startswith("_"):
            _captured_models[cls.__name__] = cls


_original_create_router = pa.create_router


def _patched_create_router(*args, **kwargs):
    router = _original_create_router(*args, **kwargs)
    if "_UserCreate" in _captured_models:
        cls = _captured_models["_UserCreate"]
        pa._UserCreate = cls
        cls.model_rebuild(force=True)
    return router


pa.BaseModel = _CaptureBaseModel
pa.create_router = _patched_create_router
