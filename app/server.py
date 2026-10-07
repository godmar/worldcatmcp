"""MCP tool definitions for the WorldCat Search API v2.

Every tool is a thin, read-only wrapper around one WorldCat endpoint. Tool
parameters use snake_case and are mapped to WorldCat's camelCase query
parameters; responses are WorldCat's JSON passed through unchanged.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field

from . import __version__
from .config import settings
from .worldcat import WorldCatClient, WorldCatError

INSTRUCTIONS = """\
Read-only access to WorldCat, OCLC's global union catalog of library holdings.

Typical workflow:
1. `search_bibs` to find records (WorldCat query syntax, e.g. `ti:moby dick AND au:melville`,
   `bn:9780439136358` for ISBN, `kw:` for keyword). Results include OCLC numbers.
2. `get_bib` with an OCLC number for the full record.
3. `get_other_editions` to list other editions/formats of a work.
4. `get_holdings` / `get_holdings_summary` to see which libraries hold an item
   (filter by country, US state such as `US-VA`, OCLC symbol, or proximity).
OCLC symbols identify libraries (e.g. `VPI` = Virginia Tech).
Paging: `offset` is 0-based, `limit` is at most 50.
"""

client = WorldCatClient(settings)

mcp = MCPServer(
    "worldcat-search",
    title="WorldCat Search",
    instructions=INSTRUCTIONS,
    version=__version__,
    log_level=settings.log_level,
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True,
                            openWorldHint=True)

# ---------------------------------------------------------------------------
# Shared parameter types
# ---------------------------------------------------------------------------

ItemType = Literal[
    "archv", "artchapter", "audiobook", "book", "compfile", "encyc", "game", "image",
    "intmm", "jrnl", "kit", "map", "msscr", "music", "news", "object", "snd", "toy",
    "video", "vis", "web",
]

OclcNumber = Annotated[int, Field(description="OCLC number of the bibliographic record, e.g. 41266045", gt=0)]
OclcNumberOpt = Annotated[int | None, Field(description="OCLC number of the item, e.g. 41266045")]
Isbn = Annotated[str | None, Field(description="ISBN of the item (alternative to oclc_number)")]
Issn = Annotated[str | None, Field(description="ISSN of the item (alternative to oclc_number)")]
Offset = Annotated[int, Field(description="0-based start position for paging", ge=0)]
Limit = Annotated[int, Field(description="Maximum number of records to return (1-50)", ge=1, le=50)]
ItemTypes = Annotated[list[ItemType] | None, Field(description="Restrict to general formats (up to 5), e.g. ['book']", max_length=5)]
ItemSubTypes = Annotated[list[str] | None, Field(
    description="Restrict to specific formats (up to 5), e.g. ['book-printbook', 'book-digital', "
    "'audiobook-cd', 'video-dvd', 'music-cd', 'jrnl-digital']", max_length=5)]
HeldBySymbol = Annotated[list[str] | None, Field(description="OCLC institution symbols (up to 5), e.g. ['VPI']", max_length=5)]
HeldByInstitutionId = Annotated[list[int] | None, Field(description="OCLC registry IDs of institutions (up to 5)", max_length=5)]
HeldByGroup = Annotated[str | None, Field(description="OCLC group symbol, e.g. 'ASRL'")]
Lat = Annotated[float | None, Field(description="Latitude for proximity filtering/sorting", ge=-90, le=90)]
Lon = Annotated[float | None, Field(description="Longitude for proximity filtering/sorting", ge=-180, le=180)]
Distance = Annotated[int | None, Field(description="Search radius around lat/lon", ge=1)]
Unit = Annotated[Literal["M", "K"] | None, Field(description="Distance unit: M (miles) or K (kilometers)")]
PreferredLanguage = Annotated[str | None, Field(description="3-letter MARC language code to prefer descriptions in, e.g. 'eng'")]
ExtraParams = Annotated[dict[str, str] | None, Field(
    description="Additional raw WorldCat query parameters (camelCase names as in the WorldCat "
    "Search API v2 docs) for options not exposed above")]


async def _call(path: str, params: dict[str, Any], extra: dict[str, str] | None = None) -> dict[str, Any]:
    if extra:
        params = {**params, **extra}
    try:
        result = await client.get(path, params)
    except WorldCatError as e:
        # e.message already carries the problem detail of a JSON error body;
        # include a raw (non-JSON) body verbatim.
        detail = f" -- {e.detail}" if isinstance(e.detail, str) and e.detail else ""
        raise ToolError(f"WorldCat API error {e.status}: {e.message}{detail}") from e
    except Exception as e:  # network errors, timeouts, ...
        raise ToolError(f"Error contacting WorldCat: {type(e).__name__}: {e}") from e
    return result if isinstance(result, dict) else {"result": result}


def _require_item(oclc_number: int | None, isbn: str | None, issn: str | None) -> None:
    if not (oclc_number or isbn or issn):
        raise ToolError("Provide one of oclc_number, isbn, or issn.")


# ---------------------------------------------------------------------------
# Bibliographic resources
# ---------------------------------------------------------------------------

@mcp.tool(annotations=READ_ONLY)
async def search_bibs(
    q: Annotated[str, Field(description=(
        "WorldCat query. Keyword or fielded search, e.g. 'kw:climate change', "
        "'ti:\"the hobbit\" AND au:tolkien', 'bn:9780439136358' (ISBN), 'su:machine learning', "
        "'(au:gazihan OR au:womacka) AND kw:java'. Common indexes: kw (keyword), ti (title), "
        "au (author), su (subject), bn (ISBN), in (ISSN), no (OCLC number), pb (publisher)."))],
    detail: Annotated[Literal["brief", "full"], Field(description=(
        "'brief' (default) returns compact records; 'full' returns detailed bibliographic data "
        "(much larger)."))] = "brief",
    item_type: ItemTypes = None,
    item_sub_type: ItemSubTypes = None,
    in_language: Annotated[list[str] | None, Field(description="Languages (MARC codes, up to 5), e.g. ['eng', 'fre']", max_length=5)] = None,
    date_published: Annotated[list[str] | None, Field(description="Publication years or ranges (up to 5), e.g. ['2000-2010'] or ['1990', '1991']", max_length=5)] = None,
    held_by_symbol: HeldBySymbol = None,
    held_by_group: HeldByGroup = None,
    held_by_institution_id: HeldByInstitutionId = None,
    audience: Annotated[Literal["juv", "nonJuv"] | None, Field(description="Juvenile or non-juvenile audience")] = None,
    content: Annotated[list[Literal["fic", "nonFic", "bio"]] | None, Field(description="Content type (fiction, non-fiction, biography)")] = None,
    genre: Annotated[str | None, Field(description="Genre, e.g. 'fiction'")] = None,
    topic: Annotated[str | None, Field(description="OCLC Conspectus division code, e.g. '34000000'")] = None,
    subtopic: Annotated[str | None, Field(description="OCLC Conspectus category code, e.g. '34932000'")] = None,
    dewey_number: Annotated[list[str] | None, Field(description="Dewey classification numbers (up to 5)", max_length=5)] = None,
    open_access: Annotated[bool | None, Field(description="Only open access content")] = None,
    peer_reviewed: Annotated[bool | None, Field(description="Only peer reviewed content")] = None,
    facets: Annotated[list[Literal[
        "subject", "creator", "datePublished", "genre", "itemType", "itemSubTypeBrief",
        "itemSubType", "language", "topic", "subtopic", "content", "audience", "databases",
    ]] | None, Field(description="Facets to include counts for in the response")] = None,
    group_related_editions: Annotated[bool | None, Field(description="Group editions of the same work (FRBR)")] = None,
    group_variant_records: Annotated[bool | None, Field(description="Group variant records of the same edition")] = None,
    show_holding_indicators: Annotated[bool | None, Field(description="Include holdings indicators (whether your institution / nearby libraries hold the item)")] = None,
    preferred_language: PreferredLanguage = None,
    lat: Lat = None,
    lon: Lon = None,
    distance: Distance = None,
    unit: Unit = None,
    order_by: Annotated[Literal[
        "library", "recency", "bestMatch", "creator", "publicationDateAsc",
        "publicationDateDesc", "mostWidelyHeld", "title",
    ] | None, Field(description="Sort order (default bestMatch)")] = None,
    offset: Offset = 0,
    limit: Limit = 10,
    extra_params: ExtraParams = None,
) -> dict[str, Any]:
    """Search WorldCat bibliographic records (books, journals, media, ...).

    Returns `numberOfRecords` and a list of records (`briefRecords` or `bibRecords`), each with
    its `oclcNumber`, title, creator, date, format, etc.
    """
    path = "/brief-bibs" if detail == "brief" else "/bibs"
    return await _call(path, {
        "q": q,
        "itemType": item_type,
        "itemSubType": item_sub_type,
        "inLanguage": in_language,
        "datePublished": date_published,
        "heldBySymbol": held_by_symbol,
        "heldByGroup": held_by_group,
        "heldByInstitutionID": held_by_institution_id,
        "audience": audience,
        "content": content,
        "genre": genre,
        "topic": topic,
        "subtopic": subtopic,
        "deweyNumber": dewey_number,
        "openAccess": open_access,
        "peerReviewed": peer_reviewed,
        "facets": facets,
        "groupRelatedEditions": group_related_editions,
        "groupVariantRecords": group_variant_records,
        "showHoldingsIndicators": show_holding_indicators,
        "preferredLanguage": preferred_language,
        "lat": lat,
        "lon": lon,
        "distance": distance,
        "unit": unit,
        "orderBy": order_by,
        "offset": offset,
        "limit": limit,
    }, extra_params)


@mcp.tool(annotations=READ_ONLY)
async def get_bib(
    oclc_number: OclcNumber,
    detail: Annotated[Literal["brief", "full"], Field(description=(
        "'full' (default) returns detailed bibliographic data (identifiers, subjects, "
        "contents notes, classification, ...); 'brief' returns a compact record."))] = "full",
    show_holding_indicators: Annotated[bool | None, Field(description="(brief only) include holdings indicators")] = None,
) -> dict[str, Any]:
    """Retrieve a single WorldCat bibliographic record by OCLC number."""
    if detail == "brief":
        return await _call(f"/brief-bibs/{oclc_number}",
                           {"showHoldingsIndicators": show_holding_indicators})
    return await _call(f"/bibs/{oclc_number}", {})


@mcp.tool(annotations=READ_ONLY)
async def get_other_editions(
    oclc_number: OclcNumber,
    item_type: ItemTypes = None,
    item_sub_type: ItemSubTypes = None,
    in_language: Annotated[list[str] | None, Field(description="Languages (MARC codes, up to 5)", max_length=5)] = None,
    date_published: Annotated[list[str] | None, Field(description="Publication years or ranges (up to 5)", max_length=5)] = None,
    held_by_symbol: HeldBySymbol = None,
    held_by_group: HeldByGroup = None,
    creator: Annotated[list[str] | None, Field(description="Creator names to filter to (up to 5)", max_length=5)] = None,
    group_variant_records: Annotated[bool | None, Field(description="Group variant records of the same edition")] = None,
    preferred_language: PreferredLanguage = None,
    order_by: Annotated[Literal[
        "library", "recency", "bestMatch", "creator", "publicationDateAsc",
        "publicationDateDesc", "language", "mostWidelyHeld", "title",
    ] | None, Field(description="Sort order (default publicationDateDesc)")] = None,
    offset: Offset = 0,
    limit: Limit = 10,
    extra_params: ExtraParams = None,
) -> dict[str, Any]:
    """List other editions (translations, formats, printings) of the work an OCLC number belongs to."""
    return await _call(f"/brief-bibs/{oclc_number}/other-editions", {
        "itemType": item_type,
        "itemSubType": item_sub_type,
        "inLanguage": in_language,
        "datePublished": date_published,
        "heldBySymbol": held_by_symbol,
        "heldByGroup": held_by_group,
        "creator": creator,
        "groupVariantRecords": group_variant_records,
        "preferredLanguage": preferred_language,
        "orderBy": order_by,
        "offset": offset,
        "limit": limit,
    }, extra_params)


# ---------------------------------------------------------------------------
# Member holdings
# ---------------------------------------------------------------------------

HeldInCountry = Annotated[str | None, Field(description="ISO 3166-1 alpha-2 country code, e.g. 'US'")]
HeldInState = Annotated[str | None, Field(description="ISO 3166-2 state/province code, e.g. 'US-VA'")]
AllEditions = Annotated[bool | None, Field(description="Include holdings of all editions of the work")]
LibraryType = Annotated[list[Literal["PUBLIC", "ALL"]] | None, Field(description="Restrict to public libraries")]


@mcp.tool(annotations=READ_ONLY)
async def get_holdings(
    oclc_number: OclcNumberOpt = None,
    isbn: Isbn = None,
    issn: Issn = None,
    held_in_country: HeldInCountry = None,
    held_in_state: HeldInState = None,
    held_by_symbol: HeldBySymbol = None,
    held_by_institution_id: HeldByInstitutionId = None,
    held_by_library_type: LibraryType = None,
    holdings_all_editions: AllEditions = None,
    holdings_all_variant_records: Annotated[bool | None, Field(description="Include holdings across variant records of the same edition")] = None,
    item_type: ItemTypes = None,
    item_sub_type: ItemSubTypes = None,
    lat: Lat = None,
    lon: Lon = None,
    distance: Distance = None,
    unit: Unit = None,
    number_nearest_holdings: Annotated[int | None, Field(description="With lat/lon: number of nearest holdings to show even outside the radius", ge=1, le=200)] = None,
    offset: Offset = 0,
    limit: Limit = 10,
    extra_params: ExtraParams = None,
) -> dict[str, Any]:
    """Find which member libraries hold a known item (by OCLC number, ISBN, or ISSN).

    Returns the bibliographic record with a list of institutions (name, OCLC symbol,
    registry ID, location, distance when lat/lon is given).
    """
    _require_item(oclc_number, isbn, issn)
    return await _call("/bibs-holdings", {
        "oclcNumber": oclc_number,
        "isbn": isbn,
        "issn": issn,
        "heldInCountry": held_in_country,
        "heldInState": held_in_state,
        "heldBySymbol": held_by_symbol,
        "heldByInstitutionID": held_by_institution_id,
        "heldByLibraryType": held_by_library_type,
        "holdingsAllEditions": holdings_all_editions,
        "holdingsAllVariantRecords": holdings_all_variant_records,
        "itemType": item_type,
        "itemSubType": item_sub_type,
        "lat": lat,
        "lon": lon,
        "distance": distance,
        "unit": unit,
        "numberNearestHoldings": number_nearest_holdings,
        "offset": offset,
        "limit": limit,
    }, extra_params)


@mcp.tool(annotations=READ_ONLY)
async def get_holdings_summary(
    oclc_number: OclcNumberOpt = None,
    isbn: Isbn = None,
    issn: Issn = None,
    held_in_country: HeldInCountry = None,
    held_in_state: HeldInState = None,
    held_by_group: HeldByGroup = None,
    held_by_symbol: HeldBySymbol = None,
    held_by_institution_id: HeldByInstitutionId = None,
    held_by_library_type: LibraryType = None,
    holdings_all_editions: AllEditions = None,
    holdings_all_variant_records: Annotated[bool | None, Field(description="Include holdings across variant records of the same edition")] = None,
    lat: Lat = None,
    lon: Lon = None,
    distance: Distance = None,
    unit: Unit = None,
    extra_params: ExtraParams = None,
) -> dict[str, Any]:
    """Get summary holding counts for a known item (total holdings, holdings in your
    state/country, whether a given institution holds it, ...)."""
    _require_item(oclc_number, isbn, issn)
    return await _call("/bibs-summary-holdings", {
        "oclcNumber": oclc_number,
        "isbn": isbn,
        "issn": issn,
        "heldInCountry": held_in_country,
        "heldInState": held_in_state,
        "heldByGroup": held_by_group,
        "heldBySymbol": held_by_symbol,
        "heldByInstitutionID": held_by_institution_id,
        "heldByLibraryType": held_by_library_type,
        "holdingsAllEditions": holdings_all_editions,
        "holdingsAllVariantRecords": holdings_all_variant_records,
        "lat": lat,
        "lon": lon,
        "distance": distance,
        "unit": unit,
    }, extra_params)


@mcp.tool(annotations=READ_ONLY)
async def get_detailed_holdings(
    oclc_number: OclcNumberOpt = None,
    isbn: Isbn = None,
    issn: Issn = None,
    held_by_symbol: HeldBySymbol = None,
    held_by_group: HeldByGroup = None,
    held_by_institution_id: HeldByInstitutionId = None,
    item_type: ItemTypes = None,
    item_sub_type: ItemSubTypes = None,
    extra_params: ExtraParams = None,
) -> dict[str, Any]:
    """Get detailed holdings (local holdings records: locations, call numbers, copies,
    summary statements for serials) of specific institutions for a known item.

    Restrict with held_by_symbol / held_by_institution_id / held_by_group.
    """
    _require_item(oclc_number, isbn, issn)
    return await _call("/bibs-detailed-holdings", {
        "oclcNumber": oclc_number,
        "isbn": isbn,
        "issn": issn,
        "heldBySymbol": held_by_symbol,
        "heldByGroup": held_by_group,
        "heldByInstitutionID": held_by_institution_id,
        "itemType": item_type,
        "itemSubType": item_sub_type,
    }, extra_params)


@mcp.tool(annotations=READ_ONLY)
async def get_retained_holdings(
    oclc_number: OclcNumberOpt = None,
    isbn: Isbn = None,
    issn: Issn = None,
    held_by_group: HeldByGroup = None,
    held_in_state: HeldInState = None,
    item_type: ItemTypes = None,
    item_sub_type: ItemSubTypes = None,
    offset: Offset = 0,
    limit: Limit = 10,
    extra_params: ExtraParams = None,
) -> dict[str, Any]:
    """Find member libraries that have a Shared Print retention commitment for a known item."""
    _require_item(oclc_number, isbn, issn)
    return await _call("/bibs-retained-holdings", {
        "oclcNumber": oclc_number,
        "isbn": isbn,
        "issn": issn,
        "heldByGroup": held_by_group,
        "heldInState": held_in_state,
        "itemType": item_type,
        "itemSubType": item_sub_type,
        "offset": offset,
        "limit": limit,
    }, extra_params)


# ---------------------------------------------------------------------------
# Local holdings resources (LHRs)
# ---------------------------------------------------------------------------

@mcp.tool(annotations=READ_ONLY)
async def search_my_holdings(
    oclc_number: OclcNumberOpt = None,
    barcode: Annotated[str | None, Field(description="Item barcode")] = None,
    order_by: Annotated[Literal["commitmentExpirationDate", "location", "oclcSymbol"] | None,
                        Field(description="Sort order")] = None,
    offset: Offset = 0,
    limit: Limit = 10,
) -> dict[str, Any]:
    """Search the local holdings records (LHRs) of the institution this server's API key
    belongs to, by OCLC number or barcode."""
    if not (oclc_number or barcode):
        raise ToolError("Provide oclc_number or barcode.")
    return await _call("/my-holdings", {
        "oclcNumber": oclc_number,
        "barcode": barcode,
        "orderBy": order_by,
        "offset": offset,
        "limit": limit,
    })


@mcp.tool(annotations=READ_ONLY)
async def get_my_holding(
    control_number: Annotated[str, Field(description="LHR control number, e.g. '238374600'")],
) -> dict[str, Any]:
    """Retrieve one local holdings record (LHR) of this server's institution by control number."""
    return await _call(f"/my-holdings/{control_number}", {})


