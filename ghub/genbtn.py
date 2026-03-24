import config
from helpers.buttons import SmartButtons


MENU_RESPONSES = {
    "vault": (
        "<b>🔐 Vault ⚙️</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "<b>USAGE:</b>\n"
        "Link repositories and manage webhooks:\n\n"
        "➢ <b>/addrepo owner/repo</b> — Link a repository by name directly.\n"
        " - Automatically creates a webhook for real-time notifications.\n\n"
        "➢ <b>/addrepo</b> — Browse your GitHub repositories interactively.\n\n"
        "➢ <b>/removerepo owner/repo</b> — Unlink a repository and delete its webhook.\n\n"
        "<b>✨ NOTE:</b>\n"
        "1️⃣ You must /connect your GitHub account first.\n"
        "2️⃣ Admin access to the repository is required to create webhooks.\n\n"
        f"<b>🔔 For Bot Update News</b>: <a href='https://{config.UPDATES_URL}'>Join Now</a>"
    ),
    "archives": (
        "<b>🗂 Archives ⚙️</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "<b>USAGE:</b>\n"
        "View and manage your linked repositories:\n\n"
        "➢ <b>/repos</b> — List all repositories linked to this chat.\n\n"
        "➢ <b>/settings</b> — Set repo update destination & notification format.\n"
        " - Set Update Destination per repository.\n"
        " - Choose notification format per repository.\n\n"
        "➢ <b>/del</b> — Delete a repository directly from GitHub.\n"
        "➢ <b>/setdescription</b> — Update a repository's description.\n"
        "➢ <b>/sethandle</b> — Rename a repository handle on GitHub.\n\n"
        "<b>✨ NOTE:</b>\n"
        "1️⃣ Settings can only be changed by chat admins.\n"
        "2️⃣ Destination & format are synced directly to your GitHub webhook.\n\n"
        f"<b>🔔 For Bot Update News</b>: <a href='https://{config.UPDATES_URL}'>Join Now</a>"
    ),
    "console": (
        "<b>🖥 Console ⚙️</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "<b>USAGE:</b>\n"
        "Admin tools for managing the bot:\n\n"
        "➢ <b>/stats</b> — View usage statistics and active users.\n"
        "➢ <b>/broadcast</b> — Forward a message to all users (reply to message).\n"
        "➢ <b>/ban @user</b> — Ban a user from using the bot.\n"
        "➢ <b>/unban @user</b> — Unban a previously banned user.\n"
        "➢ <b>/banlist</b> — View the full list of banned users.\n"
        "➢ <b>/logs</b> — Download the bot's log file.\n"
        "➢ <b>/restart</b> — Restart the bot process.\n"
        "➢ <b>/config</b> — Edit bot environment variables live.\n\n"
        "<b>✨ NOTE:</b>\n"
        "1️⃣ Admin-only commands. Authorized users can also access these.\n"
        "2️⃣ Use /auth to promote users to authorized admins.\n\n"
        f"<b>🔔 For Bot Update News</b>: <a href='https://{config.UPDATES_URL}'>Join Now</a>"
    ),
    "linkup": (
        "<b>🔗 Linkup ⚙️</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "<b>USAGE:</b>\n"
        "Connect and manage your GitHub account:\n\n"
        "➢ <b>/connect</b> — Link your GitHub account via OAuth.\n"
        " - Must be used in a private chat with the bot.\n"
        " - Grants repo and webhook management access.\n\n"
        "➢ <b>/logout</b> — Unlink your GitHub account and revoke the stored token.\n\n"
        "<b>✨ NOTE:</b>\n"
        "1️⃣ Your OAuth token is encrypted with AES-256-GCM before storage.\n"
        "2️⃣ You can reconnect at any time after /logout.\n\n"
        f"<b>🔔 For Bot Update News</b>: <a href='https://{config.UPDATES_URL}'>Join Now</a>"
    ),
    "codex": (
        "<b>📖 Codex ⚙️</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "<b>USAGE:</b>\n"
        "Interact directly with GitHub from Telegram:\n\n"
        "➢ <b>/approve</b> — Approve a PR (reply to its notification).\n"
        "➢ <b>/close</b> — Close an issue or PR (reply to its notification).\n"
        "➢ <b>/reopen</b> — Reopen an issue or PR (reply to its notification).\n\n"
        "➢ <b>/create</b> — Create a new GitHub repository and upload files as zip.\n\n"
        "➢ <b>/reload</b> — Refresh the admin permission cache for this chat.\n\n"
        "<b>✨ NOTE:</b>\n"
        "1️⃣ Action commands must be used in reply to a bot notification.\n"
        "2️⃣ You must be connected via /connect to perform actions.\n\n"
        f"<b>🔔 For Bot Update News</b>: <a href='https://{config.UPDATES_URL}'>Join Now</a>"
    ),
    "insight": (
        "<b>📊 Insight ⚙️</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "<b>USAGE:</b>\n"
        "Explore statistics and bot health:\n\n"
        "➢ <b>Statistics</b> — View daily, weekly, monthly and yearly active user counts.\n"
        "➢ <b>Top Users</b> — See the most active users leaderboard.\n"
        "➢ <b>Server</b> — Check CPU, memory, disk, and network status of the host.\n\n"
        "<b>✨ NOTE:</b>\n"
        "1️⃣ Statistics are tracked automatically as users interact with the bot.\n"
        "2️⃣ Server info reflects the live state of the hosting machine.\n\n"
        f"<b>🔔 For Bot Update News</b>: <a href='https://{config.UPDATES_URL}'>Join Now</a>"
    ),
}


