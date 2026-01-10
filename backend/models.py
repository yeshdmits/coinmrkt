from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from bson import ObjectId


class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)


# User models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class User(BaseModel):
    id: str = Field(alias="_id")
    username: str
    email: str
    is_admin: bool = False

    class Config:
        populate_by_name = True


class CoinBase(BaseModel):
    name: str
    description: str
    metal: str  # gold, silver, bronze, etc.
    weight_grams: float
    year: int
    country: str
    price: float
    stock: int
    image_url: Optional[str] = None


class CoinCreate(CoinBase):
    pass


class Coin(CoinBase):
    id: str = Field(alias="_id")

    class Config:
        populate_by_name = True


class OrderItem(BaseModel):
    coin_id: str
    quantity: int


class OrderCreate(BaseModel):
    customer_name: str
    customer_email: str
    items: list[OrderItem]
    payment_method: str = "twint"  # twint, card, etc.


class Order(BaseModel):
    id: str = Field(alias="_id")
    user_id: Optional[str] = None
    customer_name: str
    customer_email: str
    items: list[OrderItem]
    total: float
    status: str = "pending"
    payment_method: str = "twint"
    payment_status: str = "pending"  # pending, completed, failed

    class Config:
        populate_by_name = True
