from pydantic import BaseModel
from typing import Optional


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


class FunctionSpec(BaseModel):
    name: str
    runtime: str
    resources: Resources
    settings: Settings
