from pydantic import BaseModel


class Manifest(BaseModel):
    name: str
    url: str
    type: str
    file: str
    sha256: str
