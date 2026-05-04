import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import json


# para tests async
@pytest.mark.anyio
async def test_validate_token_success():
    # test para verificar q token válido retorna el payload correctamente
    mock_payload = {"sub": "user123", "email": "test@test.com"}
    mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
    mock_credentials.credentials = "valid.token.here"

    with patch("src.auth_utils.os.getenv", side_effect=lambda k: {
        "AUTH0_DOMAIN": "test.auth0.com",
        "AUTH0_AUDIENCE": "test-audience"
    }.get(k)):
        with patch("src.auth_utils.urlopen") as mock_urlopen:
            mock_jwks = {"keys": [{"kid": "key1", "kty": "RSA", "use": "sig", "n": "abc", "e": "AQAB"}]}
            mock_urlopen.return_value.read.return_value = json.dumps(mock_jwks).encode()

            with patch("src.auth_utils.jwt.get_unverified_header", return_value={"kid": "key1"}):
                with patch("src.auth_utils.jwt.decode", return_value=mock_payload):
                    from src.auth_utils import validate_token
                    result = await validate_token(mock_credentials)
                    assert result == mock_payload


@pytest.mark.anyio
async def test_validate_token_invalid_raises_401():
    # test para verificar q token inválido lanza HTTPException 401
    mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
    mock_credentials.credentials = "invalid.token"

    with patch("src.auth_utils.os.getenv", side_effect=lambda k: {
        "AUTH0_DOMAIN": "test.auth0.com",
        "AUTH0_AUDIENCE": "test-audience"
    }.get(k)):
        with patch("src.auth_utils.urlopen") as mock_urlopen:
            mock_jwks = {"keys": [{"kid": "key1", "kty": "RSA", "use": "sig", "n": "abc", "e": "AQAB"}]}
            mock_urlopen.return_value.read.return_value = json.dumps(mock_jwks).encode()

            with patch("src.auth_utils.jwt.get_unverified_header", return_value={"kid": "key1"}):
                with patch("src.auth_utils.jwt.decode", side_effect=Exception("token inválido")):
                    from src.auth_utils import validate_token
                    with pytest.raises(HTTPException) as exc:
                        await validate_token(mock_credentials)
                    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_validate_token_no_matching_key_raises_401():
    # test para verificar q si no hay key que coincida con kid, lanza 401
    mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
    mock_credentials.credentials = "some.token"

    with patch("src.auth_utils.os.getenv", side_effect=lambda k: {
        "AUTH0_DOMAIN": "test.auth0.com",
        "AUTH0_AUDIENCE": "test-audience"
    }.get(k)):
        with patch("src.auth_utils.urlopen") as mock_urlopen:
            # kid diferente al del token
            mock_jwks = {"keys": [{"kid": "other-key", "kty": "RSA", "use": "sig", "n": "abc", "e": "AQAB"}]}
            mock_urlopen.return_value.read.return_value = json.dumps(mock_jwks).encode()

            with patch("src.auth_utils.jwt.get_unverified_header", return_value={"kid": "key1"}):
                from src.auth_utils import validate_token
                with pytest.raises(HTTPException) as exc:
                    await validate_token(mock_credentials)
                assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_validate_token_urlopen_fails_raises_401():
    # test para verificar q si falla la descarga del JWKS, lanza 401
    mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
    mock_credentials.credentials = "some.token"

    with patch("src.auth_utils.os.getenv", side_effect=lambda k: {
        "AUTH0_DOMAIN": "test.auth0.com",
        "AUTH0_AUDIENCE": "test-audience"
    }.get(k)):
        with patch("src.auth_utils.urlopen", side_effect=Exception("conexión fallida")):
            from src.auth_utils import validate_token
            with pytest.raises(HTTPException) as exc:
                await validate_token(mock_credentials)
            assert exc.value.status_code == 401