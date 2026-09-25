"""Create org units and one demo user per role. Safe to run more than once.

    python -m app.scripts.seed

Demo password comes from SEED_DEMO_PASSWORD in .env.
"""

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.rbac import Role
from app.core.security import hash_password
from app.models import OrgUnit, User
from app.models.enums import OrgType

ORG_UNITS = [
    ("CMPDI", "Central Mine Planning & Design Institute Limited", OrgType.SUBSIDIARY),
    ("ECL", "Eastern Coalfields Limited", OrgType.SUBSIDIARY),
    ("BCCL", "Bharat Coking Coal Limited", OrgType.SUBSIDIARY),
    ("CCL", "Central Coalfields Limited", OrgType.SUBSIDIARY),
    ("WCL", "Western Coalfields Limited", OrgType.SUBSIDIARY),
    ("SECL", "South Eastern Coalfields Limited", OrgType.SUBSIDIARY),
    ("NCL", "Northern Coalfields Limited", OrgType.SUBSIDIARY),
    ("MCL", "Mahanadi Coalfields Limited", OrgType.SUBSIDIARY),
    ("CIL_HQ", "Coal India Limited (Headquarters)", OrgType.HQ),
    ("MINISTRY", "Ministry of Coal", OrgType.MINISTRY),
]

# (email, name, roles, org unit code)
DEMO_USERS = [
    ("admin@koylasetu.local", "Demo Admin", [Role.ADMIN], "CIL_HQ"),
    ("operator@koylasetu.local", "Demo Data Operator", [Role.OPERATOR], "CMPDI"),
    ("reviewer@koylasetu.local", "Demo Reviewer", [Role.REVIEWER], "CMPDI"),
    ("analyst@koylasetu.local", "Demo Analyst", [Role.ANALYST], "CIL_HQ"),
    ("approver@koylasetu.local", "Demo Approver", [Role.APPROVER], "CIL_HQ"),
    ("viewer@koylasetu.local", "Demo Viewer", [Role.VIEWER], "MINISTRY"),
]


def main() -> None:
    password_hash = hash_password(get_settings().seed_demo_password)
    with SessionLocal() as db:
        units: dict[str, OrgUnit] = {u.code: u for u in db.scalars(select(OrgUnit))}
        for code, name, org_type in ORG_UNITS:
            if code not in units:
                units[code] = OrgUnit(code=code, name=name, type=org_type)
                db.add(units[code])
        db.flush()

        existing = set(db.scalars(select(User.email)))
        for email, name, roles, unit_code in DEMO_USERS:
            if email in existing:
                continue
            db.add(
                User(
                    name=name,
                    email=email,
                    password_hash=password_hash,
                    roles=[r.value for r in roles],
                    org_unit_id=units[unit_code].id,
                    is_active=True,
                )
            )
        db.commit()
    print(f"Seeded {len(ORG_UNITS)} org units and {len(DEMO_USERS)} demo users.")
    for email, _, roles, unit in DEMO_USERS:
        print(f"  {email:28} {'+'.join(roles):10} {unit}")


if __name__ == "__main__":
    main()
