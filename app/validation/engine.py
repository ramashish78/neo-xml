from pathlib import Path

from lxml import etree

ASSETS = Path(__file__).resolve().parent / "assets"
PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


def default_schema_bytes() -> bytes:
    return (ASSETS / "default.xsd").read_bytes()


def default_brex_bytes() -> bytes:
    return (ASSETS / "default.brex.xml").read_bytes()


def _finding(rule_id: str, location: str, message: str) -> dict:
    return {"rule_id": rule_id, "location": location, "message": message}


def run_validation(
    xml_bytes: bytes,
    schema_bytes: bytes,
    brex_bytes: bytes | None,
    ste_words: list[str] | None,
    known_icns: set[str],
) -> dict:
    checks = []
    errors = []
    warnings = []

    if b"<!DOCTYPE" in xml_bytes.upper() or b"<!ENTITY" in xml_bytes.upper():
        errors.append(_finding("XML-DOCTYPE", "1", "DOCTYPE and entities are not allowed"))
        checks.append({"name": "XML Schema", "status": "failed", "detail": "Unsafe XML declaration"})
        return _result(checks, errors, warnings)

    try:
        doc = etree.fromstring(xml_bytes, PARSER)
    except etree.XMLSyntaxError as exc:
        errors.append(_finding("XML-WELLFORMED", str(getattr(exc, "lineno", "")), "XML is not well-formed"))
        checks.append({"name": "XML Schema", "status": "failed", "detail": "XML is not well-formed"})
        for name in ("BREX", "CALS", "Applicability", "STE", "References"):
            checks.append({"name": name, "status": "skipped", "detail": "XML is not well-formed"})
        return _result(checks, errors, warnings)

    _check_schema(doc, schema_bytes, checks, errors)
    _check_brex(doc, brex_bytes, checks, errors, warnings)
    _check_cals(doc, checks, errors)
    _check_applicability(doc, checks, errors)
    _check_ste(doc, ste_words, checks, warnings)
    _check_references(doc, known_icns, checks, errors)
    return _result(checks, errors, warnings)


def _result(checks, errors, warnings) -> dict:
    return {
        "status": "failed" if errors else "passed",
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def _check_schema(doc, schema_bytes: bytes, checks: list, errors: list) -> None:
    try:
        schema_doc = etree.fromstring(schema_bytes, PARSER)
        schema = etree.XMLSchema(schema_doc)
    except (etree.XMLSyntaxError, etree.XMLSchemaParseError):
        errors.append(_finding("XSD-LOAD", "schema", "Schema file could not be loaded"))
        checks.append({"name": "XML Schema", "status": "failed", "detail": "Schema file could not be loaded"})
        return
    if schema.validate(doc):
        checks.append({"name": "XML Schema", "status": "passed", "detail": "Schema valid"})
        return
    for entry in schema.error_log:
        errors.append(_finding("XSD", f"line {entry.line}", entry.message))
    checks.append({"name": "XML Schema", "status": "failed", "detail": "Schema errors"})


def _check_brex(doc, brex_bytes: bytes | None, checks: list, errors: list, warnings: list) -> None:
    if not brex_bytes:
        warnings.append(_finding("BREX-MISSING", "", "BREX file is not configured"))
        checks.append({"name": "BREX", "status": "not_configured", "detail": "BREX file is not configured"})
        return
    try:
        brex = etree.fromstring(brex_bytes, PARSER)
    except etree.XMLSyntaxError:
        errors.append(_finding("BREX-LOAD", "brex", "BREX file is not valid XML"))
        checks.append({"name": "BREX", "status": "failed", "detail": "BREX file is not valid XML"})
        return
    rules = brex.xpath("//rule[@id]")
    if not rules:
        checks.append({"name": "BREX", "status": "passed", "detail": "No BREX rules"})
        return
    failed = False
    for rule in rules:
        rule_id = rule.get("id")
        xpath = rule.get("xpath")
        message = rule.get("message") or "BREX rule failed"
        if not xpath:
            warnings.append(_finding(rule_id, "", "BREX rule has no xpath"))
            continue
        try:
            found = doc.xpath(xpath)
        except etree.XPathError:
            warnings.append(_finding(rule_id, xpath, "BREX xpath is invalid"))
            continue
        if not found:
            failed = True
            errors.append(_finding(rule_id, xpath, message))
    checks.append(
        {
            "name": "BREX",
            "status": "failed" if failed else "passed",
            "detail": f"{len(rules)} rules",
        }
    )


def _check_cals(doc, checks: list, errors: list) -> None:
    tables = doc.xpath("//table")
    if not tables:
        checks.append({"name": "CALS", "status": "skipped", "detail": "No tables"})
        return
    failed = False
    for index, table in enumerate(tables, start=1):
        tgroup = table.find("tgroup")
        tbody = None if tgroup is None else tgroup.find("tbody")
        if tgroup is None or tbody is None:
            failed = True
            errors.append(
                _finding("CALS-TABLE", f"table[{index}]", "CALS table requires tgroup and tbody")
            )
    checks.append({"name": "CALS", "status": "failed" if failed else "passed", "detail": f"{len(tables)} tables"})


def _check_applicability(doc, checks: list, errors: list) -> None:
    nodes = doc.xpath("//applic")
    if not nodes:
        checks.append({"name": "Applicability", "status": "skipped", "detail": "No applicability expression"})
        return
    failed = False
    for index, node in enumerate(nodes, start=1):
        text = "".join(node.itertext()).strip()
        if not text and len(node) == 0:
            failed = True
            errors.append(_finding("APPLIC-EMPTY", f"applic[{index}]", "Applicability expression is empty"))
    checks.append(
        {"name": "Applicability", "status": "failed" if failed else "passed", "detail": f"{len(nodes)} expressions"}
    )


def _check_ste(doc, ste_words: list[str] | None, checks: list, warnings: list) -> None:
    if not ste_words:
        checks.append({"name": "STE", "status": "not_configured", "detail": "STE word list is not configured"})
        return
    allowed = {word.strip().lower() for word in ste_words if word.strip()}
    unknown = []
    for node in doc.xpath("//text()"):
        for raw in str(node).split():
            word = "".join(ch for ch in raw.lower() if ch.isalpha())
            if word and word not in allowed and word not in unknown:
                unknown.append(word)
    for word in unknown:
        warnings.append(_finding("STE-WORD", word, "Word is not in the STE list"))
    checks.append(
        {
            "name": "STE",
            "status": "passed" if not unknown else "warnings",
            "detail": f"{len(unknown)} unknown words",
        }
    )


def _check_references(doc, known_icns: set[str], checks: list, errors: list) -> None:
    ids = set(doc.xpath("//@id"))
    failed = False
    for node in doc.xpath("//ref[@target]"):
        target = node.get("target")
        if target not in ids:
            failed = True
            line = getattr(node, "sourceline", "") or ""
            errors.append(_finding("REF-MISSING", f"line {line}", f"Missing reference target {target}"))
    for node in doc.xpath("//graphic[@icn]"):
        icn = node.get("icn")
        if icn not in known_icns:
            failed = True
            errors.append(_finding("REF-ICN", icn or "", "Graphic ICN was not found"))
    checks.append({"name": "References", "status": "failed" if failed else "passed", "detail": "References checked"})
