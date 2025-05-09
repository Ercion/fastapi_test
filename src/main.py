from sqlmodel import SQLModel, Field, create_engine, Session, select, func
from fastapi import FastAPI, HTTPException, Depends
#from pydantic import BaseModel,Field    
from datetime import date
from collections.abc import Sequence
from collections import defaultdict
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

# Define the Expense model
class Expense(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category: str = Field(max_length=50, description="Category of the expense")
    amount: float = Field(gt=0, description="Amount must be greater than 0")
    date: date


class ExpenseCreate(SQLModel):
    category: str = Field(max_length=50)
    amount: float = Field(gt=0)
    date: date

#database connection
sqlite_file_name = "expenses.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=True)

# Create the database and tables
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

#expenses_list = []

def get_session():
    with Session(engine) as session:
        yield session

@app.get("/")
def root():
    return {"message": "Hello, World!"}

@app.post("/expenses/", response_model=Expense)
def create_expense(
    expense: ExpenseCreate, 
    session: Session = Depends(get_session)
):
    new_expense = Expense(**expense.model_dump())
    try:
        session.add(new_expense)
        session.commit()
        session.refresh(new_expense)
        return new_expense
    except Exception as e:
        print("🚨 Exception occurred:", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/expenses/", response_model=Sequence[Expense])
def get_all_expenses(session: Session = Depends(get_session)):
    expenses = session.exec(select(Expense)).all()
    if not expenses:
        raise HTTPException(status_code=404, detail="No expenses found")
    return expenses

@app.get("/expenses/category/{category}", response_model=Sequence[Expense])
def get_category_based_expenses(
    category: str, 
    session: Session = Depends(get_session)
):
    if not category:
        raise HTTPException(status_code=400, detail="Category is required")
    try:
        expenses = session.exec(select(Expense).where(
                func.lower(Expense.category) == category.lower())
        ).all()
    except Exception as e:
        print("🚨 Exception occurred:", e)
        raise HTTPException(status_code=500, detail=str(e))
    if not expenses:
        raise HTTPException(status_code=404, detail="No expenses found")
    return expenses

@app.get("/expenses/summary/{min_amount}", response_model=dict)
def get_summary(
    min_amount: float = 0, 
    session: Session = Depends(get_session)
):
    expenses_list = session.exec(select(Expense)).all()
    
    if not expenses_list:
        raise HTTPException(status_code=404, detail="No expenses found")
    
    expense_summary = defaultdict(float)
    for expense in expenses_list:
        expense_summary[expense.category] += expense.amount
    return{ 
            category: amount
            for category, amount in sorted(
                expense_summary.items(), key=lambda x: x[1], reverse=True
            )
            if amount > min_amount 
    }

@app.delete("/expenses/{index}", response_model=dict)
def delete_expense(
    index: int, 
    session: Session= Depends(get_session)
):
    if not index:
        raise HTTPException(status_code=400, detail="Expense index is required")
    try:
        
        deleted_expense = session.exec(select(Expense).where(Expense.id == index)).one()
        session.delete(deleted_expense)
        session.commit()
        if not deleted_expense:
            raise HTTPException(status_code=404, detail="Expense index not found")
    except Exception as e:
        print("🚨 Exception occurred:", e)
        raise HTTPException(status_code=500, detail=str(e))

    return {"message":f"Deleted expense at {index} --> {deleted_expense}"}


@app.put("/expenses/{index}", response_model=Expense)
def update_expense(
    index: int, expense: Expense, 
    session: Session = Depends(get_session)
):
    
    updated_expense = session.exec(select(Expense).where(Expense.id == index)).one()
    update = expense.model_dump(exclude_unset=True)
    for key, value in update.items():
        setattr(updated_expense, key, value)
    session.add(updated_expense)
    session.commit()
    session.refresh(updated_expense)
    
    if not updated_expense:
        raise HTTPException(status_code=404, detail="Expense index not found")
    return updated_expense

@app.get("/expenses/search/", response_model=Sequence[Expense])
def search_expenses(q: str | None = None, session: Session = Depends(get_session)):
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    
    searched_expenses = session.exec(select(Expense).where(
        func.lower(Expense.category) == q.lower()
    )).all()

    if not searched_expenses:
        raise HTTPException(status_code=404, detail="No expenses found")    
    else: 
        return searched_expenses


@app.get("/expenses/datefilter/", response_model=Sequence[Expense])
def search_expenses_bydate(
    start_date: date | None = None, 
    end_date: date =  date.today(),
    session: Session = Depends(get_session)
):
   with Session(engine) as session:
         expenses_list = session.exec(select(Expense)).all()
   return [
       expense for expense in expenses_list 
       if (not start_date or start_date <= expense.date) and 
       (not end_date or expense.date <= end_date)
        ]
