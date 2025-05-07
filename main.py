from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from typing import List, Optional
import mysql.connector
from auth import AuthHandler, hash_password
from schemas import AuthDetails

app = FastAPI()
auth_handler = AuthHandler()
security = HTTPBearer()

# Root welcome endpoint
@app.get("/")
def root():
    return {"message": "Welcome to the Sakila FastAPI Service!"}

# In-memory token blacklist for revocation
revoked_tokens = set()

# Database connection utility
def get_db():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="your_user",
            password="your_password",
            database="sakila"
        )
    except mysql.connector.Error:
        raise HTTPException(status_code=500, detail="Database connection error")

# Pydantic models
class Film(BaseModel):
    film_id: int
    title: str
    description: Optional[str]
    release_year: int

class NewCustomer(BaseModel):
    store_id: int
    first_name: str
    last_name: str
    email: str
    address_id: int
    active: int

class UpdateAddress(BaseModel):
    address_id: int
    address: str
    district: str

class CustomerCreate(BaseModel):
    store_id: int
    first_name: str
    last_name: str
    email: str
    address_id: int
    active: int
    password: str

class CustomerOut(BaseModel):
    customer_id: int
    first_name: str
    last_name: str
    email: str

# --- Token Endpoints ---
@app.post("/token", tags=["Token"])
def login(auth_details: AuthDetails):
    if not auth_handler.authenticate(auth_details.username, auth_details.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = auth_handler.encode_token(auth_details.username)
    return {"token": token}

@app.put("/token", tags=["Token"])
def refresh_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    old_token = credentials.credentials
    if old_token in revoked_tokens:
        raise HTTPException(status_code=401, detail="Token has been revoked")
    username = auth_handler.decode_token(old_token)
    new_token = auth_handler.encode_token(username)
    return {"token": new_token}

@app.delete("/token", tags=["Token"])
def revoke_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    revoked_tokens.add(token)
    return {"message": "Token has been revoked"}

# Dependency for protected routes
def jwt_required(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    if token in revoked_tokens:
        raise HTTPException(status_code=401, detail="Token has been revoked")
    return auth_handler.decode_token(token)

# --- GET Endpoints (Public) ---
@app.get("/films", response_model=List[Film])
def get_all_films():
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT film_id, title, description, release_year FROM film LIMIT 10"
    )
    rows = cursor.fetchall()
    cursor.close()
    return [Film(film_id=r[0], title=r[1], description=r[2], release_year=r[3]) for r in rows]

@app.get("/films/category/{category_id}", response_model=List[Film])
def get_films_by_category(category_id: int):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT f.film_id, f.title, f.description, f.release_year
        FROM film f
        JOIN film_category fc ON f.film_id = fc.film_id
        WHERE fc.category_id = %s
        """, (category_id,)
    )
    rows = cursor.fetchall()
    cursor.close()
    if not rows:
        raise HTTPException(status_code=404, detail="No films found in this category")
    return [Film(film_id=r[0], title=r[1], description=r[2], release_year=r[3]) for r in rows]

@app.get("/customers/active/{store_id}", response_model=List[NewCustomer])
def get_active_customers(store_id: int):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT store_id, first_name, last_name, email, address_id, active"
        " FROM customer WHERE store_id=%s AND active=1", (store_id,)
    )
    results = cursor.fetchall()
    cursor.close()
    if not results:
        raise HTTPException(status_code=404, detail="No active customers found for this store")
    return results

@app.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT customer_id, first_name, last_name, email FROM customer WHERE customer_id=%s",
        (customer_id,)
    )
    result = cursor.fetchone()
    cursor.close()
    if not result:
        raise HTTPException(status_code=404, detail="Customer not found")
    return result

# --- POST Endpoints (Protected) ---
@app.post("/customers/new", status_code=201)
def create_customer(
    customer: CustomerCreate,
    username: str = Depends(jwt_required)
):
    hashed_pw = hash_password(customer.password)
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO customer (store_id, first_name, last_name, email, address_id, active, password, create_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                customer.store_id, customer.first_name, customer.last_name,
                customer.email, customer.address_id, customer.active, hashed_pw
            )
        )
        db.commit()
    except mysql.connector.Error:
        raise HTTPException(status_code=500, detail="Error creating customer")
    finally:
        cursor.close()
    return {"message": "Customer created successfully"}

@app.post("/films/new", status_code=201)
def add_new_film(
    title: str,
    description: str,
    release_year: int,
    language_id: int,
    username: str = Depends(jwt_required)
):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO film (title, description, release_year, language_id)
            VALUES (%s, %s, %s, %s)
            """,
            (title, description, release_year, language_id)
        )
        db.commit()
    except mysql.connector.Error:
        raise HTTPException(status_code=500, detail="Error adding film")
    finally:
        cursor.close()
    return {"message": "Film added successfully"}

# --- PUT Endpoints (Protected) ---
@app.put("/address/update", status_code=200)
def update_customer_address(
    data: UpdateAddress,
    username: str = Depends(jwt_required)
):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE address SET address=%s, district=%s WHERE address_id=%s",
            (data.address, data.district, data.address_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Address not found")
        db.commit()
    except mysql.connector.Error:
        raise HTTPException(status_code=500, detail="Error updating address")
    finally:
        cursor.close()
    return {"message": "Address updated"}

@app.put("/film/title/{film_id}", status_code=200)
def update_film_title(
    film_id: int,
    title: str,
    username: str = Depends(jwt_required)
):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE film SET title=%s WHERE film_id=%s", (title, film_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Film not found")
        db.commit()
    except mysql.connector.Error:
        raise HTTPException(status_code=500, detail="Error updating film title")
    finally:
        cursor.close()
    return {"message": "Film title updated"}

# --- DELETE Endpoints (Protected) ---
@app.delete("/customer/delete/{customer_id}", status_code=200)
def delete_customer(
    customer_id: int,
    username: str = Depends(jwt_required)
):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM customer WHERE customer_id=%s", (customer_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Customer not found")
        db.commit()
    except mysql.connector.Error:
        raise HTTPException(status_code=500, detail="Error deleting customer")
    finally:
        cursor.close()
    return {"message": "Customer deleted"}

@app.delete("/film/delete/{film_id}", status_code=200)
def delete_film(
    film_id: int,
    username: str = Depends(jwt_required)
):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM film WHERE film_id=%s", (film_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Film not found")
        db.commit()
    except mysql.connector.Error:
        raise HTTPException(status_code=500, detail="Error deleting film")
    finally:
        cursor.close()
    return {"message": "Film deleted"}
