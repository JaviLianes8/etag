"""Run the Python reference implementations on the seeded cases of oracle_fixture.py.

Each function needs its framework installed (pip install etag[oracle]); none of them is
a dependency of etag. The modules are imported by name so the type check of etag does
not need them either.
"""

from __future__ import annotations

import importlib
from typing import Any


def _sorted(tags: Any) -> list[str | None]:
    # Werkzeug 3.1.9 stores the empty tag "" as None, so None has to sort too.
    return sorted(tags, key=lambda tag: (tag is not None, tag or ""))


def run_werkzeug(case: dict[str, Any]) -> dict[str, Any]:
    """werkzeug.http.parse_etags and is_resource_modified (If-None-Match, GET)."""
    http = importlib.import_module("werkzeug.http")
    parsed = []
    for field in case["fields"]:
        tags = http.parse_etags(field)
        every = tags.as_set(include_weak=True)
        weak = _sorted(tag for tag in every if tags.is_weak(tag))
        parsed.append({"star": tags.star_tag, "strong": _sorted(tags.as_set()), "weak": weak})
    modified = []
    for method, current, _, none_match in case["scenarios"]:
        if method != "GET" or current is None or none_match is None:
            modified.append(None)
            continue
        environ = {"REQUEST_METHOD": "GET", "HTTP_IF_NONE_MATCH": none_match}
        modified.append(http.is_resource_modified(environ, etag=current))
    return {"parse_etags": parsed, "is_resource_modified": modified}


def run_django(case: dict[str, Any]) -> dict[str, Any]:
    """django.utils.http.parse_etags and django.utils.cache.get_conditional_response."""
    conf = importlib.import_module("django.conf")
    if not conf.settings.configured:
        conf.settings.configure(ALLOWED_HOSTS=["*"], USE_TZ=True)
        importlib.import_module("django").setup()
    http = importlib.import_module("django.utils.http")
    cache = importlib.import_module("django.utils.cache")
    response_type = importlib.import_module("django.http").HttpResponse
    factory = importlib.import_module("django.test").RequestFactory()
    parsed = [http.parse_etags(field) for field in case["fields"]]
    statuses = []
    for method, current, match, none_match in case["scenarios"]:
        headers = {}
        if match is not None:
            headers["HTTP_IF_MATCH"] = match
        if none_match is not None:
            headers["HTTP_IF_NONE_MATCH"] = none_match
        request = factory.generic(method, "/", **headers)
        answer = cache.get_conditional_response(request, etag=current, response=response_type())
        statuses.append(answer.status_code)
    return {"parse_etags": parsed, "get_conditional_response": statuses}


def run_aiohttp(case: dict[str, Any]) -> dict[str, Any]:
    """aiohttp's If-Match / If-None-Match parsing and its file response decision."""
    request = importlib.import_module("aiohttp.web_request").BaseRequest
    match_tags = importlib.import_module("aiohttp.web_fileresponse").FileResponse._etag_match

    def read(field: str | None) -> Any:
        tags = request._if_match_or_none_impl(field)
        return None if tags is None else [[tag.is_weak, tag.value] for tag in tags]

    parsed = [read(field) for field in case["fields"]]
    statuses: list[int | None] = []
    for method, current, match, none_match in case["scenarios"]:
        # aiohttp only serves strong tags of its own, and only for GET and HEAD.
        if method not in ("GET", "HEAD") or current is None or current.startswith("W/"):
            statuses.append(None)
            continue
        value = current[1:-1]
        ifmatch = request._if_match_or_none_impl(match)
        ifnonematch = request._if_match_or_none_impl(none_match)
        if ifmatch is not None and not match_tags(value, ifmatch, weak=False):
            statuses.append(412)
        elif ifnonematch is not None and match_tags(value, ifnonematch, weak=True):
            statuses.append(304)
        else:
            statuses.append(200)
    return {"parse": parsed, "file_response": statuses}


def run_starlette(case: dict[str, Any]) -> list[bool | None]:
    """starlette.staticfiles.StaticFiles.is_not_modified (If-None-Match, GET, strong tag)."""
    headers = importlib.import_module("starlette.datastructures").Headers
    files = importlib.import_module("starlette.staticfiles").StaticFiles(
        directory=".", check_dir=False
    )
    answers: list[bool | None] = []
    for method, current, _, none_match in case["scenarios"]:
        if method != "GET" or current is None or current.startswith("W/") or none_match is None:
            answers.append(None)
            continue
        response = headers(headers={"etag": current})
        answers.append(files.is_not_modified(response, headers(headers={"if-none-match": none_match})))
    return answers
