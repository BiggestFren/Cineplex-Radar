"""Prepare a bind-mounted Unraid state directory, then drop root permanently."""

from __future__ import annotations

import os
import pwd


def main() -> None:
    account = pwd.getpwnam("radar")
    state = "/state"
    os.makedirs(state, exist_ok=True)
    for root, directories, files in os.walk(state):
        os.chown(root, account.pw_uid, account.pw_gid)
        for name in directories:
            os.chown(os.path.join(root, name), account.pw_uid, account.pw_gid)
        for name in files:
            os.chown(os.path.join(root, name), account.pw_uid, account.pw_gid)
    os.setgroups([])
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.execvp(
        "uvicorn",
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    )


if __name__ == "__main__":
    main()
