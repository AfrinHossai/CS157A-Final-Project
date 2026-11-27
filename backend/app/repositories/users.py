from ..db import get_db


def find_by_email(email):
    with get_db().cursor(dictionary=True) as cur:
        cur.execute(
            "SELECT user_id, name, email, password_hash FROM `User` WHERE email = %s",
            (email,),
        )
        return cur.fetchone()


def find_by_id(user_id):
    with get_db().cursor(dictionary=True) as cur:
        cur.execute(
            "SELECT user_id, name, email FROM `User` WHERE user_id = %s",
            (user_id,),
        )
        return cur.fetchone()


def create(name, email, password_hash):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO `User` (name, email, password_hash) VALUES (%s, %s, %s)",
            (name, email, password_hash),
        )
        user_id = cur.lastrowid
    conn.commit()
    return user_id
