"""Quick test — writes results to a file."""
import pathlib

results = []

try:
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    h = ctx.hash("testpass")
    assert ctx.verify("testpass", h)
    assert not ctx.verify("wrongpass", h)
    results.append("PASS: bcrypt hashing + verification")
except Exception as e:
    results.append(f"FAIL: bcrypt - {e}")

try:
    from jose import jwt
    token = jwt.encode({"sub": "test@example.com"}, "secret", algorithm="HS256")
    payload = jwt.decode(token, "secret", algorithms=["HS256"])
    assert payload["sub"] == "test@example.com"
    results.append("PASS: JWT encode + decode")
except Exception as e:
    results.append(f"FAIL: JWT - {e}")

try:
    from app.core.security import verify_password, get_password_hash, create_access_token
    from app.api.auth import router as auth_router
    from app.api.deps import get_current_user
    results.append("PASS: all new modules import cleanly")
except Exception as e:
    results.append(f"FAIL: imports - {e}")

try:
    from app.core.security import verify_password, get_password_hash, create_access_token
    hashed = get_password_hash("mypassword")
    assert verify_password("mypassword", hashed)
    assert not verify_password("wrong", hashed)
    tok = create_access_token(data={"sub": "user@test.com"})
    assert len(tok) > 0
    results.append("PASS: full security flow (hash -> verify -> token)")
except Exception as e:
    results.append(f"FAIL: security flow - {e}")

results.append("\nALL TESTS PASSED ✅" if all(r.startswith("PASS") for r in results) else "\nSOME TESTS FAILED ❌")

pathlib.Path("test_auth_results.txt").write_text("\n".join(results), encoding="utf-8")
