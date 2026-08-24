from unittest.mock import MagicMock, patch

import pytest

from howler.services import auth_service


def _mock_user_with_apikey(key_name="dev", acl=None):
    """Build a mock user with a single apikey."""
    if acl is None:
        acl = ["R", "W"]

    key_obj = MagicMock()
    key_obj.acl = acl
    key_obj.expiry_date = None

    user_data = MagicMock()
    user_data.apikeys = {key_name: key_obj}
    return user_data


@patch.object(auth_service, "redis")
@patch.object(auth_service, "verify_password", return_value=True)
@patch.object(auth_service, "datastore")
def test_cache_populated_on_successful_bcrypt(mock_ds, mock_verify, mock_redis):
    """After a successful bcrypt verification, the result is cached."""
    mock_redis.get.return_value = None
    user_data = _mock_user_with_apikey()
    mock_ds.return_value.user.get_if_exists.return_value = user_data

    result_user, result_acl = auth_service.validate_apikey("alice", "dev:s3cret")

    assert result_user == user_data
    assert result_acl == ["R", "W"]
    mock_verify.assert_called_once()
    mock_redis.setex.assert_called_once()


@patch.object(auth_service, "redis")
@patch.object(auth_service, "verify_password")
@patch.object(auth_service, "datastore")
def test_cache_hit_skips_bcrypt(mock_ds, mock_verify, mock_redis):
    """On a cache hit, bcrypt (verify_password) is not called."""
    expected_hash = auth_service._hash_secret("alice", "dev", "s3cret")
    mock_redis.get.return_value = expected_hash.encode()
    user_data = _mock_user_with_apikey()
    mock_ds.return_value.user.get_if_exists.return_value = user_data

    result_user, result_acl = auth_service.validate_apikey("alice", "dev:s3cret")

    assert result_user == user_data
    assert result_acl == ["R", "W"]
    mock_verify.assert_not_called()


@patch.object(auth_service, "redis")
@patch.object(auth_service, "verify_password", return_value=False)
@patch.object(auth_service, "datastore")
def test_failed_bcrypt_does_not_cache(mock_ds, mock_verify, mock_redis):
    """A failed bcrypt verification should not populate the cache."""
    mock_redis.get.return_value = None
    user_data = _mock_user_with_apikey()
    mock_ds.return_value.user.get_if_exists.return_value = user_data

    result_user, result_acl = auth_service.validate_apikey("alice", "dev:wrong")

    assert result_user is None
    assert result_acl is None
    mock_redis.setex.assert_not_called()


@patch.object(auth_service, "redis")
@patch.object(auth_service, "verify_password", return_value=True)
@patch.object(auth_service, "datastore")
def test_stale_cache_triggers_bcrypt(mock_ds, mock_verify, mock_redis):
    """If the cached hash doesn't match the current secret, bcrypt runs."""
    old_hash = auth_service._hash_secret("alice", "dev", "old_secret")
    mock_redis.get.return_value = old_hash.encode()
    user_data = _mock_user_with_apikey()
    mock_ds.return_value.user.get_if_exists.return_value = user_data

    result_user, result_acl = auth_service.validate_apikey("alice", "dev:new_secret")

    assert result_user == user_data
    mock_verify.assert_called_once()
    mock_redis.setex.assert_called_once()


@patch.object(auth_service, "config")
def test_encrypt_decrypt_non_jwt_token(mock_config):
    """Non-JWT credentials use AES-GCM and never appear in the ciphertext."""
    mock_config.system.jwe_secret_key = "0123456789abcdef0123456789abcdef"
    token = "analyst:internal-token"

    encrypted_token = auth_service.encrypt_token(token)

    assert encrypted_token is not None
    assert encrypted_token.startswith("aesgcm:")
    assert token not in encrypted_token
    assert auth_service.decrypt_token(encrypted_token) == token


@patch.object(auth_service.jwt_service, "encrypt_token", return_value="jwt-ciphertext")
def test_encrypt_jwt_delegates_to_jwt_service(mock_encrypt):
    """JWT-shaped tokens use the JWT service's JWE encryption."""
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZSJ9.c2lnbmF0dXJl"

    assert auth_service.encrypt_token(token) == "jwt-ciphertext"
    mock_encrypt.assert_called_once_with(token)


@patch.object(auth_service.jwt_service, "decrypt_token", return_value="jwt-token")
def test_decrypt_jwt_delegates_to_jwt_service(mock_decrypt):
    """Compact JWE ciphertext is decrypted by the JWT service."""
    encrypted_token = "header.encrypted-key.iv.ciphertext.tag"

    assert auth_service.decrypt_token(encrypted_token) == "jwt-token"
    mock_decrypt.assert_called_once_with(encrypted_token)


def test_non_jwt_with_three_segments_does_not_delegate_to_jwt_service():
    """Tokens with two periods are not mistaken for JWTs without a JWT header."""
    assert not auth_service._is_jwt("not.a.jwt")


@pytest.mark.parametrize("token", [None])
def test_encrypt_decrypt_none_token(token):
    """Absent tokens remain absent and do not require an encryption key."""
    assert auth_service.encrypt_token(token) is None
    assert auth_service.decrypt_token(token) is None
