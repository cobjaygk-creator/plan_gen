"""Read API for the isolated preregistration landing-page benchmark."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..media_cache import as_absolute_path
from ..models import User
from .models import GamePreRegistration, PreRegistrationType

router = APIRouter(prefix="/preregistrations", tags=["preregistrations"])


@router.get("/campaigns")
def list_campaigns(
    campaign_type: PreRegistrationType | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return verified game preregistration campaigns, newest discovery first."""
    query = select(GamePreRegistration).where(GamePreRegistration.is_game_preregistration.is_(True))
    if campaign_type:
        query = query.where(GamePreRegistration.preregistration_type == campaign_type.value)
    campaigns = db.scalars(query.order_by(GamePreRegistration.discovered_at.desc())).all()
    return {
        "types": [item.value for item in PreRegistrationType],
        "campaigns": [
            {
                "id": item.id,
                "game_name": item.game_name,
                "normalized_game_name": item.normalized_game_name,
                "campaign_name": item.campaign_name,
                "preregistration_type": item.preregistration_type,
                "developer": item.developer,
                "publisher": item.publisher,
                "genre": item.genre,
                "platform": item.platform.split(",") if item.platform else [],
                "preregistration_start_date": item.preregistration_start_date,
                "preregistration_end_date": item.preregistration_end_date,
                "release_date": item.release_date,
                "update_date": item.update_date,
                "official_url": item.official_url,
                "preregistration_url": item.preregistration_url,
                "thumbnail_url": as_absolute_path(item.thumbnail_url),
                "main_visual_url": as_absolute_path(item.main_visual_url),
                "status": item.status,
                "confidence_score": item.confidence_score,
                "discovered_at": item.discovered_at,
            }
            for item in campaigns
        ],
    }
