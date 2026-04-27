import re
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin
from collections import OrderedDict

from bs4 import BeautifulSoup
from bs4.element import Tag

from common import base_url
from models import AsyncMethodInfo, Category, MethodInfo, ParamInfo, ReturnValue

SIGNATURE_RE = re.compile(
    r"^(?:(?P<returns>.*?)\s*=)?\s*"  # optional return types
    r"(?:(?P<class>\w+)\.)?(?P<name>\w+)"  # Class.MethodName
    r"\((?P<params>[^)]*)\)$"  # (params)
)

PARAM_RE = re.compile(
    r"^(?P<tag>\[[\w\s]*])?\s*"  # tag, i.e. [optional] or [server only]. Docs doesn't make use of multiple tags on a single param yet
    r"(?P<type>\w+)\s*"  # param type
    r"(?P<name>.*?)\s*$"  # param name
)


def parse_codeblock(code: str) -> tuple[str, dict[str, ParamInfo], list[ReturnValue]]:
    code = code.strip()

    match = SIGNATURE_RE.match(code)
    assert match

    groups = match.groupdict()

    return_str = groups["returns"]
    if return_str:
        return_type = []
        for item in return_str.split(","):
            t, name = item.split()
            return_type.append(ReturnValue(type=t, name=name))
    else:
        return_type = [ReturnValue(type="nil")]

    method_name = str(groups["name"])

    param_str = str(groups["params"])
    params: dict[str, ParamInfo] = OrderedDict()
    if param_str:
        for param in param_str.split(", "):
            is_optional, category = False, Category.SHARED

            match = PARAM_RE.match(param)
            assert match

            groups = match.groupdict()

            tag = groups["tag"]
            if tag:
                tag = tag.strip().lower()
                if tag == "[optional]":
                    is_optional = True

                if tag == "[server only]":
                    category = Category.SERVER
                elif tag == "[client only]":  # A guess, not present in docs yet
                    category = Category.CLIENT

            param_type = groups["type"]
            param_name = groups["name"]

            if param_name == "function":
                param_name = "func"

            params[param_name] = ParamInfo(
                type=param_type, is_optional=is_optional, category=category
            )

    return method_name, params, return_type


def process_admonition(admonition_div: Tag) -> str:
    output = StringIO()

    children = tuple(
        child for child in admonition_div.children if isinstance(child, Tag)
    )
    admonition_type = children[0].get_text().upper()

    if admonition_type == "NOTE":
        output.write("> ℹ️ **Note**: \n")

    elif admonition_type == "TIP":
        output.write("> 💡 **Tip**: \n")

    elif admonition_type == "INFO":
        output.write("> ❕ **INFO**: \n")

    elif admonition_type == "WARNING":
        output.write("> ⚠️ **Warning**: \n")

    elif admonition_type == "DANGER":
        output.write("> 🔥 **Danger**: \n")

    else:
        raise ValueError(f"Unknown admonition type {admonition_type}")

    admonition_content_div = children[1]
    admonition_content = admonition_content_div.children

    output.write("".join(map(str, admonition_content)))

    return output.getvalue()


def resolve_links(container: Tag, symbols: set[str]):
    for a in container.find_all("a"):
        href = a.get("href", "")
        assert isinstance(href, str)

        if not href.startswith("#"):
            continue

        key = href[1:].lower()

        if key in symbols:
            a.replace_with(a.get_text())


def parse_method_section(header: Tag):
    codeblocks = []
    description = StringIO()
    got_description = False

    for sibling in header.next_siblings:
        if not isinstance(sibling, Tag):
            continue

        if sibling.name == "hr":
            break

        if sibling.name == "p":
            if not got_description:
                description.write(sibling.get_text())
                description.write("\n")
                got_description = True
            else:
                for p_child in sibling.children:
                    if isinstance(p_child, Tag) and p_child.name == "code":
                        codeblocks.append(p_child)

        if sibling.name == "div":
            classes = sibling.attrs.get("class")

            if not (classes and "theme-admonition" in classes):
                continue

            # parse admonitions
            description.write(process_admonition(sibling))
            description.write("\n")
            description.write("\n")  # escape blockquote

    return codeblocks, description.getvalue().strip()


def convert_return_type_to_param(returns: list[ReturnValue]) -> dict[str, ParamInfo]:
    if not returns:
        return {}

    params: dict[str, ParamInfo] = OrderedDict()

    for ret in returns:
        if not ret.name:
            continue
        params[ret.name] = ParamInfo(type=ret.type)

    return params


def parse_methods(
    soup: BeautifulSoup, methods: dict[str, MethodInfo], doc_url: str
) -> None:
    for method_name, method_info in tuple(methods.items()):
        method_header = soup.find(id=method_name.lower())
        assert method_header is not None

        a_tag = method_header.find("a")
        assert a_tag is not None
        method_info.doc_link = urljoin(doc_url, str(a_tag.attrs["href"]))

        codeblocks, description = parse_method_section(method_header)

        method_info.description = description

        for codeblock in codeblocks:
            code = codeblock.get_text()

            if not code:
                continue

            meth_name, params, returns = parse_codeblock(code)

            if method_name == meth_name:
                method_info.params = params
                method_info.returns = returns

            async_index = meth_name.find("Async")
            is_async = async_index != -1

            if not is_async:
                continue

            if meth_name == method_name:
                sync_method_name = meth_name[:async_index]
                if methods.get(sync_method_name) is None:
                    continue
            else:
                sync_method_name = method_name

            if sync_method_name:  # convert the return type of sync version to parameter of the callback in async version
                methods[meth_name] = AsyncMethodInfo(
                    category=method_info.category,
                    description=method_info.description,
                    params=params,
                    returns=returns,
                    doc_link=method_info.doc_link,
                    async_of=sync_method_name,
                )


def parse_toc(soup):
    headers = soup.find_all("h2")

    methods: dict[str, MethodInfo] = {}

    for header in headers:
        category = header.attrs["id"].split("-", maxsplit=1)[0]
        if category not in ("shared", "client", "server"):
            continue
        category = Category(category)

        table = header.find_next_sibling("table")
        tbody = table.find_next("tbody")
        td_list: list[BeautifulSoup] = list(
            filter(lambda child: child.name == "td", tbody.descendants)
        )
        i = 0
        while i < len(td_list):
            methods[td_list[i].get_text()] = MethodInfo(category=category)
            i += 2

    return methods


def parse(filepath: Path | str) -> tuple[str, dict[str, MethodInfo]]:
    filepath = Path(filepath)
    assert isinstance(filepath, Path)

    with open(filepath, encoding="utf8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    doc_url = urljoin(base_url, filepath.as_posix().rsplit(".", maxsplit=1)[0])

    h1_tag = soup.find("h1")
    assert h1_tag is not None
    class_name = h1_tag.get_text()

    methods = parse_toc(soup)

    parse_methods(soup, methods, doc_url)

    return class_name, methods


if __name__ == "__main__":
    from pprint import pprint

    pprint(parse("../docs/scripting/functions/events.html"))
