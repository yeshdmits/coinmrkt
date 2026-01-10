from pathlib import Path
import uuid
import shutil
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from bson import ObjectId
from passlib.context import CryptContext
from database import coins_collection, orders_collection, users_collection
from models import Coin, CoinCreate, Order, OrderCreate, User, UserCreate, UserLogin

app = FastAPI(title="CoinMrkt API")

STATIC_DIR = Path(__file__).parent / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def serialize_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc


# Static pages
@app.get("/")
async def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login")
async def serve_login():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/register")
async def serve_register():
    return FileResponse(STATIC_DIR / "register.html")


@app.get("/orders")
async def serve_orders():
    return FileResponse(STATIC_DIR / "orders.html")


@app.get("/admin")
async def serve_admin():
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/manage")
async def serve_manage():
    return FileResponse(STATIC_DIR / "manage.html")


@app.get("/coin/{coin_id}")
async def serve_coin_detail(coin_id: str):
    return FileResponse(STATIC_DIR / "coin.html")


# Image upload endpoint
@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...), request: Request = None):
    """Upload an image and return its URL"""
    if request:
        user_id = request.cookies.get("user_id")
        if user_id:
            user = await users_collection.find_one({"_id": ObjectId(user_id)})
            if not user or not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Admin access required")
        else:
            raise HTTPException(status_code=401, detail="Not authenticated")

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPEG, PNG, GIF, WebP")

    # Generate unique filename
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = UPLOADS_DIR / filename

    # Save file
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"url": f"/uploads/{filename}"}


# Auth endpoints
@app.post("/api/auth/register")
async def register(user: UserCreate, response: Response):
    existing = await users_collection.find_one({"username": user.username})
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    existing_email = await users_collection.find_one({"email": user.email})
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")

    user_data = {
        "username": user.username,
        "email": user.email,
        "password_hash": hash_password(user.password),
        "is_admin": False
    }
    result = await users_collection.insert_one(user_data)
    created = await users_collection.find_one({"_id": result.inserted_id})

    response.set_cookie(key="user_id", value=str(created["_id"]), httponly=True)
    return {"message": "Registration successful", "user": serialize_user(created)}


@app.post("/api/auth/login")
async def login(user: UserLogin, response: Response):
    db_user = await users_collection.find_one({"username": user.username})
    if not db_user or not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    response.set_cookie(key="user_id", value=str(db_user["_id"]), httponly=True)
    return {"message": "Login successful", "user": serialize_user(db_user)}


