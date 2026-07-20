from sqlalchemy.orm import Session

from app.models.user import User
from app.models.role import Role

from app.core.security import hash_password



def create_admin(db:Session):


    role = db.query(Role).filter(
        Role.name=="Admin"
    ).first()



    if not role:

        role=Role(
            name="Admin"
        )

        db.add(role)

        db.commit()

        db.refresh(role)



    user=db.query(User).filter(
        User.username=="admin"
    ).first()



    if not user:

        user=User(

            username="admin",

            email="admin@example.com",

            full_name="Administrator",

            password_hash=hash_password(
                "admin123"
            ),

        )

        user.roles.append(role)

        db.add(user)

        db.commit()