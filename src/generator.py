from collections import OrderedDict

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from function_parser import parse
from io import StringIO
from pathlib import Path

from models import AsyncMethodInfo, Category, MethodInfo, ParamInfo, ReturnValue

aliases = {
    "int": "integer",
    "uint": "integer",
    "float": "number",
    "char": "string",
    "bool": "boolean",
    "void": "nil",
    "list": "any[]",
}


def convert_returns_to_params(returns: list[ReturnValue]) -> dict[str, ParamInfo]:
    if not returns:
        return {}

    params: dict[str, ParamInfo] = OrderedDict()

    for ret in returns:
        if not ret.name:
            continue
        params[ret.name] = ParamInfo(type=ret.type)

    return params


def _write_single_stub(
    writer: StringIO,
    method_name: str,
    method: MethodInfo,
    params: dict,
    category_label: str | None,
    overloads: list[str] | None = None,
) -> None:
    writer.write("--- ")
    writer.write("\n--- ".join(method.description.split("\n")))
    writer.write(f"\n---\n--- [Open Docs 🔗]({method.doc_link})")

    if category_label:
        writer.write(f" | {category_label}")
    writer.write("\n")

    if isinstance(method, AsyncMethodInfo):
        writer.write("---@async\n")

    for param_name, param_info in params.items():
        writer.write(f"---@param {param_name}")
        if param_info.is_optional:
            writer.write("?")
        writer.write(f" {param_info.type}\n")

    for ret in method.returns:
        writer.write(f"---@return {ret.type} {ret.name}\n")

    if overloads:
        for overload in overloads:
            writer.write(f"---@overload {overload}\n")

    writer.write(f"function {method_name}(")
    writer.write(", ".join(params.keys()))
    writer.write(") end\n\n")


def write_method_stub(
    writer: StringIO,
    method_name: str,
    method: MethodInfo,
    overloads: list[str] | None = None,
) -> None:
    # Only shared methods can have categorized params; server/client-only methods shouldn't
    has_categorized_params = method.category == Category.SHARED and any(
        p.category != Category.SHARED for p in method.params.values()
    )

    if has_categorized_params:
        # Split params into three variants
        client_params = OrderedDict()
        server_params = OrderedDict()

        for k, v in method.params.items():
            if v.category != Category.SERVER:  # shared + client
                client_params[k] = v
            if v.category != Category.CLIENT:  # shared + server
                server_params[k] = v

        for variant_params, label in (
            (client_params, "**Client-side Only**"),
            (server_params, "**Server-side Only**"),
        ):
            _write_single_stub(
                writer, method_name, method, variant_params, label, overloads
            )
    else:
        category_label = None
        if method.category == Category.CLIENT:
            category_label = "**Client-side Only**"
        elif method.category == Category.SERVER:
            category_label = "**Server-side Only**"

        _write_single_stub(
            writer, method_name, method, method.params, category_label, overloads
        )


def preprocess_description(method: MethodInfo, class_name: str, symbols: set[str]):
    desc = BeautifulSoup(method.description, "html.parser")

    for a in desc.find_all("a"):
        href = a.get("href", "")
        assert isinstance(href, str)

        if href.startswith("#"):
            key = href[1:].lower()
            if key in symbols:
                a.replace_with(f"{class_name}.{a.get_text()}")

    method.description = desc.decode().replace(
        "&gt;", ">"
    )  # else block quotes will break


def handle_async_method(method: AsyncMethodInfo, methods: dict[str, MethodInfo]):
    if method.async_of is None:
        return

    callback_param_info = method.params.get("callback") or method.params.get(
        "callbackFunc"
    )
    if callback_param_info is None:
        return

    sync_method = methods.get(method.async_of)
    if sync_method is None:
        return

    callback_params = convert_returns_to_params(sync_method.returns)
    params_str = ", ".join(
        f"{param_name}: {param.type}" for param_name, param in callback_params.items()
    )
    callback_param_info.type = f"fun({params_str})"


