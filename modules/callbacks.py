import asyncio
import html
import subprocess
import time
from datetime import datetime, timedelta

import psutil
from telethon import events
from telethon.errors import MessageNotModifiedError

import config
from bot import Irene
from core.start import get_start_text
from database.store import DataStore
from ghub.genbtn import (
    MENU_RESPONSES,
    build_start_buttons,
    build_main_menu_buttons,
    build_back_to_menu_button,
    build_back_to_start_button,
    build_about_buttons,
    build_fstats_buttons,
    build_stats_back_button,
    build_server_back_button,
    build_top_users_buttons,
    build_policy_terms_buttons,
    build_policy_back_button,
)
from helpers.donate import DONATION_TEXT, get_donation_buttons
from helpers.guard import ban_check
from helpers.logger import LOGGER


async def measure_network_speed():
    try:
        def run_speedtest():
            try:
                import speedtest
                st = speedtest.Speedtest()
                st.get_best_server()
                download_bps = st.download()
                upload_bps = st.upload()
                download_mbps = download_bps / 1_000_000
                upload_mbps = upload_bps / 1_000_000
                return f"{download_mbps:.2f} Mbps", f"{upload_mbps:.2f} Mbps"
            except Exception as e:
                return "Error", "Error"
        download_speed, upload_speed = await asyncio.to_thread(run_speedtest)
        if download_speed == "Error":
            return "N/A", "N/A"
        return download_speed, upload_speed
    except Exception as e:
        return "N/A", "N/A"


async def _safe_edit(event, text, parse_mode="html", buttons=None, link_preview=False):
    try:
        await event.edit(text, parse_mode=parse_mode, buttons=buttons, link_preview=link_preview)
    except MessageNotModifiedError:
        pass
    except Exception as e:
        LOGGER.error(f"_safe_edit error: {e}")
        try:
            await event.answer("Something went wrong.", alert=False)
        except Exception:
            pass


