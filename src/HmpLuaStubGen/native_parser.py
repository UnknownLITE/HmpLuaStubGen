import re
from pathlib import Path
from urllib.parse import urljoin

from HmpLuaStubGen.common import arg_names
from HmpLuaStubGen.models import ParamInfo, MethodInfo, ReturnValue

base_url = "https://github.com/HappinessMP/natives/blob/master/"
TYPE_INFO_RE = re.compile(
    r"^- *\*{2}(?P<type>[^*]+?\*?):?\*{2} *(?:(?P<name>\S+)(?: +(?P<description>.*))?)?$"
)


def parse_arguments(reader) -> tuple[str, dict[str, ParamInfo]]:
    params: dict[str, ParamInfo] = {}
    num_types: dict[str, int] = {}  # count the number of params with same type

    while line := reader.readline():
        if line.startswith("#"):
            break

        m = TYPE_INFO_RE.match(line)
        if not m or not m.string.strip():
            continue
        groupdict = m.groupdict()
        param_name = groupdict["name"] or ""
        param_type = str(groupdict["type"])
        param_desc = groupdict["description"] or ""
        if param_desc.startswith("(") and param_desc.endswith(")"):
            param_desc = param_desc[1:-1]

        if not param_name:
            n = num_types.get(param_type, 1)
            t = arg_names.get(param_type, param_type)
            param_name = f"{t}{n}"
            num_types[param_type] = n + 1

        if param_type in ("scrVector&", "Vector3", "Vector3*"):
            param_type = "number"
            if param_name:
                param_name += "_"
            params[param_name + "x"] = ParamInfo(
                type=param_type, description=param_desc
            )
            params[param_name + "y"] = ParamInfo(
                type=param_type, description=param_desc
            )
            params[param_name + "z"] = ParamInfo(
                type=param_type, description=param_desc
            )
        else:
            params[param_name] = ParamInfo(type=param_type, description=param_desc)

    return line, params


def parse_results(reader) -> tuple[str, list[ReturnValue]]:
    results: list[ReturnValue] = []

    while line := reader.readline():
        if line.startswith("#"):
            break

        m = TYPE_INFO_RE.match(line)
        if not m or not m.string.strip():
            continue
        groupdict = m.groupdict()
        ret_name = groupdict["name"] or ""
        ret_type = str(groupdict["type"])

        if ret_type.startswith("Vector3"):
            ret_type = "number"
            if ret_name:
                ret_name += "_"
            results.append(ReturnValue(name=ret_name + "x", type=ret_type))
            results.append(ReturnValue(name=ret_name + "y", type=ret_type))
            results.append(ReturnValue(name=ret_name + "z", type=ret_type))
        else:
            results.append(ReturnValue(name=ret_name, type=ret_type))

    return line, results


def parse_native(filepath: Path):
    filepath = Path(filepath)
    method = MethodInfo()

    with open(filepath) as f:
        line = f.readline()
        while True:
            if not line:
                break
            line = line.strip()
            if line.lower() == "### arguments":
                line, params = parse_arguments(f)
                method.params = params
            elif line.lower() == "### results":
                line, results = parse_results(f)
                method.returns = results
            elif line.lower() == "## description":
                method.description = f.read().strip()
                line = ""  # nothing to read, we read all of it
            else:
                line = f.readline()

    full_url = urljoin(base_url, "/".join(filepath.parts[-2:]))
    method.doc_link = full_url
    return method


if __name__ == "__main__":
    from pprint import pprint

    # pprint(parse_native("../../docs/natives/PATH/GetClosestCarNodeFavourDirection.md"))
    pprint(parse_native("../../docs/natives/HUD/AddPointToGpsRaceTrack.md"))
