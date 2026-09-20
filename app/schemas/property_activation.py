from pydantic import BaseModel


class PropertyActivationRequest(BaseModel):
    plate_code: str
