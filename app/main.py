from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, constr

app = FastAPI()

class Transaction(BaseModel):
    id: int | None =None
    amount: float = Field(..., gt=0, description="The amount of the transaction must be greater than 0")
    currency: str = constr(min_length=3, max_length=3)
    description: str = constr(min_length=3, max_length=100)
    created_timestamp: datetime = datetime.now()
    updated_timestamp: datetime | None = None

transactions = [
    Transaction(id=1, amount=100.0, currency="USD", description="Payment for services"),
    Transaction(id=2, amount=250.5, currency="EUR", description="Invoice payment"),
    Transaction(id=3, amount=75.0, currency="PLN", description="Refund"),
    Transaction(id=4, amount=25.0, currency="PLN", description="Refund")
]

@app.get("/transactions")
def show_transactions():
    return transactions

@app.get("/transactions/{id}")
def show_transaction(id: int):
    for transaction in transactions:
        if transaction.id==id:
            return transaction
    else:
        raise HTTPException(status_code=404, detail="Transaction not found")
@app.post("/", status_code=201)
def create_transaction(transaction: Transaction):
    transaction.id = len(transactions)+1
    transactions.append(transaction)
    return transactions

@app.put("/transactions/{id}")
def update_transaction(id: int, updated_transaction: Transaction):
    for transaction in transactions:
        if transaction.id==id:
            transaction.amount = updated_transaction.amount
            transaction.currency = updated_transaction.currency
            transaction.description = updated_transaction.description
            transaction.updated_timestamp = datetime.now()
            return transaction
    else:
        raise HTTPException(status_code=404, detail="Transaction not found")

@app.delete("/transactions/{id}", status_code=204)
def delete_transaction(id: int):
    for transaction in transactions:
        if transaction.id==id:
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
    return sorted(transactions, key=lambda t: t.amount, reverse=reverse)

@app.get("/query")
def query_transactions(
        currency: Optional[str] = None,
        sort_by: str = "id",
        order: str = "desc"
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

    return results


@app.get("/report/summary")
def show_report_summary():

    currencies= {}

    for t in transactions:
        if t.currency in currencies.keys():
            currencies[t.currency] += t.amount
        else:
            currencies[t.currency] = t.amount

    return currencies

