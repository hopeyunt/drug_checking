import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from app.models.drug import Drug
from app.services import drug_service


@pytest_asyncio.fixture
async def drug_in_db(db):
    drug = Drug(trade_name="Варфарин", inn="warfarin", atc_code="B01AA03", source="grls")
    db.add(drug)
    await db.commit()
    await db.refresh(drug)
    yield drug
    await db.delete(drug)
    await db.commit()


@pytest.mark.asyncio
async def test_search_by_trade_name(db, drug_in_db):
    results = await drug_service.search_drugs_local(db, "Варфарин")
    assert any(d.trade_name == "Варфарин" for d in results)


@pytest.mark.asyncio
async def test_search_by_inn(db, drug_in_db):
    results = await drug_service.search_drugs_local(db, "warfarin")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_search_partial_match(db, drug_in_db):
    results = await drug_service.search_drugs_local(db, "арфа")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_search_no_results(db):
    results = await drug_service.search_drugs_local(db, "несуществующий_xyz_999")
    assert results == []


@pytest.mark.asyncio
async def test_get_drug_by_name_found(db, drug_in_db):
    result = await drug_service.get_drug_by_name(db, "Варфарин")
    assert result is not None
    assert result.inn == "warfarin"


@pytest.mark.asyncio
async def test_get_drug_by_name_by_inn(db, drug_in_db):
    result = await drug_service.get_drug_by_name(db, "warfarin")
    assert result is not None


@pytest.mark.asyncio
async def test_get_drug_by_name_case_insensitive(db, drug_in_db):
    result = await drug_service.get_drug_by_name(db, "варфарин")
    assert result is not None


@pytest.mark.asyncio
async def test_get_drug_by_name_not_found(db):
    result = await drug_service.get_drug_by_name(db, "абсолютно_несуществующий_xyz")
    assert result is None


def _mock_grls_client(response_data):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = response_data
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


@pytest.mark.asyncio
async def test_fetch_from_grls_success():
    mock_ctx = _mock_grls_client(
        {"data": [{"tradeName": "Варфарин", "mnnName": "warfarin", "atcCode": "B01AA03"}]}
    )
    with patch("app.services.drug_service.httpx.AsyncClient", return_value=mock_ctx):
        result = await drug_service.fetch_from_grls("Варфарин")
    assert result is not None
    assert result["inn"] == "warfarin"
    assert result["atc_code"] == "B01AA03"


@pytest.mark.asyncio
async def test_fetch_from_grls_empty_data():
    mock_ctx = _mock_grls_client({"data": []})
    with patch("app.services.drug_service.httpx.AsyncClient", return_value=mock_ctx):
        result = await drug_service.fetch_from_grls("НеизвестноеНазвание")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_from_grls_non_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.drug_service.httpx.AsyncClient", return_value=mock_ctx):
        result = await drug_service.fetch_from_grls("Варфарин")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_from_grls_network_error():
    import httpx
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.drug_service.httpx.AsyncClient", return_value=mock_ctx):
        result = await drug_service.fetch_from_grls("Варфарин")
    assert result is None


@pytest.mark.asyncio
async def test_resolve_drug_found_in_db(db, drug_in_db):
    result = await drug_service.resolve_drug(db, "Варфарин")
    assert result is not None
    assert result.inn == "warfarin"


@pytest.mark.asyncio
async def test_resolve_drug_from_grls(db):
    with patch("app.services.drug_service.fetch_from_grls", return_value={
        "trade_name": "ТестПрепарат", "inn": "test_inn", "atc_code": "T00"
    }):
        result = await drug_service.resolve_drug(db, "ТестПрепарат_уникальный_xyz")
    assert result is not None
    assert result.inn == "test_inn"


@pytest.mark.asyncio
async def test_resolve_drug_not_found_anywhere(db):
    with patch("app.services.drug_service.fetch_from_grls", return_value=None):
        result = await drug_service.resolve_drug(db, "НесуществующийПрепарат")
    assert result is None


@pytest.mark.asyncio
async def test_resolve_drug_grls_no_inn(db):
    with patch("app.services.drug_service.fetch_from_grls", return_value={
        "trade_name": "Препарат", "inn": "", "atc_code": ""
    }):
        result = await drug_service.resolve_drug(db, "ПрепаратБезМНН")
    assert result is None
