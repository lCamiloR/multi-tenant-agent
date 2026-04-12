from fastapi import FastAPI
from pydantic import BaseModel
from uuid import uuid4
app = FastAPI()


class Item(BaseModel):
    name: str
    price: float
    is_offer: bool | None = None


@app.get("/")
def invoke():
    return {"Hello": "World"}

