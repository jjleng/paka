from typing import Any

from paka.cluster.context import Context
from paka.model.store import ModelStore, S3ModelStore


def get_model_store(ctx: Context, *args: Any, **kwargs: Any) -> ModelStore:
    assert ctx.provider == "aws"

    return S3ModelStore(ctx.bucket, *args, **kwargs)
