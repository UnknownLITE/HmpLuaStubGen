base_url = "https://happinessmp.net/"

lua_types = {
    "nil",
    "boolean",
    "number",
    "string",
    "userdata",
    "function",
    "thread",
    "table",
    "any",  # LuaCATS
    "events",  # alias
}

aliases = {
    "int": "integer",
    "uint": "integer",
    "float": "number",
    "char": "string",
    "bool": "boolean",
    "void": "nil",
    "list": "any[]",
    # natives
    "char*": "string",
    "float*": "number",
    "void*": "table",
}

# these types will be replaced instead of getting an alias,
# as they contain symbols not allowed for an alias name
type_map = {"float&": "number"}

all_aliases = aliases.copy()
all_aliases.update(type_map)

arg_names = {
    "boolean": "bool",
    "integer": "int",
    "number": "float",
    "char": "str",
    "char*": "str",
    "float*": "float",
    "float&": "float",
    "void*": "table",
}
