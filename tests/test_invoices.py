"""Invoices, customers, tenant isolation, payment portal and proof uploads."""
import io

import pytest

import app.api.invoices as invoices_api
from conftest import INVOICE


async def _create_invoice(client, **overrides):
    r = await client.post("/api/invoices", json={**INVOICE, **overrides})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def test_invoice_crud(user_client):
    inv_id = await _create_invoice(user_client)
    listed = (await user_client.get("/api/invoices")).json()
    assert any(i["id"] == inv_id for i in listed)

    r = await user_client.patch(f"/api/invoices/{inv_id}", json={"status": "reminded", "reminders": 1})
    assert r.status_code == 200
    assert next(i for i in (await user_client.get("/api/invoices")).json() if i["id"] == inv_id)["status"] == "reminded"

    assert (await user_client.delete(f"/api/invoices/{inv_id}")).status_code in (200, 204)
    assert not any(i["id"] == inv_id for i in (await user_client.get("/api/invoices")).json())


async def test_patch_cannot_change_owner(user_client):
    inv_id = await _create_invoice(user_client)
    await user_client.patch(f"/api/invoices/{inv_id}", json={"owner_id": "000000000000000000000000"})
    assert any(i["id"] == inv_id for i in (await user_client.get("/api/invoices")).json())


async def test_tenant_isolation(user_client, new_client, unique_email):
    from conftest import register_and_login
    inv_id = await _create_invoice(user_client)
    other = new_client()
    await register_and_login(other, unique_email("other"))

    assert not any(i["id"] == inv_id for i in (await other.get("/api/invoices")).json())
    assert (await other.patch(f"/api/invoices/{inv_id}", json={"status": "recovered"})).status_code in (403, 404)
    assert (await other.delete(f"/api/invoices/{inv_id}")).status_code in (403, 404)


async def test_customer_crud_and_recalculate(user_client):
    r = await user_client.post("/api/customers", json={"company": "Beta Pvt", "phone": "+919800000001", "city": "Pune"})
    assert r.status_code in (200, 201)
    cust_id = r.json()["id"]
    await _create_invoice(user_client, company="Beta Pvt", customerId=cust_id, amount=5000)

    assert (await user_client.put(f"/api/customers/{cust_id}", json={"city": "Mumbai"})).json()["city"] == "Mumbai"
    assert (await user_client.post(f"/api/customers/{cust_id}/recalculate")).status_code == 200
    assert (await user_client.delete(f"/api/customers/{cust_id}")).status_code in (200, 204)


async def test_portal_link_is_public_and_owner_safe(user_client, new_client):
    inv_id = await _create_invoice(user_client)
    token = (await user_client.post(f"/api/invoices/{inv_id}/portal-link")).json()["token"]
    view = await new_client().get(f"/api/invoices/portal/{token}")
    assert view.status_code == 200
    body = view.json()
    assert body["company"] == INVOICE["company"] and body["invoiceNo"] == INVOICE["invoiceNo"]
    assert "owner_id" not in body
    assert (await new_client().get("/api/invoices/portal/not-a-real-token")).status_code == 404


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(invoices_api, "_get_upload_dir", lambda: str(tmp_path))
    return tmp_path


PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + b"0" * 64
JPEG = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"0" * 64
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.mark.parametrize("name, data, mime", [
    ("proof.pdf", PDF, "application/pdf"),
    ("proof.png", PNG, "image/png"),
    ("proof.jpg", JPEG, "image/jpeg"),
    ("proof.jpg", JPEG, "image/jpg"),
    ("lead.pdf", b"\n\n" + PDF, "application/pdf"),  # %PDF allowed within the first 1 KB
])
async def test_valid_uploads_accepted(user_client, upload_dir, name, data, mime):
    r = await user_client.post("/api/invoices/upload-proof", files={"file": (name, io.BytesIO(data), mime)})
    assert r.status_code == 201, r.text
    assert (upload_dir / r.json()["proof_url"].rsplit("/", 1)[1]).read_bytes() == data


@pytest.mark.parametrize("name, data, mime", [
    ("evil.pdf", b"MZ\x90\x00 executable bytes", "application/pdf"),   # unknown magic bytes
    ("evil.pdf", PNG, "application/pdf"),                              # content/type mismatch
    ("evil.exe", PDF, "application/pdf"),                              # extension not allowed
    ("evil.pdf", PDF, "text/html"),                                    # MIME not allowed
])
async def test_bad_uploads_rejected(user_client, upload_dir, name, data, mime):
    r = await user_client.post("/api/invoices/upload-proof", files={"file": (name, io.BytesIO(data), mime)})
    assert r.status_code == 400, r.text
    assert not list(upload_dir.iterdir())
