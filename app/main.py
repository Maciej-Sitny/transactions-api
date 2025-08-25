from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, constr

app = FastAPI()

class Transaction(BaseModel):
    id: UUID
    amount: float = Field(..., gt=0, description="The amount of the transaction must be greater than 0")
    currency: str = constr(min_length=3, max_length=3)
    description: str = constr(min_length=3, max_length=100)
    created_timestamp: datetime = Field(default_factory=datetime.now)
    updated_timestamp: datetime | None = Field(default=None)

    class Config:
        extra = "forbid"

class TransactionResponse(BaseModel):
    id: UUID
    amount: float
    currency: str
    description: str

class PaginatedTransactions(BaseModel):
    page: int
    limit: int
    total: int
    data: list[TransactionResponse]

transactions = [
    Transaction(id=uuid4(), amount=100.0, currency="USD", description="Payment for services"),
    Transaction(id=uuid4(), amount=250.5, currency="EUR", description="Invoice payment"),
    Transaction(id=uuid4(), amount=75.0, currency="PLN", description="Refund"),
    Transaction(id=uuid4(), amount=25.0, currency="PLN", description="Refund")
]

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
):

    result = pagify(transactions, page, limit)

    return result

@app.get("/transactions/{id}", response_model=TransactionResponse)
def show_transaction(id: str):
    for transaction in transactions:
        if transaction.id==UUID(id):
            return transaction
    else:
        raise HTTPException(status_code=404, detail="Transaction not found")
@app.post("/transactions", status_code=201, response_model=TransactionResponse)
def create_transaction(transaction: Transaction):
    transaction.id = uuid4()
    transactions.append(transaction)
    return transactions

@app.put("/transactions/{id}", response_model=TransactionResponse)
def update_transaction(id: str, updated_transaction: Transaction):
    for transaction in transactions:
        if transaction.id==UUID(id):
            transaction.amount = updated_transaction.amount
            transaction.currency = updated_transaction.currency
            transaction.description = updated_transaction.description
            transaction.updated_timestamp = datetime.now()
            return transaction
    else:
        raise HTTPException(status_code=404, detail="Transaction not found")

@app.delete("/transactions/{id}", status_code=204, response_model=TransactionResponse)
def delete_transaction(id: str):
    for transaction in transactions:
        if transaction.id==UUID(id):
            transactions.remove(transaction)
            return transaction
    else:
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

class ReportSummaryResponse(BaseModel):
    __root__: dict[str, CurrencySummary]

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

