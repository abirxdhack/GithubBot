from dataclasses import dataclass


@dataclass
class LinkedRepo:
    name: str
    hook_id: int
    peer_id: int = None


@dataclass
class GhAccount:
    tg_id: int
    token_enc: str = ""


@dataclass
class MsgContext:
    owner: str
    repo: str
    num: int
    kind: str