def build_start_buttons():
    sb = SmartButtons()
    sb.button(text="⚙️ Main Menu",      callback_data="main_menu",   position="header")
    sb.button(text="ℹ️ About Me",       callback_data="about_me")
    sb.button(text="📄 Policy & Terms", callback_data="policy_terms")
    return sb.build_menu(b_cols=2)


def build_main_menu_buttons():
    sb = SmartButtons()
    sb.button(text="🔐 Vault",    callback_data="menu_vault")
    sb.button(text="🗂 Archives", callback_data="menu_archives")
    sb.button(text="🖥 Console",  callback_data="menu_console")
    sb.button(text="🔗 Linkup",   callback_data="menu_linkup")
    sb.button(text="📖 Codex",    callback_data="menu_codex")
    sb.button(text="📊 Insight",  callback_data="menu_insight")
    sb.button(text="❌ Dismiss",  callback_data="close_panel",  position="footer")
    return sb.build_menu(b_cols=2, f_cols=1)


def build_back_to_menu_button():
    sb = SmartButtons()
    sb.button(text="⬅️ Back", callback_data="back_to_main_menu")
    return sb.build_menu(b_cols=1)


def build_back_to_start_button():
    sb = SmartButtons()
    sb.button(text="⬅️ Back", callback_data="back_to_start")
    return sb.build_menu(b_cols=1)


def build_about_buttons():
    sb = SmartButtons()
    sb.button(text="📊 Statistics", callback_data="gh_fstats")
    sb.button(text="💾 Server",     callback_data="gh_server")
    sb.button(text="⭐️ Donate",    callback_data="donate")
    sb.button(text="⬅️ Back",       callback_data="back_to_start", position="footer")
    return sb.build_menu(b_cols=3, f_cols=1)


def build_fstats_buttons():
    sb = SmartButtons()
    sb.button(text="📈 Usage Report", callback_data="gh_stats")
    sb.button(text="🏆 Top Users",    callback_data="top_users_1")
    sb.button(text="⬅️ Back",         callback_data="about_me",  position="footer")
    return sb.build_menu(b_cols=2, f_cols=1)


def build_stats_back_button():
    sb = SmartButtons()
    sb.button(text="⬅️ Back", callback_data="gh_fstats")
    return sb.build_menu(b_cols=1)


def build_server_back_button():
    sb = SmartButtons()
    sb.button(text="⬅️ Back", callback_data="about_me")
    return sb.build_menu(b_cols=1)


def build_top_users_buttons(page: int, total_pages: int):
    sb = SmartButtons()
    if page == 1 and total_pages > 1:
        sb.button(text="Next ➡️", callback_data=f"top_users_{page + 1}")
        sb.button(text="⬅️ Back", callback_data="gh_fstats",            position="footer")
        return sb.build_menu(b_cols=1, f_cols=1)
    elif 1 < page < total_pages:
        sb.button(text="⬅️ Previous", callback_data=f"top_users_{page - 1}")
        sb.button(text="Next ➡️",     callback_data=f"top_users_{page + 1}")
        return sb.build_menu(b_cols=2)
    elif page == total_pages and page > 1:
        sb.button(text="⬅️ Previous", callback_data=f"top_users_{page - 1}")
        return sb.build_menu(b_cols=1)
    else:
        sb.button(text="⬅️ Back", callback_data="gh_fstats")
        return sb.build_menu(b_cols=1)


def build_policy_terms_buttons():
    sb = SmartButtons()
    sb.button(text="🔐 Privacy Policy",     callback_data="privacy_policy")
    sb.button(text="📋 Terms & Conditions", callback_data="terms_conditions")
    sb.button(text="⬅️ Back",               callback_data="back_to_start", position="footer")
    return sb.build_menu(b_cols=2, f_cols=1)


def build_policy_back_button():
    sb = SmartButtons()
    sb.button(text="⬅️ Back", callback_data="policy_terms")
    return sb.build_menu(b_cols=1)