import base64
import os
import re
import tempfile
import zipfile
import asyncio

from telethon import events
from telethon.tl.types import User

import config
from bot import Irene
from cache.ttlcache import TTLCache
from crypto.vault import unseal
from database.store import DataStore
from ghub.ghclient import GhApi, GhApiError
from helpers import LOGGER, send_message, edit_message, SmartButtons, new_task, clean_download
from helpers.guard import ban_check

_prefixes = "".join(re.escape(p) for p in config.COMMAND_PREFIXES)
_create_pat = re.compile(rf"^[{_prefixes}]create(?:\s|$)", re.IGNORECASE)

_sessions = TTLCache()

_STEP_NAME = "name"
_STEP_DESC = "desc"
_STEP_ZIP  = "zip"


async def _get_api(tg_id: int):
    acc = await DataStore.get().get_account(tg_id)
    if not acc or not acc.token_enc:
        return None
    try:
        return GhApi(unseal(acc.token_enc))
    except Exception:
        return None


def _cancel_btn():
    sb = SmartButtons()
    sb.button("❌ Cancel", callback_data="cr:cancel")
    return sb.build_menu(1)


def _repo_btn(url):
    sb = SmartButtons()
    sb.button("📥 Repository", url=url)
    return sb.build_menu(1)


@Irene.on(events.NewMessage(pattern=_create_pat))
@new_task
async def create_cmd(e):
    chat = await e.get_chat()
    if not isinstance(chat, User):
        await send_message(e.chat_id, "Use in private chat")
        return

    api = await _get_api(e.sender_id)
    if not api:
        await send_message(e.chat_id, "**❌Please connect your github acc first**", parse_mode="md")
        return

    m = await send_message(
        e.chat_id,
        "**Send Me The Name Of The Repo**\n**Click Button To Cancell ❌**",
        parse_mode="md",
        buttons=_cancel_btn()
    )

    await _sessions.put(e.sender_id, {
        "step": _STEP_NAME,
        "msg":  m.id,
        "name": None,
        "desc": None,
        "full": None,
        "url":  None
    }, ttl=600)


@Irene.on(events.CallbackQuery(pattern=b"cr:cancel"))
@ban_check
async def cancel_cb(e):
    s = await _sessions.get(e.sender_id)
    if not s:
        return

    await _sessions.delete(e.sender_id)

    if s.get("step") == _STEP_ZIP and s.get("full"):
        api = await _get_api(e.sender_id)
        if api:
            try:
                o, r = s["full"].split("/", 1)
                await api.delete_repo(o, r)
            except Exception:
                pass
        await e.edit("**Procedure cancelled ❌ repo deleted**", parse_mode="md")
    else:
        await e.edit("**Cancelled, repo creating procedure**", parse_mode="md")


@Irene.on(events.NewMessage())
@new_task
async def router(e):
    if not e.is_private:
        return

    s = await _sessions.get(e.sender_id)
    if not s:
        return

    step = s["step"]

    if step == _STEP_NAME and e.text:
        name = e.text.strip()
        if not re.match(r"^[a-zA-Z0-9_.\-]+$", name):
            return

        s["name"] = name
        s["step"]  = _STEP_DESC

        await edit_message(
            e.chat_id,
            s["msg"],
            "**Repo Name Received Send Description**\n**Click Below Button To Cancel**",
            parse_mode="md",
            buttons=_cancel_btn()
        )

        await _sessions.put(e.sender_id, s, ttl=600)

    elif step == _STEP_DESC and e.text:
        s["desc"] = e.text.strip()

        wait = await send_message(e.chat_id, "**Creating repository....please wait..**", parse_mode="md")

        api = await _get_api(e.sender_id)
        try:
            repo = await api.create_repo(s["name"], s["desc"])
        except Exception as ex:
            LOGGER.error(f"create_repo failed: {ex}")
            await edit_message(e.chat_id, wait.id, "**❌Sorry Failed To Create Repository**", parse_mode="md")
            await _sessions.delete(e.sender_id)
            return

        s["full"] = repo["full_name"]
        s["url"]  = repo["html_url"]
        s["step"] = _STEP_ZIP
        s["msg"]  = wait.id

        await edit_message(
            e.chat_id,
            wait.id,
            "**Repo Created Now Send Files As Zip**\n**Files Must Be Under 100 MB**\n**Click Below Buttons To Cancel**",
            parse_mode="md",
            buttons=_cancel_btn()
        )

        await _sessions.put(e.sender_id, s, ttl=1800)

    elif step == _STEP_ZIP and e.document:
        status = await send_message(e.chat_id, "**Extracting Files Zip....For Upload**", parse_mode="md")

        tmp = tempfile.mkdtemp()
        zp  = os.path.join(tmp, "f.zip")

        try:
            await Irene.download_media(e.message, zp)

            if not zipfile.is_zipfile(zp):
                raise Exception("not a zip")

            files = []
            with zipfile.ZipFile(zp) as z:
                for n in z.namelist():
                    if n.endswith("/"):
                        continue
                    with z.open(n) as f:
                        files.append((n, f.read()))

            names = [f[0] for f in files]
            top   = set(n.split("/")[0] for n in names if "/" in n)

            prefix = ""
            if len(top) == 1:
                p = list(top)[0] + "/"
                if all(n.startswith(p) for n in names):
                    prefix = p

            clean_download(zp)
            zp = None

            await edit_message(e.chat_id, status.id, "**Uploading To Github Repository **", parse_mode="md")

            api = await _get_api(e.sender_id)
            o, r = s["full"].split("/", 1)

            for path, data in files:
                path = path.strip().replace("\\", "/")

                if prefix and path.startswith(prefix):
                    path = path[len(prefix):]

                if not path:
                    continue

                b64      = base64.b64encode(data).decode()
                existing = await api.get_content_safe(o, r, path)
                sha      = existing.get("sha") if isinstance(existing, dict) else None

                await api.put_file(o, r, path, b64, f"Add {path}", sha)
                await asyncio.sleep(0.15)

            await edit_message(
                e.chat_id,
                status.id,
                f"**✅ Repo Created Successfully!**\n**━━━━━━━━━━━━━━━━**\nYour Repo: [{s['name']}]({s['url']})\n\nYour repo is now live at **github **sever officialy. Share it with anyone — they can use it **independently.**",
                parse_mode="md",
                buttons=_repo_btn(s["url"]),
                link_preview=False
            )

        except Exception as ex:
            LOGGER.error(f"upload fail: {ex}")
            await edit_message(e.chat_id, status.id, "**Sorry failed to upload to github**", parse_mode="md")

        finally:
            if zp and os.path.exists(zp):
                clean_download(zp)
            try:
                os.rmdir(tmp)
            except Exception:
                pass
            await _sessions.delete(e.sender_id)