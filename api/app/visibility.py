"""Who may see which rows.

Admins see everything. Sales users see every company and contact, but only the deals and
activities they own. The same rule is enforced again in PostgreSQL (row-level security) for
the read-only role used by the Ask tab, so keep both in sync when it changes.
"""

from sqlalchemy import Select

from app.models import Activity, Deal, User


def visible_deals(query: Select, user: User) -> Select:
    return query if user.role == "admin" else query.where(Deal.owner_id == user.id)


def visible_activities(query: Select, user: User) -> Select:
    return query if user.role == "admin" else query.where(Activity.owner_id == user.id)
