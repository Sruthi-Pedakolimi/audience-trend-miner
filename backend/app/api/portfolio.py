import json

from fastapi import APIRouter, HTTPException

from app.agent.graph import LIVE_CACHE_PATH
from app.agent.schemas import PortfolioEntry

router = APIRouter()


@router.get("/portfolio")
def get_portfolio() -> dict:
    if not LIVE_CACHE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No cached portfolio found at {LIVE_CACHE_PATH}",
        )

    payload = json.loads(LIVE_CACHE_PATH.read_text())
    portfolio = [
        PortfolioEntry.model_validate(entry).model_dump()
        for entry in payload["final_portfolio"]
    ]

    return {
        "generated_at": payload["generated_at"],
        "source": payload["source"],
        "portfolio": portfolio,
    }
