#!/usr/bin/env python3
"""user-report.py — produce a simple user report by parsing /etc/passwd
Usage: python3 user-report.py
"""

import pwd


def get_users():
    users = []
    for p in pwd.getpwall():
        users.append({
            'name': p.pw_name,
            'uid': p.pw_uid,
            'home': p.pw_dir,
            'shell': p.pw_shell,
        })
    return users


if __name__ == '__main__':
    for u in get_users():
        print(f"{u['uid']:5d} {u['name']:20s} {u['home']:30s} {u['shell']}")
