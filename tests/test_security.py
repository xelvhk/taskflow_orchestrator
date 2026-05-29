from app.core.security import hash_api_key, verify_api_key


def test_hash_api_key_is_deterministic_and_verifiable() -> None:
    api_key = "tf_secret"
    api_key_hash = hash_api_key(api_key)

    assert api_key_hash != api_key
    assert verify_api_key(api_key, api_key_hash)
    assert not verify_api_key("tf_wrong", api_key_hash)