@mcp.tool(annotations=READ_ONLY)
async def search_retained_holdings(
    oclc_number: OclcNumberOpt = None,
    barcode: Annotated[str | None, Field(description="Item barcode")] = None,
    held_by_symbol: HeldBySymbol = None,
    held_by_institution_id: HeldByInstitutionId = None,
    sp_program: Annotated[str | None, Field(description="Shared print program, e.g. 'WEST'")] = None,
    order_by: Annotated[Literal["commitmentExpirationDate", "location", "oclcSymbol"] | None,
                        Field(description="Sort order")] = None,
    offset: Offset = 0,
    limit: Limit = 10,
) -> dict[str, Any]:
    """Search shared-print local holdings records (retention commitments, with expiration
    dates and locations) by OCLC number or barcode.

    WorldCat requires at least one of held_by_symbol, held_by_institution_id, or sp_program.
    """
    if not (oclc_number or barcode):
        raise ToolError("Provide oclc_number or barcode.")
    if not (held_by_symbol or held_by_institution_id or sp_program):
        raise ToolError("Provide at least one of held_by_symbol, held_by_institution_id, or sp_program.")
    return await _call("/retained-holdings", {
        "oclcNumber": oclc_number,
        "barcode": barcode,
        "heldBySymbol": held_by_symbol,
        "heldByInstitutionID": held_by_institution_id,
        "spProgram": sp_program,
        "orderBy": order_by,
        "offset": offset,
        "limit": limit,
    })
