import aiohttp

import config


def build_auth_url(state: str) -> str:
    return (
        "https://github.com/login/oauth/authorize"
        f"?client_id={config.GH_CLIENT_ID}"
        f"&scope=repo,delete_repo,admin:repo_hook,read:user"
        f"&state={state}"
        f"&redirect_uri={config.PUBLIC_URL}/auth/callback"
    )


async def exchange_code(code: str) -> str:
    async with aiohttp.ClientSession() as sess:
        async with sess.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id":     config.GH_CLIENT_ID,
                "client_secret": config.GH_CLIENT_SECRET,
                "code":          code,
            },
            headers={"Accept": "application/json"},
        ) as resp:
            resp.raise_for_status()
            data  = await resp.json(content_type=None)
            token = data.get("access_token", "")
            if not token:
                raise ValueError(f"GitHub returned no access_token: {data}")
            return token