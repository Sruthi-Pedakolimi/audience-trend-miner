from fastapi import FastAPI

from app.api.generate import router as generate_router
from app.api.portfolio import router as portfolio_router
from app.api.rejected import router as rejected_router

app = FastAPI()

app.include_router(generate_router)
app.include_router(portfolio_router)
app.include_router(rejected_router)


@app.get("/health")
def health():
    return {"status": "ok"}
