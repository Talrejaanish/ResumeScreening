from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    mpin: str = Field(pattern=r"^\d{4,8}$")

class LoginInput(BaseModel):
    email: EmailStr
    mpin: str

class ProfileInput(BaseModel):
    phone: Optional[str] = ""
    location: Optional[str] = ""
    skills: List[str] = []
    experience_years: float = 0
    education: Optional[str] = ""

class JobInput(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    company: str = Field(min_length=2, max_length=150)
    location: str = ""
    description: str = Field(min_length=20)
    required_skills: List[str] = []
