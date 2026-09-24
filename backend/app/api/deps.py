from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    get_current_user,
    get_optional_user,
    require_admin,
    require_admin_only,
)
from app.models import User

DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
AdminUser = Annotated[User, Depends(require_admin_only)]
StaffUser = Annotated[User, Depends(require_admin)]
