from __future__ import annotations

import getpass

from app import ADMIN_CONFIG_FILE, hash_password, json_dumps, now_iso


def main() -> int:
    username = input("管理员账号（直接回车使用 admin）：").strip() or "admin"
    password = getpass.getpass("新密码：").strip()
    confirm = getpass.getpass("再次输入新密码：").strip()
    if not password:
        print("密码不能为空。")
        return 1
    if password != confirm:
        print("两次输入的密码不一致。")
        return 1

    config = {
        "username": username,
        "password_hash": hash_password(password),
        "updated_at": now_iso(),
    }
    ADMIN_CONFIG_FILE.write_text(json_dumps(config), encoding="utf-8")
    print(f"管理员账号已更新：{username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
