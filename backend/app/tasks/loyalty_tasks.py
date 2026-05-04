from app.tasks.celery_app import celery_app
from app.core.database import get_sync_db
from app.services.billing_service import recalculate_loyalty


@celery_app.task(name="app.tasks.loyalty_tasks.recalculate_all_loyalty_levels")
def recalculate_all_loyalty_levels():
    from sqlalchemy import select as sync_select
    from app.models.user import User

    db = next(get_sync_db())
    updated = 0
    try:
        users = db.execute(sync_select(User).where(User.is_active == True)).scalars().all()
        for user in users:
            new_level = recalculate_loyalty(user.monthly_checks)
            if user.loyalty_level != new_level:
                user.loyalty_level = new_level
            user.monthly_checks = 0
            updated += 1

        db.commit()
        return {"updated": updated, "status": "ok"}
    except Exception as exc:
        db.rollback()
        raise
    finally:
        db.close()
