from uuid import uuid4

from app.core.security import create_access_token, read_user_id_from_access_token


def test_access_token_roundtrip():
    user_id = uuid4()
    token = create_access_token(user_id)
    parsed_id = read_user_id_from_access_token(token)
    assert parsed_id == user_id
