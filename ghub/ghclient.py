import aiohttp

GH_API = "https://api.github.com"


class GhApiError(Exception):
    def __init__(self, status: int, message: str = ""):
        self.status  = status
        self.message = message
        super().__init__(f"GitHub API error {status}: {message}")


class GhApi:
    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(self, method: str, path: str, **kwargs):
        url = f"{GH_API}{path}"
        async with aiohttp.ClientSession(headers=self._headers) as sess:
            async with sess.request(method, url, **kwargs) as resp:
                if resp.status == 204:
                    return {}
                data = await resp.json(content_type=None)
                if resp.status >= 400:
                    msg = data.get("message", "") if isinstance(data, dict) else str(data)
                    raise GhApiError(resp.status, msg)
                return data

    async def get_scopes(self) -> list:
        url = f"{GH_API}/user"
        async with aiohttp.ClientSession(headers=self._headers) as sess:
            async with sess.get(url) as resp:
                raw = resp.headers.get("X-OAuth-Scopes", "")
                return [s.strip() for s in raw.split(",") if s.strip()]

    async def has_scope(self, scope: str) -> bool:
        scopes = await self.get_scopes()
        return scope in scopes

    async def get(self, path: str, params: dict = None):
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: dict = None):
        return await self._request("POST", path, json=json)

    async def patch(self, path: str, json: dict = None):
        return await self._request("PATCH", path, json=json)

    async def delete(self, path: str):
        return await self._request("DELETE", path)

    async def put(self, path: str, json: dict = None):
        return await self._request("PUT", path, json=json)

    async def get_me(self) -> dict:
        return await self.get("/user")

    async def get_repo(self, full_name: str) -> dict:
        return await self.get(f"/repos/{full_name}")

    async def get_repo_by_id(self, repo_id: int) -> dict:
        return await self.get(f"/repositories/{repo_id}")

    async def list_repos(self, page: int = 1, per_page: int = 5) -> tuple:
        data = await self.get("/user/repos", params={
            "sort":      "updated",
            "direction": "desc",
            "per_page":  per_page,
            "page":      page,
        })
        return data

    async def create_hook(self, owner: str, repo: str, url: str,
                          secret: str, events: list) -> dict:
        return await self.post(f"/repos/{owner}/{repo}/hooks", json={
            "name":   "web",
            "active": True,
            "events": events,
            "config": {
                "url":          url,
                "content_type": "json",
                "secret":       secret,
            },
        })

    async def get_hook(self, owner: str, repo: str, hook_id: int) -> dict:
        return await self.get(f"/repos/{owner}/{repo}/hooks/{hook_id}")

    async def edit_hook(self, owner: str, repo: str, hook_id: int,
                        events: list, hook_url: str, secret: str) -> dict:
        return await self.patch(f"/repos/{owner}/{repo}/hooks/{hook_id}", json={
            "active": True,
            "events": events,
            "config": {
                "url":          hook_url,
                "content_type": "json",
                "secret":       secret,
            },
        })

    async def delete_hook(self, owner: str, repo: str, hook_id: int):
        return await self.delete(f"/repos/{owner}/{repo}/hooks/{hook_id}")

    async def close_issue(self, owner: str, repo: str, number: int):
        return await self.patch(f"/repos/{owner}/{repo}/issues/{number}",
                                json={"state": "closed"})

    async def reopen_issue(self, owner: str, repo: str, number: int):
        return await self.patch(f"/repos/{owner}/{repo}/issues/{number}",
                                json={"state": "open"})

    async def approve_pr(self, owner: str, repo: str, number: int):
        return await self.post(f"/repos/{owner}/{repo}/pulls/{number}/reviews",
                               json={"event": "APPROVE"})

    async def close_pr(self, owner: str, repo: str, number: int):
        return await self.patch(f"/repos/{owner}/{repo}/pulls/{number}",
                                json={"state": "closed"})

    async def create_repo(self, name: str, description: str = "", private: bool = False) -> dict:
        return await self.post("/user/repos", json={
            "name":        name,
            "description": description,
            "private":     private,
            "auto_init":   False,
        })

    async def delete_repo(self, owner: str, repo: str):
        return await self.delete(f"/repos/{owner}/{repo}")

    async def update_repo(self, owner: str, repo: str, **kwargs) -> dict:
        return await self.patch(f"/repos/{owner}/{repo}", json=kwargs)

    async def rename_repo_gh(self, owner: str, repo: str, new_name: str) -> dict:
        return await self.patch(f"/repos/{owner}/{repo}", json={"name": new_name})

    async def get_content_safe(self, owner: str, repo: str, path: str) -> dict:
        try:
            return await self.get(f"/repos/{owner}/{repo}/contents/{path}")
        except GhApiError as e:
            if e.status == 404:
                return {}
            raise

    async def put_file(self, owner: str, repo: str, path: str,
                       content_b64: str, message: str, sha: str = None) -> dict:
        payload = {
            "message": message,
            "content": content_b64,
        }
        if sha:
            payload["sha"] = sha
        return await self.put(f"/repos/{owner}/{repo}/contents/{path}", json=payload)