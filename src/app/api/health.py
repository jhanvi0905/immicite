from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    # Liveness only; the database check is added with the schema (M1).
    return {"status": "ok"}