def generate_function_stub(writer: StringIO, filepath: Path):
    class_name, methods = parse(filepath)

    writer.write(f"--#region {class_name}\n\n")
    writer.write(f"---@class {class_name}\n")
    writer.write(f"{class_name} = {{}}\n\n")

    symbols = set(map(str.lower, methods.keys()))

    for method_name, method in methods.items():
        full_method_name = f"{class_name}.{method_name}"

        preprocess_description(method, class_name, symbols)

        if isinstance(method, AsyncMethodInfo) and method.async_of is not None:
            handle_async_method(method, methods)

        write_method_stub(writer, full_method_name, method)

    writer.write("--#endregion\n\n\n")


def generate_overloads(
    full_method_name: str, method: MethodInfo, events: dict[str, MethodInfo]
):

    def generate_callback_func_sig(params: dict[str, ParamInfo]):
        return ", ".join(
            f"{n}{'?' if p.is_optional else ''}: {p.type}" for n, p in params.items()
        )

    if full_method_name == "Events.Subscribe":
        overloads = []
        for event_name, event_info in events.items():
            callback_func_sig = generate_callback_func_sig(event_info.params)
            overloads.append(
                f"fun(name: '{event_name}', callbackFunc: fun({callback_func_sig}), isRemoteAllowed?: bool)"
            )
        return overloads

    name_param = method.params.get("name")

    if name_param is not None:
        name_param.type = "events"
    return None


def simplify_description(description: str) -> str:
    desc = BeautifulSoup(description, "html.parser")
    description = ""

    for element in desc:
        if isinstance(element, NavigableString):
            description += element.replace("\n\n", "\n")
            continue
        assert isinstance(element, Tag)

        if element.name == "p":
            for c in element.children:
                if isinstance(c, Tag) and c.name == "br":
                    c.replace_with(" ")

        text = element.get_text()

        if element.name == "code":
            description += f"`{text}`"
            continue

        if element.name == "strong":
            description += f"**{text}**"
            continue

        description += text

    return description.replace("\n", "").replace("> ❕ **INFO**:", "")


def generate_events_stub(
    writer: StringIO, functions_filepath: Path, events_filepath: Path
):
    class_name, methods = parse(functions_filepath)
    _, events = parse(events_filepath)

    writer.write("---@alias events\n")
    for event_name, event in events.items():
        desc = simplify_description(event.description)
        writer.write(f'---| "{event_name}" # {desc}\n')
    writer.write("\n")

    writer.write(f"--#region {class_name}\n\n")
    writer.write(f"---@class {class_name}\n")
    writer.write(f"{class_name} = {{}}\n\n")

    symbols = set(map(str.lower, methods.keys()))

    for method_name, method in methods.items():
        full_method_name = f"{class_name}.{method_name}"

        preprocess_description(method, class_name, symbols)

        # if isinstance(method, AsyncMethodInfo) and method.async_of is not None:
        #     handle_async_method(method, methods)

        write_method_stub(
            writer,
            full_method_name,
            method,
            overloads=generate_overloads(full_method_name, method, events),
        )

    writer.write("--#endregion\n\n\n")


def generate_stubs(docs_folder: Path, dist_folder: Path):
    dist_folder.mkdir(parents=True, exist_ok=True)
    with open(dist_folder / "aliases.d.lua", "w") as f:
        f.write("---@meta\n\n")
        for alias_name, alias_type in aliases.items():
            f.write(f"---@alias {alias_name} {alias_type}\n")
        f.write("\n")

    writer = StringIO()
    writer.write("---@meta\n\n")

    for file in docs_folder.joinpath("scripting/functions").iterdir():
        if file.stem.lower() in ("game", "events"):
            continue  # we have to handle these separately
        generate_function_stub(writer, file)

    with open(dist_folder / "functions.d.lua", "w", encoding="utf8") as f:
        f.write(writer.getvalue())

    with open(dist_folder / "events.d.lua", "w", encoding="utf8") as f:
        f.write("---@meta\n\n")
        generate_events_stub(
            f,
            docs_folder / "scripting/functions/events.html",
            docs_folder / "scripting/events.html",
        )


if __name__ == "__main__":
    docs_folder = Path("../docs")
    dist_folder = Path("../dist")
    generate_stubs(docs_folder, dist_folder)
