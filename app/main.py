from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4
from fastapi import FastAPI, HTTPException, Depends
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, constr, field_validator, RootModel
from enum import Enum
from fastapi.responses import JSONResponse
from fastapi.requests import Request
import logging
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext

app = FastAPI()

SECRET_KEY = "supersecretkey123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

fake_users_db = {
    "alice": {
        "username": "alice",
        "hashed_password": pwd_context.hash("password123"),
    }
}

def authenticate_user(username: str, password: str):
    user = fake_users_db.get(username)
    if not user or not pwd_context.verify(password, user["hashed_password"]):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
        to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub":user["username"]}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

logging.basicConfig(level=logging.INFO)

class Currency (str, Enum):
    USD = "USD"
    GBP = "GBP"
    JPY = "JPY"
    PLN = "PLN"
    EUR="EUR"
    CHF="CHF"


class Transaction(BaseModel):
    id: UUID
    amount: float = Field(..., gt=0, description="The amount of the transaction must be greater than 0")
    currency: Currency = Field(..., description="The currency of the transaction")
    description: str = constr(min_length=3, max_length=100)
    created_timestamp: datetime = Field(default_factory=datetime.now)
    updated_timestamp: datetime | None = Field(default=None)

    # @field_validator("currency", mode="before")
    # def validate_currency(cls, v):
    #     return v.upper()

    class Config:
        extra = "forbid"

class TransactionResponse(BaseModel):
    user: str
    transaction: Transaction

class PaginatedTransactions(BaseModel):
    page: int
    limit: int
    total: int
    data: list[TransactionResponse]

transactions = [
    Transaction(id=uuid4(), amount=100.0, currency=Currency("USD"), description="Payment for services", created_timestamp=datetime.now(), updated_timestamp=None),
    Transaction(id=uuid4(), amount=250.5, currency=Currency("EUR"), description="Invoice payment", created_timestamp=datetime.now(), updated_timestamp=None),
    Transaction(id=uuid4(), amount=75.0, currency=Currency("PLN"), description="Refund",created_timestamp=datetime.now(), updated_timestamp=None),
    Transaction(id=uuid4(), amount=25.0, currency=Currency("PLN"), description="Refund", created_timestamp=datetime.now(), updated_timestamp=None)
]

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "code": exc.status_code
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "details": exc.errors(),
            "code": 422
        },
    )

def pagify(
        data: list | dict,
        page: int,
        limit: int
):
    if page < 1 or limit<1:
        raise HTTPException(status_code=404, detail="Invalid page or limit number")

    start = (page - 1) * limit
    end = page * limit

    return {
        "page": page,
        "limit": limit,
        "total": len(data),
        "data": data[start:end],
    }



@app.get("/transactions", response_model=PaginatedTransactions)
def show_transactions(
        page: int = 1,
        limit : int = 10,
        user: str = Depends(get_current_user)
):

    result = pagify(transactions, page, limit)
    result["data"] = [{"user": user, "transaction": t} for t in result["data"]]
    return result

@app.get("/transactions/{id}", response_model=TransactionResponse)
def show_transaction(id: str, user= Depends(get_current_user)):
    for transaction in transactions:
        if transaction.id==UUID(id):
            return {"user": user, "transaction": transaction}
    else:
        raise HTTPException(status_code=404, detail="Transaction not found")
@app.post("/transactions", status_code=201, response_model=TransactionResponse)
def create_transaction(transaction: Transaction, user = Depends(get_current_user)):
    transaction.id = uuid4()
    transactions.append(transaction)
    logging.info(f"Created transaction {transaction.id} for {transaction.amount} {transaction.currency}")
    return {"user": user, "transaction": transaction}

@app.put("/transactions/{id}", response_model=TransactionResponse)
def update_transaction(id: str, updated_transaction: Transaction, user= Depends(get_current_user)):
    for transaction in transactions:
        if transaction.id==UUID(id):
            transaction.amount = updated_transaction.amount
            transaction.currency = updated_transaction.currency
            transaction.description = updated_transaction.description
            transaction.updated_timestamp = datetime.now()
            logging.info(f"Updated transaction {id}")
            return {"user": user, "transaction":transaction}
    else:
        logging.error(f"Transaction {id} not found")
        raise HTTPException(status_code=404, detail="Transaction not found")

@app.delete("/transactions/{id}", status_code=200, response_model=TransactionResponse)
def delete_transaction(id: str, user= Depends(get_current_user)):
    for transaction in transactions:
        if transaction.id==UUID(id):
            transactions.remove(transaction)
            logging.warning(f"Deleted transaction {id}")
            return { "user": user, "transaction":transaction}
    else:
        logging.error(f"Attempt to delete non-existent transaction of id {id}")
        raise HTTPException(status_code=404, detail="Transaction not found")

@app.get("/filter/{currency}")
def show_filter(currency: str):
    return [t for t in transactions if t.currency==currency]


@app.get("/sorted")
def sort_transactions(by: str = "id", order: str = "asc"):
    reverse = order == "desc"
    return sorted(transactions, key=lambda t: getattr(t, by), reverse=reverse)

@app.get("/query", response_model=PaginatedTransactions)
def query_transactions(
        currency: Optional[str] = None,
        sort_by: str = "id",
        order: str = "desc",
        page: int =1,
        limit: int =10
):
    valid_sort_fields = ["id", "amount", "currency"]
    if sort_by not in valid_sort_fields:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by, must be one of {valid_sort_fields}")

    if order not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="Invalid order, must be 'asc' or 'desc'")


    results =transactions
    if currency:
        results = [t for t in transactions if t.currency==currency]

    reverse = order == "desc"
    results = sorted(results, key=lambda t: getattr(t, sort_by), reverse=reverse)


    return pagify(results, page, limit)



class CurrencySummary(BaseModel):
    count: int
    total: float

class ReportSummaryResponse(RootModel[dict[str, float]]):
    pass

@app.get("/report/summary", response_model=ReportSummaryResponse)
def show_report_summary():

    currencies= {}

    for t in transactions:
        if t.currency in currencies.keys():
            currencies[t.currency]["count"] += 1
            currencies[t.currency]["total"] += t.amount
        else:
            currencies[t.currency] = {"count": 1, "total": t.amount}

    return currencies

