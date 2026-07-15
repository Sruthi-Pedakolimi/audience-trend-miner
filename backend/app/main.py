from fastapi import FastAPI

from app.api.portfolio import router as portfolio_router

app = FastAPI()

app.include_router(portfolio_router)


@app.get("/health")
def health():
    return {"status": "ok"}
