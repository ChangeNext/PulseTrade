from pathlib import Path

from app.stock_listing import StockListingRepository


def test_stock_listing_search_reads_krx_html_export() -> None:
    repository = StockListingRepository(Path(__file__).resolve().parents[1] / "상장법인목록.xls")

    results = repository.search("삼성전자")

    assert results
    assert results[0].symbol == "005930"
    assert results[0].name == "삼성전자"


def test_stock_listing_search_matches_symbol_prefix() -> None:
    repository = StockListingRepository(Path(__file__).resolve().parents[1] / "상장법인목록.xls")

    results = repository.search("00593")

    assert results
    assert results[0].symbol == "005930"
