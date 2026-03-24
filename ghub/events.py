from dataclasses import dataclass
from typing import List


@dataclass
class HookEvent:
    key: str
    label: str
    short: str


SUPPORTED: List[HookEvent] = [
    HookEvent("push",         "Code",                  "p"),
    HookEvent("issues",       "Issues",                "i"),
    HookEvent("pull_request", "Pull requests",         "pr"),
    HookEvent("gollum",       "Wikis",                 "g"),
    HookEvent("repository",   "Settings",              "rep"),
    HookEvent("meta",         "Webhooks and services", "mt"),
    HookEvent("deploy_key",   "Deploy keys",           "dk"),
    HookEvent("member",       "Collaboration invites", "m"),
    HookEvent("fork",         "Forks",                 "f"),
    HookEvent("star",         "Stars",                 "s"),
]

SHORT_TO_KEY = {e.short: e.key for e in SUPPORTED}
KEY_TO_SHORT = {e.key: e.short for e in SUPPORTED}
