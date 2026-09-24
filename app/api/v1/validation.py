from fastapi import APIRouter, Depends

from app.core.db import get_db
from app.core.deps import require
from app.core.serialize import to_public
from app.services.validation_service import ValidationService

router = APIRouter(prefix="/validation-results", tags=["validation"])


@router.get("/{result_id}")
def get_result(result_id: str, user=Depends(require("dm.read")), db=Depends(get_db)):
    return to_public(ValidationService(db).get_result(user, result_id))