@Irene.on(events.CallbackQuery())
@ban_check
async def handle_all_callbacks(event):
    data = event.data.decode("utf-8") if isinstance(event.data, bytes) else event.data

    try:
        from modules.middleware import track
        await track(event.sender_id, event.chat_id)
    except Exception:
        pass

    try:
        if data == "back_to_start":
            sender     = await event.get_sender()
            first_name = getattr(sender, "first_name", "") or ""
            last_name  = getattr(sender, "last_name", "") or ""
            name       = f"{first_name} {last_name}".strip() or "there"
            await _safe_edit(
                event,
                get_start_text(name),
                parse_mode="markdown",
                buttons=build_start_buttons(),
                link_preview=False,
            )

        elif data == "main_menu":
            await _safe_edit(
                event,
                "<b>Here are the GitHub Notify Bot Options: 👇</b>",
                buttons=build_main_menu_buttons(),
            )

        elif data == "back_to_main_menu":
            await _safe_edit(
                event,
                "<b>Here are the GitHub Notify Bot Options: 👇</b>",
                buttons=build_main_menu_buttons(),
            )

        elif data == "about_me":
            text = (
                "<b>ℹ️ About GitHub Notify Bot</b>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Name:</b> GitHub Notify Bot ⚙️\n"
                "<b>Version:</b> v1.0 (Beta) 🛠\n\n"
                "<b>Development Team:</b>\n"
                "- <b>Creator:</b> <a href='https://t.me/ISmartCoder'>Abir Arafat Chawdhury 🇧🇩</a>\n\n"
                "<b>Technical Stacks:</b>\n"
                "- <b>Language:</b> Python 🐍\n"
                "- <b>Libraries:</b> Telethon, FastAPI, aiohttp 📚\n"
                "- <b>Database:</b> MongoDB 🗄\n"
                "- <b>Hosting:</b> VPS 🌐\n\n"
                "<b>About:</b> The all-in-one GitHub webhook bridge for Telegram — "
                "get instant notifications for every event on your repositories!"
            )
            await _safe_edit(event, text, buttons=build_about_buttons())

        elif data == "donate":
            await _safe_edit(
                event,
                DONATION_TEXT,
                buttons=get_donation_buttons(5),
                link_preview=False,
            )

        elif data == "gh_fstats":
            text = (
                "<b>🗒 GitHub Notify Statistics Menu 🔍</b>\n"
                "<b>━━━━━━━━━━━━━━━━━</b>\n"
                "Stay Updated With Real Time Insights....⚡️\n\n"
                "⊗ <b>Usage Report:</b> Get Full Usage Stats Of The Bot ⚙️\n"
                "⊗ <b>Top Users:</b> Get Top User's Leaderboard 🔥\n\n"
                "<b>━━━━━━━━━━━━━━━━━</b>\n"
                "<b>💡 Select an option and take control:</b>\n"
            )
            await _safe_edit(event, text, buttons=build_fstats_buttons())

        elif data == "gh_stats":
            store   = DataStore.get()
            now     = datetime.utcnow()
            daily   = await store.count_users({"is_group": False, "last_activity": {"$gte": now - timedelta(days=1)}})
            weekly  = await store.count_users({"is_group": False, "last_activity": {"$gte": now - timedelta(weeks=1)}})
            monthly = await store.count_users({"is_group": False, "last_activity": {"$gte": now - timedelta(days=30)}})
            yearly  = await store.count_users({"is_group": False, "last_activity": {"$gte": now - timedelta(days=365)}})
            total_users  = await store.count_users({"is_group": False})
            total_groups = await store.count_users({"is_group": True})
            text = (
                "<b>📊 GitHub Notify Bot Status ⇾ Report ✅</b>\n"
                "<b>━━━━━━━━━━━━━━━━</b>\n"
                "<b>Users & Groups Engagement:</b>\n"
                f"<b>1 Day:</b> {daily} users were active\n"
                f"<b>1 Week:</b> {weekly} users were active\n"
                f"<b>1 Month:</b> {monthly} users were active\n"
                f"<b>1 Year:</b> {yearly} users were active\n"
                f"<b>Total Connected Groups:</b> {total_groups}\n"
                "<b>━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Total Bot Users:</b> {total_users} ✅"
            )
            await _safe_edit(event, text, buttons=build_stats_back_button())

        elif data.startswith("top_users_"):
            page           = int(data.split("_")[-1])
            users_per_page = 9
            store          = DataStore.get()
            all_users      = await store.top_users(limit=1000)
            total_users    = len(all_users)
            total_pages    = max((total_users + users_per_page - 1) // users_per_page, 1)
            start_idx      = (page - 1) * users_per_page
            paginated      = all_users[start_idx:start_idx + users_per_page]

            lines = (
                f"<b>🏆 Top Users (Daily) — Page {page}/{total_pages}:</b>\n"
                "<b>━━━━━━━━━━━━━━━</b>\n"
            )
            for i, user in enumerate(paginated, start=start_idx + 1):
                uid = user["user_id"]
                try:
                    tg_user = await Irene.get_entity(uid)
                    first   = html.escape(tg_user.first_name or "")
                    last    = html.escape(getattr(tg_user, "last_name", "") or "")
                    full    = f"{first} {last}".strip() or f"User {uid}"
                except Exception:
                    full = f"User {uid}"
                rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔸"
                lines += (
                    f"{rank} <b>{i}.</b> "
                    f"<a href=\"tg://user?id={uid}\">{full}</a>\n"
                    f"<b> └ User ID:</b> <code>{uid}</code>\n\n"
                )
            if not paginated:
                lines += "<i>No active users found today.</i>\n"

            await _safe_edit(
                event, lines,
                parse_mode="html",
                buttons=build_top_users_buttons(page, total_pages),
                link_preview=False,
            )

        elif data == "gh_server":
            await event.answer("Fetching server stats...", alert=False)
            try:
                ping_out = subprocess.getoutput("ping -c 1 google.com")
                ping = ping_out.split("time=")[1].split()[0] + " ms" if "time=" in ping_out else "N/A"
            except Exception:
                ping = "N/A"

            download_speed, upload_speed = await measure_network_speed()
            disk = psutil.disk_usage("/")
            mem  = psutil.virtual_memory()
            cpu  = psutil.cpu_percent(interval=1)

            text = (
                "<b>⚙️ Server Status Report</b>\n"
                "<b>━━━━━━━━━━━━━━━</b>\n"
                "<b>🛜 Connectivity:</b>\n"
                f"<b>- Ping:</b> {ping}\n"
                "<b>- Status:</b> Online ✅\n"
                f"<b>- Download:</b> {download_speed}\n"
                f"<b>- Upload:</b> {upload_speed}\n\n"
                "<b>💾 Server Storage:</b>\n"
                f"<b>- Total:</b> {disk.total / (2**30):.2f} GB\n"
                f"<b>- Used:</b> {disk.used / (2**30):.2f} GB\n"
                f"<b>- Available:</b> {disk.free / (2**30):.2f} GB\n\n"
                "<b>🧠 Memory Usage:</b>\n"
                f"<b>- Total:</b> {mem.total / (2**30):.2f} GB\n"
                f"<b>- Used:</b> {mem.used / (2**30):.2f} GB\n"
                f"<b>- Available:</b> {mem.available / (2**30):.2f} GB\n\n"
                f"<b>🖥 CPU Usage:</b> {cpu}%"
            )
            await _safe_edit(event, text, buttons=build_server_back_button())

        elif data == "policy_terms":
            text = (
                "<b>📜 Policy & Terms Menu</b>\n\n"
                "At <b>GitHub Notify Bot ⚙️</b>, we prioritize your privacy and security. "
                "Review our <b>Privacy Policy</b> and <b>Terms & Conditions</b> before using the bot.\n\n"
                "🔹 <b>Privacy Policy</b>: Learn how we collect, use, and protect your data.\n"
                "🔹 <b>Terms & Conditions</b>: Understand the rules for using our services.\n\n"
                "✅ Staying informed helps you use <b>GitHub Notify Bot ⚙️</b> safely and responsibly.\n\n"
                "<b>💡 Choose an option below to proceed:</b>"
            )
            await _safe_edit(event, text, buttons=build_policy_terms_buttons())

        elif data == "privacy_policy":
            text = (
                "<b>📜 Privacy Policy for GitHub Notify Bot ⚙️</b>\n\n"
                "By using <b>GitHub Notify Bot ⚙️</b>, you agree to this privacy policy.\n\n"
                "<b>1. Information We Collect:</b>\n"
                "   - <b>Personal Information:</b> User ID and username for basic functionality.\n"
                "   - <b>GitHub Data:</b> Encrypted OAuth token, repo names, webhook IDs.\n"
                "   - <b>Usage Data:</b> Anonymous logs to improve our services.\n\n"
                "<b>2. How We Use Data:</b>\n"
                "   - <b>Service Delivery:</b> To deliver GitHub notifications and handle commands.\n"
                "   - <b>Security:</b> Tokens encrypted with AES-256-GCM before storage.\n\n"
                "<b>3. Third-Party Services:</b>\n"
                "   Only minimum required data is shared with GitHub APIs.\n\n"
                "<b>4. Data Security:</b>\n"
                "   Webhook payloads are processed in real-time and never stored permanently.\n\n"
                "<b>5. Your Rights:</b>\n"
                "   You may stop using the bot at any time. Use /logout to revoke your token.\n\n"
                "<i>We respect your privacy and aim to keep your data safe.</i>"
            )
            await _safe_edit(event, text, buttons=build_policy_back_button())

        elif data == "terms_conditions":
            text = (
                "<b>📜 Terms & Conditions for GitHub Notify Bot ⚙️</b>\n\n"
                "By using <b>GitHub Notify Bot ⚙️</b>, you accept these <b>Terms & Conditions</b>.\n\n"
                "<b>1. Usage Guidelines:</b>\n"
                "   - <b>Eligibility:</b> Must be 13 years of age or older.\n"
                "   - This bot fully complies with Telegram's "
                "<a href=\"https://telegram.org/tos/bot-developers\">Terms Of Service</a>.\n\n"
                "<b>2. Prohibited Actions:</b>\n"
                "   - Illegal and unauthorized usage is strictly forbidden.\n"
                "   - Spamming, abuse, or any kind of misuse is not tolerated.\n\n"
                "<b>3. Tools and Usage:</b>\n"
                "   - For personal and team use only.\n"
                "   - We do not support misuse, fraud, or any policy-violating behavior.\n\n"
                "<b>4. User Responsibility:</b>\n"
                "   - Users are responsible for how they use the bot.\n"
                "   - All activity must comply with Telegram and applicable laws.\n\n"
                "<b>5. Disclaimer:</b>\n"
                "   - No guarantee of uptime, accuracy, or data reliability.\n\n"
                "<b>6. Termination:</b>\n"
                "   - Violations may lead to user ban or service suspension without notice.\n\n"
                "<b>7. Contact:</b>\n"
                "   - For concerns, contact <a href=\"https://t.me/ISmartCoder\">Abir Arafat Chawdhury</a>.\n\n"
                "Thank you for using <b>GitHub Notify Bot ⚙️</b>. Your privacy and safety matter most. 🚀"
            )
            await _safe_edit(event, text, buttons=build_policy_back_button())

        elif data in ("menu_vault", "menu_archives", "menu_console", "menu_linkup", "menu_codex", "menu_insight"):
            key = data.replace("menu_", "")
            await _safe_edit(
                event,
                MENU_RESPONSES[key],
                buttons=build_back_to_menu_button(),
            )

        elif data == "close_panel":
            try:
                await event.delete()
            except Exception as e:
                LOGGER.error(f"close_panel error: {e}")

        elif data.startswith("c:") or data.startswith("pr:"):
            from modules.callbacks_repo import route_repo_callback
            await route_repo_callback(event, data)

        elif (
            data.startswith("rm:") or
            data.startswith("sd:") or
            data.startswith("sh:")
        ):
            from modules.repomanage import (
                rm_pg_cb, rm_pick_cb, rm_go_cb, rm_cancel_cb,
                sd_pg_cb, sd_pick_cb, sd_go_cb, sd_cancel_cb,
                sh_pg_cb, sh_pick_cb, sh_go_cb, sh_cancel_cb,
            )
            if data.startswith("rm:pick_pg:"):
                await rm_pg_cb(event)
            elif data.startswith("rm:pick:"):
                await rm_pick_cb(event)
            elif data.startswith("rm:go:"):
                await rm_go_cb(event)
            elif data == "rm:cancel":
                await rm_cancel_cb(event)
            elif data.startswith("sd:pick_pg:"):
                await sd_pg_cb(event)
            elif data.startswith("sd:pick:"):
                await sd_pick_cb(event)
            elif data.startswith("sd:go:"):
                await sd_go_cb(event)
            elif data == "sd:cancel":
                await sd_cancel_cb(event)
            elif data.startswith("sh:pick_pg:"):
                await sh_pg_cb(event)
            elif data.startswith("sh:pick:"):
                await sh_pick_cb(event)
            elif data.startswith("sh:go:"):
                await sh_go_cb(event)
            elif data == "sh:cancel":
                await sh_cancel_cb(event)

        elif data.startswith("cr:"):
            from modules.create import cancel_cb
            if data == "cr:cancel":
                await cancel_cb(event)

    except Exception as e:
        LOGGER.error(f"Callback error for data={data}: {e}")
        try:
            await event.answer("Something went wrong.", alert=False)
        except Exception:
            pass