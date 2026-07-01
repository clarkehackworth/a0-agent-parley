"""Determine whether shell commands are permitted for an incoming chat message."""


def commands_restriction(cfg: dict, message: str) -> str:
    """Return a prompt line blocking commands, or '' if commands are allowed.

    Rules:
      enable_commands=false → always blocked.
      enable_commands=true, password set → blocked unless password appears in message.
      enable_commands=true, no password → allowed.
    """
    if not cfg.get("enable_commands", False):
        return (
            "IMPORTANT: Shell/system commands are disabled for chat-triggered requests. "
            "Do not execute any shell, terminal, or system commands."
        )
    password = (cfg.get("commands_password") or "").strip()
    if password and password not in message:
        return (
            "IMPORTANT: Shell/system commands require the correct password in the message. "
            "Do not execute any shell, terminal, or system commands for this request."
        )
    return ""


if __name__ == "__main__":
    assert commands_restriction({"enable_commands": False}, "run ls") != ""
    assert commands_restriction({"enable_commands": True, "commands_password": ""}, "hi") == ""
    assert commands_restriction({"enable_commands": True, "commands_password": "secret"}, "hi") != ""
    assert commands_restriction({"enable_commands": True, "commands_password": "secret"}, "secret: run ls") == ""
    print("ok commands_policy")
