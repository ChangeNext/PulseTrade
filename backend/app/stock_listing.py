from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


@dataclass(frozen=True)
class ListedStock:
    symbol: str
    name: str
    market: str
    sector: str = ""
    product: str = ""


class ListingTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_cell = False
        self._cell_chunks: list[str] = []
        self._current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"td", "th"}:
            self._in_cell = True
            self._cell_chunks = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._in_cell:
            text = " ".join("".join(self._cell_chunks).split())
            self._current_row.append(text)
            self._in_cell = False
            self._cell_chunks = []
        elif tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = []


class StockListingRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._stocks: list[ListedStock] | None = None
        self._mtime_ns: int | None = None

    def all(self) -> list[ListedStock]:
        stat = self.path.stat()
        if self._stocks is None or self._mtime_ns != stat.st_mtime_ns:
            self._stocks = self._load()
            self._mtime_ns = stat.st_mtime_ns
        return self._stocks

    def search(self, query: str, limit: int = 20) -> list[ListedStock]:
        normalized = query.strip().lower()
        if not normalized:
            return []
        exact: list[ListedStock] = []
        prefix: list[ListedStock] = []
        partial: list[ListedStock] = []
        for stock in self.all():
            symbol = stock.symbol.lower()
            name = stock.name.lower()
            if normalized == symbol or normalized == name:
                exact.append(stock)
            elif symbol.startswith(normalized) or name.startswith(normalized):
                prefix.append(stock)
            elif normalized in symbol or normalized in name or normalized in stock.market.lower():
                partial.append(stock)
        return (exact + prefix + partial)[:limit]

    def _load(self) -> list[ListedStock]:
        parser = ListingTableParser()
        parser.feed(self.path.read_text(encoding="euc-kr", errors="replace"))
        stocks: list[ListedStock] = []
        seen: set[str] = set()
        for row in parser.rows:
            if len(row) < 3 or row[0] == "회사명":
                continue
            symbol = row[2].strip()
            if len(symbol) != 6 or not symbol.isdigit() or symbol in seen:
                continue
            stocks.append(
                ListedStock(
                    name=row[0],
                    market=row[1],
                    symbol=symbol,
                    sector=row[3] if len(row) > 3 else "",
                    product=row[4] if len(row) > 4 else "",
                )
            )
            seen.add(symbol)
        return stocks
