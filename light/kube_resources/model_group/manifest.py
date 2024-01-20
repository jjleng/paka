from pydantic import BaseModel


class Manifest(BaseModel):
    name: str
    url: str
    model_type: str
    model_file: str
    sha256: str
