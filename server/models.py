from pydantic import BaseModel
from typing import Optional

class TimeEntry(BaseModel):
    date: str
    clock_in: Optional[str] = None
    clock_out: Optional[str] = None
    pause_start: Optional[str] = None
    pause_end: Optional[str] = None
    note: str = ""
    is_manual: int = 0

class Absence(BaseModel):
    type: str
    start_date: str
    end_date: str
    days: float = 1.0
    note: str = ""

class Settings(BaseModel):
    weekly_hours: float
    vacation_days: float
    employee_name: str
    pause_duration: float = 30
    friday_hours: float = 0

class LoginRequest(BaseModel):
    name: str
    pin: str

class CreateUser(BaseModel):
    name: str
    pin: str
