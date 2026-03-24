from typing import Optional, List

import motor.motor_asyncio

import config
from database.models import LinkedRepo, GhAccount


class DataStore:
    _instance = None

    def __init__(self):
        self._client   = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URI)
        self._db       = self._client[config.DB_NAME]
        self._accounts = self._db["gh_accounts"]
        self._repos    = self._db["linked_repos"]
        self._guards   = self._db["gh_guards"]
        self._security = self._db["gh_security"]
        self._reboot   = self._db["gh_reboot"]
        self._users    = self._db["gh_users"]

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def setup(self):
        await self._accounts.create_index("tg_id", unique=True)
        await self._repos.create_index([("chat_id", 1), ("name", 1)], unique=True)
        await self._guards.create_index("user_id", unique=True)
        await self._security.create_index("user_id", unique=True)
        await self._users.create_index([("user_id", 1), ("is_group", 1)], unique=True)
        await self._users.create_index("last_activity")

    async def save_token(self, tg_id: int, token_enc: str):
        await self._accounts.update_one(
            {"tg_id": tg_id},
            {"$set": {"tg_id": tg_id, "token_enc": token_enc}},
            upsert=True,
        )

    async def get_account(self, tg_id: int) -> Optional[GhAccount]:
        doc = await self._accounts.find_one({"tg_id": tg_id})
        if not doc:
            return None
        return GhAccount(tg_id=doc["tg_id"], token_enc=doc.get("token_enc", ""))

    async def clear_token(self, tg_id: int):
        await self._accounts.update_one({"tg_id": tg_id}, {"$set": {"token_enc": ""}})

    async def add_repo(self, chat_id: int, repo: LinkedRepo):
        await self._repos.update_one(
            {"chat_id": chat_id, "name": repo.name},
            {"$set": {"chat_id": chat_id, "name": repo.name, "hook_id": repo.hook_id}},
            upsert=True,
        )

    async def get_repo(self, chat_id: int, name: str) -> Optional[LinkedRepo]:
        doc = await self._repos.find_one({"chat_id": chat_id, "name": name})
        if not doc:
            return None
        return LinkedRepo(name=doc["name"], hook_id=doc.get("hook_id", 0),
                          peer_id=doc.get("peer_id", None))

    async def list_repos(self, chat_id: int) -> List[LinkedRepo]:
        out = []
        async for doc in self._repos.find({"chat_id": chat_id}):
            out.append(LinkedRepo(name=doc["name"], hook_id=doc.get("hook_id", 0),
                                  peer_id=doc.get("peer_id", None)))
        return out

    async def set_repo_peer(self, chat_id: int, name: str, peer_id: int):
        await self._repos.update_one(
            {"chat_id": chat_id, "name": name},
            {"$set": {"peer_id": peer_id}},
        )

    async def find_chats_by_repo(self, name: str) -> List[dict]:
        out = []
        async for doc in self._repos.find({"name": name}, {"chat_id": 1, "peer_id": 1}):
            out.append({"chat_id": doc["chat_id"], "peer_id": doc.get("peer_id")})
        return out

    async def remove_repo(self, chat_id: int, name: str):
        await self._repos.delete_one({"chat_id": chat_id, "name": name})



    async def rename_repo(self, old_name: str, new_name: str):
        await self._repos.update_many({"name": old_name}, {"$set": {"name": new_name}})

    async def get_guards(self) -> List[dict]:
        return await self._guards.find({}).to_list(None)

    async def add_guard(self, user_id: int, data: dict):
        await self._guards.update_one({"user_id": user_id}, {"$set": data}, upsert=True)

    async def remove_guard(self, user_id: int) -> bool:
        result = await self._guards.delete_one({"user_id": user_id})
        return result.deleted_count > 0

    async def is_banned(self, user_id: int) -> bool:
        return bool(await self._security.find_one({"user_id": user_id}))

    async def ban_user(self, user_id: int, data: dict):
        await self._security.insert_one(data)

    async def unban_user(self, user_id: int) -> bool:
        result = await self._security.delete_one({"user_id": user_id})
        return result.deleted_count > 0

    async def get_banlist(self) -> List[dict]:
        return await self._security.find({}).to_list(None)

    async def save_reboot(self, chat_id: int, msg_id: int):
        await self._reboot.delete_many({})
        await self._reboot.insert_one({"chat_id": chat_id, "msg_id": msg_id})

    async def get_reboot(self) -> Optional[dict]:
        return await self._reboot.find_one({})

    async def clear_reboot(self):
        await self._reboot.delete_many({})

    async def track_user(self, user_id: int, is_group: bool = False):
        from datetime import datetime
        now = datetime.utcnow()
        await self._users.update_one(
            {"user_id": user_id, "is_group": is_group},
            {"$set": {"user_id": user_id, "last_activity": now, "is_group": is_group},
             "$inc": {"activity_count": 1}},
            upsert=True,
        )

    async def count_users(self, query: dict = None) -> int:
        return await self._users.count_documents(query or {})

    async def top_users(self, limit: int = 27) -> List[dict]:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        return await self._users.find(
            {"is_group": False, "last_activity": {"$gte": now - timedelta(days=1)}}
        ).sort("activity_count", -1).to_list(limit)

    async def all_user_ids(self) -> List[dict]:
        return await self._users.find({}, {"user_id": 1, "is_group": 1}).to_list(None)