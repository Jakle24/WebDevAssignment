#create a schema for your login details using the code below


# schemas.py
# Importing the necessary librarys
from pydantic import BaseModel, EmailStr, constr

class AuthDetails(BaseModel):
    username: str
    password: str

class CustomerCreate(BaseModel):
    first_name: constr(min_length=1, max_length=45)
    last_name: constr(min_length=1, max_length=45)
    email: EmailStr
    password: constr(min_length=8)
    # Add other fields as needed