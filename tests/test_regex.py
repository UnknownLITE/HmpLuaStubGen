from pytest import mark

from HmpLuaStubGen.function_parser import SIGNATURE_RE, PARAM_RE


@mark.parametrize(
    "code, does_match, groupdict",
    [
        (
            "scriptInit()",
            True,
            {
                "returns": None,
                "class": None,
                "name": "scriptInit",
                "params": "",
            },
        ),
        (
            "Chat.Clear()",
            True,
            {"returns": None, "class": "Chat", "name": "Clear", "params": ""},
        ),
        (
            "Chat.BroadcastMessage(string message)",
            True,
            {
                "returns": None,
                "class": "Chat",
                "name": "BroadcastMessage",
                "params": "string message",
            },
        ),
        (
            "Chat.SendMessage(int serverID, string message)",
            True,
            {
                "returns": None,
                "class": "Chat",
                "name": "SendMessage",
                "params": "int serverID, string message",
            },
        ),
        (
            "bool inputActive = Chat.IsInputActive()",
            True,
            {
                "returns": "bool inputActive",
                "class": "Chat",
                "name": "IsInputActive",
                "params": "",
            },
        ),
        (
            "int status, string data = HTTP.Get(string url)", # shortened version of HTTP.Request just for testing
            True,
            {
                "returns": "int status, string data",
                "class": "HTTP",
                "name": "Get",
                "params": "string url",
            },
        ),
        ("test", False, None),
    ],
)
def test_signature_re(code: str, does_match: bool, groupdict):
    match = SIGNATURE_RE.match(code)
    if not code.strip():
        assert not does_match
        return
    match_found = bool(match)
    assert match_found == does_match

    if match_found:
        assert groupdict == match.groupdict()


@mark.parametrize(
    "code, does_match, groupdict",
    [
        (
            "string message",
            True,
            {"tag": None, "type": "string", "name": "message"},
        ),
        (
            "[optional] function callback",
            True,
            {"tag": "[optional]", "type": "function", "name": "callback"},
        ),
        (
            "[server only] int serverID",
            True,
            {"tag": "[server only]", "type": "int", "name": "serverID"},
        ),
        (
            "[client only] int serverID",
            True,
            {"tag": "[client only]", "type": "int", "name": "serverID"},
        ),
        (
            "any ...",
            True,
            {"tag": None, "type": "any", "name": "..."},
        ),
        ("", False, None),
    ],
)
def test_param_re(code: str, does_match: bool, groupdict):
    match = PARAM_RE.match(code)
    match_found = bool(match)
    assert match_found == does_match, match.groupdict()

    if match_found:
        assert groupdict == match.groupdict()