@app.post("/api/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key="user_id")
    return {"message": "Logged out"}


@app.get("/api/auth/me")
async def get_current_user(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return {"user": None}

    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if user:
            return {"user": serialize_user(user)}
    except:
        pass
    return {"user": None}


def serialize_user(user):
    return {
        "_id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "is_admin": user.get("is_admin", False)
    }


async def enrich_order_with_coins(order):
    """Add coin details to each item in the order"""
    enriched_items = []
    for item in order.get("items", []):
        coin = await coins_collection.find_one({"_id": ObjectId(item["coin_id"])})
        enriched_item = {
            "coin_id": item["coin_id"],
            "quantity": item["quantity"],
            "coin": serialize_doc(coin) if coin else None
        }
        enriched_items.append(enriched_item)
    order["items"] = enriched_items
    return order


# Coins endpoints
@app.get("/api/coins", response_model=list[Coin])
async def get_coins():
    coins = await coins_collection.find().to_list(100)
    return [serialize_doc(c) for c in coins]


@app.get("/api/coins/{coin_id}", response_model=Coin)
async def get_coin(coin_id: str):
    coin = await coins_collection.find_one({"_id": ObjectId(coin_id)})
    if not coin:
        raise HTTPException(status_code=404, detail="Coin not found")
    return serialize_doc(coin)


@app.post("/api/coins", response_model=Coin)
async def create_coin(coin: CoinCreate):
    result = await coins_collection.insert_one(coin.model_dump())
    created = await coins_collection.find_one({"_id": result.inserted_id})
    return serialize_doc(created)


@app.delete("/api/coins/{coin_id}")
async def delete_coin(coin_id: str):
    result = await coins_collection.delete_one({"_id": ObjectId(coin_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Coin not found")
    return {"message": "Coin deleted"}


# Orders endpoints
@app.post("/api/orders", response_model=Order)
async def create_order(order: OrderCreate, request: Request):
    total = 0.0
    for item in order.items:
        coin = await coins_collection.find_one({"_id": ObjectId(item.coin_id)})
        if not coin:
            raise HTTPException(status_code=404, detail=f"Coin {item.coin_id} not found")
        if coin["stock"] < item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock for {coin['name']}")
        total += coin["price"] * item.quantity

    # Stock will be decremented when payment is confirmed
    order_data = order.model_dump()
    order_data["total"] = total
    order_data["status"] = "pending"
    order_data["payment_status"] = "pending"

    # Associate with logged in user if available
    user_id = request.cookies.get("user_id")
    if user_id:
        order_data["user_id"] = user_id

    result = await orders_collection.insert_one(order_data)
    created = await orders_collection.find_one({"_id": result.inserted_id})
    return serialize_doc(created)


@app.post("/api/orders/{order_id}/confirm-payment")
async def confirm_payment(order_id: str):
    """Simulate TWINT payment confirmation - payment is done but order stays pending for admin review"""
    order = await orders_collection.find_one({"_id": ObjectId(order_id)})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.get("payment_status") == "completed":
        raise HTTPException(status_code=400, detail="Payment already completed")

    # Verify stock is still available and decrement
    for item in order.get("items", []):
        coin = await coins_collection.find_one({"_id": ObjectId(item["coin_id"])})
        if not coin:
            raise HTTPException(status_code=404, detail=f"Coin not found")
        if coin["stock"] < item["quantity"]:
            raise HTTPException(status_code=400, detail=f"Not enough stock for {coin['name']}")

    # Decrement stock now that payment is confirmed
    for item in order.get("items", []):
        await coins_collection.update_one(
            {"_id": ObjectId(item["coin_id"])},
            {"$inc": {"stock": -item["quantity"]}}
        )

    # Only update payment_status, order status stays "pending" until admin approves
    await orders_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"payment_status": "completed"}}
    )

    updated = await orders_collection.find_one({"_id": ObjectId(order_id)})
    return serialize_doc(updated)


@app.get("/api/orders")
async def get_orders(request: Request):
    """Get orders for current user, or all orders for admin"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if user.get("is_admin"):
        orders = await orders_collection.find().to_list(100)
    else:
        orders = await orders_collection.find({"user_id": user_id}).to_list(100)

    enriched_orders = []
    for order in orders:
        enriched = await enrich_order_with_coins(serialize_doc(order))
        enriched_orders.append(enriched)
    return enriched_orders


@app.get("/api/admin/orders")
async def get_all_orders(request: Request):
    """Admin only: get all orders"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    orders = await orders_collection.find().to_list(100)
    enriched_orders = []
    for order in orders:
        enriched = await enrich_order_with_coins(serialize_doc(order))
        enriched_orders.append(enriched)
    return enriched_orders


@app.put("/api/admin/orders/{order_id}/status")
async def update_order_status(order_id: str, request: Request):
    """Admin only: update order status"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    new_status = body.get("status")
    if new_status not in ["pending", "completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    order = await orders_collection.find_one({"_id": ObjectId(order_id)})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    await orders_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": new_status}}
    )

    updated = await orders_collection.find_one({"_id": ObjectId(order_id)})
    return serialize_doc(updated)


# Admin coin management
@app.put("/api/admin/coins/{coin_id}")
async def update_coin(coin_id: str, coin: CoinCreate, request: Request):
    """Admin only: update a coin"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    existing = await coins_collection.find_one({"_id": ObjectId(coin_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Coin not found")

    await coins_collection.update_one(
        {"_id": ObjectId(coin_id)},
        {"$set": coin.model_dump()}
    )

    updated = await coins_collection.find_one({"_id": ObjectId(coin_id)})
    return serialize_doc(updated)


@app.delete("/api/admin/coins/{coin_id}")
async def admin_delete_coin(coin_id: str, request: Request):
    """Admin only: delete a coin"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await coins_collection.delete_one({"_id": ObjectId(coin_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Coin not found")
    return {"message": "Coin deleted"}


@app.post("/api/admin/coins")
async def admin_create_coin(coin: CoinCreate, request: Request):
    """Admin only: create a coin"""
    user_id = request.cookies.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await coins_collection.insert_one(coin.model_dump())
    created = await coins_collection.find_one({"_id": result.inserted_id})
    return serialize_doc(created)


@app.on_event("startup")
async def seed_data():
    # Seed coins
    count = await coins_collection.count_documents({})
    if count == 0:
        sample_coins = [
            {
                "name": "American Gold Eagle",
                "description": "1 oz gold coin featuring Lady Liberty",
                "metal": "Gold",
                "weight_grams": 31.1,
                "year": 2024,
                "country": "USA",
                "price": 2150.00,
                "stock": 10,
                "image_url": "https://images.unsplash.com/photo-1610375461246-83df859d849d?w=300"
            }
        ]
        await coins_collection.insert_many(sample_coins)

    # Seed admin user
    admin = await users_collection.find_one({"username": "admin"})
    if not admin:
        await users_collection.insert_one({
            "username": "admin",
            "email": "admin@coinmrkt.com",
            "password_hash": hash_password("admin"),
            "is_admin": True
        })


app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
