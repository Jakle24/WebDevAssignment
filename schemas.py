#create a schema for your login details using the code below


# schemas.py
# Importing the necessary librarys
from pydantic import BaseModel
class AuthDetails(BaseModel):
    username: str
    password: str