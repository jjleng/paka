from enum import Enum
from typing import Optional

from pydantic import BaseModel

APP_KIND_FUNCTION = "function"
APP_KIND_JOB = "job"


class Resource(BaseModel):
    cpu: Optional[str]
    memory: Optional[str]


class Resources(BaseModel):
    requests: Optional[Resource]
    limits: Optional[Resource]


class Settings(BaseModel):
    concurrency: Optional[int] = 500
    timeout: Optional[int] = 60
    idle_timeout: Optional[int] = 120
    requests_per_pod: Optional[int] = 1


class Runtime(BaseModel):
    image: str
    builder_image: str


class FunctionSpec(BaseModel):
    name: str
    runtime: Runtime
    resources: Resources
    settings: Settings
    kind: str = APP_KIND_FUNCTION
