import json
import traceback

from ghub.markup import esc, repo_link, user_link, clean_body as prose, release_notes as release_body, with_url_btn, action_icon


def _g(obj, *keys, default=""):
    for k in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(k, default)
    return obj if obj is not None else default


def on_issues(ev: dict):
    repo   = _g(ev, "repository", "full_name")
    action = _g(ev, "action")
    sender = _g(ev, "sender", "login")
    issue  = ev.get("issue", {})
    title  = _g(issue, "title")
    url    = _g(issue, "html_url")
    num    = _g(issue, "number")

    msg = (
        f"📌 <b>{esc(action.title())} issue #{num}</b>\n"
        f"📝 <b>Title:</b> {esc(title)}\n\n"
        f"📦 <b>Repository:</b> {repo_link(repo)}\n"
        f"👤 <b>By:</b> {user_link(sender)}\n"
    )
    if action in ("opened", "edited"):
        body = _g(issue, "body")
        if body:
            msg += f"📝 <b>Description:</b>\n{prose(body)}\n"
    elif action == "closed":
        closer = issue.get("closed_by") or {}
        login  = closer.get("login", "") if isinstance(closer, dict) else ""
        if login:
            msg += f"🔒 <b>Closed by:</b> {user_link(login)}\n"
    elif action == "reopened":
        msg += "🔄 <i>Issue reopened</i>\n"
    elif action == "assigned":
        names = [a.get("login", "") for a in issue.get("assignees", [])]
        msg  += f"👥 <b>Assigned to:</b> {', '.join(user_link(n) for n in names)}\n"
    elif action == "labeled":
        labels = [l.get("name", "") for l in issue.get("labels", [])]
        msg   += f"🏷️ <b>Labels:</b> {', '.join(esc(l) for l in labels)}\n"
    elif action == "milestoned":
        ms = issue.get("milestone") or {}
        if isinstance(ms, dict) and ms.get("title"):
            msg += f"📅 <b>Milestone:</b> {esc(ms['title'])}\n"
    return with_url_btn(msg, "🔗 View Issue", url)


def on_pull_request(ev: dict):
    repo   = _g(ev, "repository", "full_name")
    action = _g(ev, "action")
    sender = _g(ev, "sender", "login")
    pr     = ev.get("pull_request", {})
    title  = _g(pr, "title")
    url    = _g(pr, "html_url")
    state  = _g(pr, "state")
    num    = _g(pr, "number")

    msg = (
        f"🚀 <b>PR {esc(action.title())} #{num}: {esc(title)}</b>\n\n"
        f"📦 <b>Repository:</b> {repo_link(repo)}\n"
        f"👤 <b>By:</b> {user_link(sender)} | 🔖 <b>State:</b> {esc(state)}\n"
    )
    if action == "opened":
        msg += f"📝 <b>Description:</b>\n{prose(_g(pr, 'body'))}\n"
    elif action == "closed":
        msg += "✅ Merged\n" if pr.get("merged") else "❌ Closed without merging\n"
    elif action == "reopened":
        msg += "🔄 Reopened\n"
    elif action == "edited":
        msg += f"✏️ Edited\n📝 <b>Description:</b>\n{prose(_g(pr, 'body'))}\n"
    elif action == "assigned":
        names = [a.get("login", "") for a in pr.get("assignees", [])]
        msg  += f"👥 <b>Assigned:</b> {', '.join(user_link(n) for n in names)}\n"
    elif action == "review_requested":
        names = [r.get("login", "") for r in pr.get("requested_reviewers", [])]
        msg  += f"🧐 <b>Reviewers:</b> {', '.join(user_link(n) for n in names)}\n"
    elif action == "labeled":
        labels = [l.get("name", "") for l in pr.get("labels", [])]
        msg   += f"🏷️ <b>Labels:</b> {', '.join(esc(l) for l in labels)}\n"
    elif action == "synchronize":
        msg += "🔄 New commits pushed\n"
    return with_url_btn(msg, "🔗 View PR", url)


def on_push(ev: dict):
    ri       = ev.get("repository", {})
    repo     = _g(ri, "name")
    repo_url = _g(ri, "html_url")
    branch   = _g(ev, "ref").replace("refs/heads/", "")
    compare  = _g(ev, "compare")
    commits  = ev.get("commits", [])
    head     = ev.get("head_commit")
    if not commits and head:
        commits = [head]
    if not commits:
        return None, None

    plural = "s" if len(commits) > 1 else ""
    msg    = f"🔨 <b>{len(commits)} new commit{plural} to</b> <code>{esc(repo)}:{esc(branch)}</code>\n\n"

    if ev.get("created"):
        msg += "🌱 <i>New branch created</i>\n"
    elif ev.get("deleted"):
        msg += "🗑️ <i>Branch deleted</i>\n"
    elif ev.get("forced"):
        msg += "⚠️ <i>Force pushed</i>\n"

    for c in commits:
        sha   = c.get("id", "")
        short = sha[:7]
        curl  = f"{repo_url}/commit/{sha}"
        auth  = c.get("author", {})
        login = auth.get("username", "") or auth.get("login", "")
        who   = user_link(login) if login else esc(auth.get("name", ""))
        line  = c.get("message", "").split("\n")[0]
        msg  += f'🔹 - <a href="{curl}">{esc(short)}</a>: {esc(line)} by {who}\n'

    if len(msg) > 4000:
        msg = (
            f"🔨 <b>{len(commits)} new commit(s) to</b> <code>{esc(repo)}:{esc(branch)}</code>\n\n"
            "⚠️ <i>Too many commits to display, check the repository for details.</i>\n"
        )
    if len(commits) == 1:
        return with_url_btn(msg, "🔗 View Commit", f"{repo_url}/commit/{commits[0].get('id', '')}")
    return with_url_btn(msg, "🔗 View Commits", compare)

def on_create(ev: dict):
    ri       = ev.get("repository", {})
    repo     = _g(ri, "full_name")
    repo_url = _g(ri, "html_url")
    sender   = _g(ev, "sender", "login")
    ref_type = _g(ev, "ref_type")
    ref      = _g(ev, "ref")

    msg = (
        f"✨ <b>New {esc(ref_type)} created</b>\n\n"
        f"🔖 <b>Name:</b> <code>{esc(ref)}</code>\n"
        f"📦 <b>Repository:</b> {repo_link(repo)}\n"
        f"👤 <b>By:</b> {user_link(sender)}\n"
    )
    desc = _g(ev, "description")
    if desc:
        msg += f"📝 <b>Description:</b> {prose(desc)}\n"
    if ref_type == "repository" and _g(ev, "master_branch"):
        msg += f"🌿 <b>Default branch:</b> {esc(_g(ev, 'master_branch'))}\n"
    return with_url_btn(msg, "🔗 View Repository", repo_url)


def on_delete(ev: dict):
    ri       = ev.get("repository", {})
    repo     = _g(ri, "full_name")
    repo_url = _g(ri, "html_url") or f"https://github.com/{repo}"
    sender   = _g(ev, "sender", "login")
    s_url    = _g(ev, "sender", "html_url") or f"https://github.com/{sender}"
    ref_type = _g(ev, "ref_type")
    ref      = _g(ev, "ref")

    msg = (
        "📡 <b>Smart Webhook Ping Received</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"📦 <b>Repo:</b> <a href=\"{repo_url}\">{esc(repo)}</a>\n"
        f"🔔 <b>Ping:</b> {esc(ref_type)} <code>{esc(ref)}</code>\n"
        f"📊 <b>Status:</b> Deleted\n"
        f"🗑️ <b>Deleted By:</b> <a href=\"{s_url}\">{esc(sender)}</a>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "🙏 <b>Thanks for Using Best Bot</b>"
    )
    return with_url_btn(msg, "View Repository", repo_url)


def on_fork(ev: dict):
    original = _g(ev, "repository", "full_name")
    forked   = _g(ev, "forkee", "full_name")
    sender   = _g(ev, "sender", "login")
    stars    = _g(ev, "repository", "stargazers_count")
    forks    = _g(ev, "repository", "forks_count")

    msg = (
        f"🍴 {repo_link(original)} forked by 👤 {user_link(sender)}\n\n"
        f"✨ <b>Stars:</b> {stars} | 🍴 <b>Forks:</b> {forks}"
    )
    return with_url_btn(msg, "🔗 View Fork", f"https://github.com/{forked}")

def on_commit_comment(ev: dict):
    comment = ev.get("comment", {})
    body    = _g(comment, "body")
    sha     = _g(comment, "commit_id")
    repo    = _g(ev, "repository", "full_name")
    sender  = _g(ev, "sender", "login")
    action  = _g(ev, "action")
    curl    = f"https://github.com/{repo}/commit/{sha}"
    icon    = {"created": "💬", "edited": "✏️", "deleted": "🗑️"}.get(action, "⚠️")
    short   = sha[:7] if len(sha) >= 7 else sha

    msg = (
        f"{icon} <b>{user_link(sender)} {esc(action)} comment on commit</b>\n\n"
        f"📦 <b>Repository:</b> {repo_link(repo)}\n"
        f'🔑 <b>Commit:</b> <a href="{curl}"><code>{esc(short)}</code></a>\n'
    )
    if action in ("created", "edited"):
        msg += f"💭 <b>Comment:</b> {prose(body)}"
    return with_url_btn(msg, "🔗 View Comment", _g(comment, "html_url"))


def on_public(ev: dict):
    repo     = _g(ev, "repository", "full_name")
    repo_url = _g(ev, "repository", "html_url")
    sender   = _g(ev, "sender", "login")
    msg = (
        f"🔓 <b>Repository made public</b>\n\n"
        f"📦 <b>Name:</b> {repo_link(repo)}\n"
        f"👤 <b>By:</b> {user_link(sender)}"
    )
    return with_url_btn(msg, "🔗 View Repository", repo_url)


def on_issue_comment(ev: dict):
    action  = _g(ev, "action")
    issue   = ev.get("issue", {})
    comment = ev.get("comment", {})
    repo    = _g(ev, "repository", "full_name")
    sender  = _g(ev, "sender", "login")
    icon    = {"created": "💬", "edited": "✏️", "deleted": "🗑️"}.get(action, "⚠️")
    iurl    = _g(issue, "html_url")

    msg = (
        f"{icon} <b>{user_link(sender)} {esc(action)} comment on</b> "
        f'🔗 <a href="{iurl}">{esc(repo)}#{_g(issue, "number")}</a>\n\n'
        f"📝 <b>Title:</b> {esc(_g(issue, 'title'))}\n"
    )
    if action in ("created", "edited"):
        msg += f"💭 <b>Comment:</b> {prose(_g(comment, 'body'))}"
    return with_url_btn(msg, "🔗 View Comment", _g(comment, "html_url"))


def on_member(ev: dict):
    action   = _g(ev, "action")
    member   = _g(ev, "member", "login")
    repo     = _g(ev, "repository", "full_name")
    repo_url = _g(ev, "repository", "html_url")
    sender   = _g(ev, "sender", "login")
    icon, verb = {
        "added":   ("➕", "added to"),
        "removed": ("➖", "removed from"),
        "edited":  ("✏️", "updated in"),
    }.get(action, ("⚠️", f"performed action on"))

    msg = (
        f"{icon} <b>{user_link(member)}</b> {esc(verb)} <b>{repo_link(repo)}</b>\n\n"
        f"👤 <b>By:</b> {user_link(sender)}"
    )
    if action == "edited" and ev.get("changes"):
        msg += f"\n📝 <b>Changes:</b> {esc(str(ev['changes']))}"
    return with_url_btn(msg, "🔗 View Repository", repo_url)


def on_repository(ev: dict):
    action   = _g(ev, "action")
    ri       = ev.get("repository", {})
    repo     = _g(ri, "full_name")
    repo_url = _g(ri, "html_url") or f"https://github.com/{repo}"
    sender   = _g(ev, "sender", "login")
    s_url    = _g(ev, "sender", "html_url") or f"https://github.com/{sender}"
    status   = {
        "created":    "Repository Created",
        "renamed":    f"Renamed to {esc(_g(ri, 'name'))}",
        "archived":   "Repository Archived",
        "unarchived": "Repository Unarchived",
        "deleted":    "Repository Deleted",
        "publicized": "Made Public",
        "privatized": "Made Private",
    }.get(action, esc(action).title())

    msg = (
        "📡 <b>Smart Webhook Ping Received</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"📦 <b>Repo:</b> <a href=\"{repo_url}\">{esc(repo)}</a>\n"
        f"🔔 <b>Ping:</b> repository.{esc(action)}\n"
        f"📊 <b>Status:</b> {status}\n"
        f"👤 <b>Repo Owner:</b> <a href=\"{s_url}\">{esc(sender)}</a>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "✨ <b>Thanks for Using Best Bot</b>"
    )
    return with_url_btn(msg, "View Repository", repo_url)


def on_release(ev: dict):
    action  = _g(ev, "action")
    release = ev.get("release", {})
    repo    = _g(ev, "repository", "full_name")
    sender  = _g(ev, "sender", "login")
    icon, verb = {
        "created":   ("🎉", "New release"),
        "published": ("🚀", "Release published"),
        "deleted":   ("🗑️", "Release deleted"),
        "edited":    ("✏️", "Release edited"),
    }.get(action, ("⚠️", f"Unknown action ({action})"))

    msg = (
        f"{icon} <b>{esc(verb)} in</b> {repo_link(repo)}\n\n"
        f"<b>Tag:</b> {esc(_g(release, 'tag_name'))}\n"
        f"<b>By:</b> {user_link(sender)}"
    )
    body = _g(release, "body")
    if action in ("created", "edited") and body:
        msg += f"\n<b>Notes:</b>\n{release_body(body)}"
    return with_url_btn(msg, "View Release", _g(release, "html_url"))


def on_watch(ev: dict):
    action  = _g(ev, "action")
    ri      = ev.get("repository", {})
    repo    = _g(ri, "full_name")
    repo_url = _g(ri, "html_url") or f"https://github.com/{repo}"
    sender  = _g(ev, "sender", "login")
    s_url   = _g(ev, "sender", "html_url") or f"https://github.com/{sender}"

    msg = (
        "📡 <b>Smart Webhook Ping Received</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"📦 <b>Repo:</b> <a href=\"{repo_url}\">{esc(repo)}</a>\n"
        f"🔔 <b>Ping:</b> watch.{esc(action)}\n"
        f"📊 <b>Status:</b> Active\n"
        f"⭐️ <b>Starred By:</b> <a href=\"{s_url}\">{esc(sender)}</a>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "🙏 <b>Thanks for Using Best Bot</b>"
    )
    return with_url_btn(msg, "View Repository", repo_url)


def on_star(ev: dict):
    action  = _g(ev, "action")
    ri      = ev.get("repository", {})
    repo    = _g(ri, "full_name")
    repo_url = _g(ri, "html_url") or f"https://github.com/{repo}"
    sender  = _g(ev, "sender", "login")
    s_url   = _g(ev, "sender", "html_url") or f"https://github.com/{sender}"

    if action == "created":
        star_line = f"⭐️ <b>Starred By:</b> <a href=\"{s_url}\">{esc(sender)}</a>"
        status    = "Starred"
    else:
        star_line = f"⭐️ <b>Unstarred By:</b> <a href=\"{s_url}\">{esc(sender)}</a>"
        status    = "Unstarred"

    msg = (
        "📡 <b>Smart Webhook Ping Received</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"📦 <b>Repo:</b> <a href=\"{repo_url}\">{esc(repo)}</a>\n"
        f"🔔 <b>Ping:</b> star.{esc(action)}\n"
        f"📊 <b>Status:</b> {status}\n"
        f"{star_line}\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "🙏 <b>Thanks for Using Best Bot</b>"
    )
    return with_url_btn(msg, "View Repository", repo_url)


def on_gollum(ev: dict):
    if not ev:
        return "📚 <b>No wiki update data available</b>", None
    msg    = "📚 <b>Wiki Update</b>\n\n"
    ri     = ev.get("repository")
    if ri:
        msg += f"📦 <b>Repository:</b> {repo_link(_g(ri, 'full_name'))}\n"
    org = ev.get("organization")
    if org:
        msg += f"🏢 <b>Organization:</b> {esc(_g(org, 'login'))}\n"
    sender = ev.get("sender")
    if sender:
        msg += f"👤 <b>Edited by:</b> {user_link(_g(sender, 'login'))}\n"
    pages = ev.get("pages", [])
    if pages:
        msg += "\n📄 <b>Page Changes:</b>\n"
        for page in pages:
            if not page:
                continue
            act   = page.get("action", "unknown")
            icon  = action_icon(act)
            title = page.get("title") or page.get("page_name") or ""
            if title:
                msg += f"{icon} <b>{esc(title)}</b> ({esc(act)})\n"
            summary = page.get("summary", "")
            if summary:
                msg += f"📝 <i>Summary:</i> {esc(summary)}\n"
            sha = page.get("sha", "")
            if sha:
                msg += f"🔑 <i>Revision:</i> {esc(sha[:7])}\n"
            purl = page.get("html_url", "")
            if purl:
                msg += f"🔗 <a href=\"{purl}\">View Page</a>\n"
            msg += "\n"
    return msg, None


def on_deploy_key(ev: dict):
    if not ev:
        return "🔑 <b>No deploy key data</b>", None
    action = _g(ev, "action")
    key    = ev.get("key", {})
    ri     = ev.get("repository", {})
    sender = _g(ev, "sender", "login")
    msg    = f"🔑 <b>Deploy Key {esc(action)}</b>\n\n"
    if key:
        msg += f"📝 <b>Title:</b> {esc(_g(key, 'title'))}\n"
        ku   = _g(key, "url")
        if ku:
            msg += f'🔗 <a href="{ku}">View Key</a>\n'
    msg += f"📦 <b>Repository:</b> {repo_link(_g(ri, 'name'))}\n"
    msg += f"👤 <b>By:</b> {user_link(sender)}"
    return with_url_btn(msg, "🔗 View Repository", _g(ri, "html_url"))

def on_ping(ev: dict):
    ri       = ev.get("repository") or {}
    sender   = ev.get("sender") or {}
    repo_name = _g(ri, "full_name") or _g(ri, "name") or "Unknown"
    repo_url  = _g(ri, "html_url") or f"https://github.com/{repo_name}"
    sender_login = _g(sender, "login")
    sender_url   = _g(sender, "html_url") or f"https://github.com/{sender_login}"
    zen      = ev.get("zen") or ""
    hook_id  = str(_g(ev, "hook_id") or "")
    status   = "Active ✅"

    msg = (
        "📡 <b>Smart Webhook Ping Received</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Repo:</b> <a href=\"{repo_url}\">{esc(repo_name)}</a>\n"
        f"🔔 <b>Ping:</b> {esc(zen)}\n"
        f"📊 <b>Status:</b> {status}\n"
        f"🆔 <b>Hook ID:</b> <code>{esc(hook_id)}</code>\n"
        f"👤 <b>Repo-Owner:</b> <a href=\"{sender_url}\">{esc(sender_login)}</a>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ <b>Thanks For Using Best Bot</b>"
    )
    return msg, None

def on_pr_review(ev: dict):
    action = _g(ev, "action")
    review = ev.get("review", {})
    pr     = ev.get("pull_request", {})
    state  = _g(review, "state").lower()
    icon   = {"approved": "✅", "changes_requested": "✏️", "commented": "💬", "dismissed": "❌"}.get(state, "🔍")
    purl   = _g(pr, "html_url")

    msg = (
        f"{icon} <b>PR Review {esc(action)}</b>\n\n"
        f"📦 <b>Repository:</b> {repo_link(_g(ev, 'repository', 'full_name'))}\n"
        f'🔀 <b>PR:</b> <a href="{purl}">{esc(_g(pr, "title"))}#{_g(pr, "number")}</a>\n'
        f"📊 <b>State:</b> {esc(state)}\n"
        f"👤 <b>By:</b> {user_link(_g(ev, 'sender', 'login'))}\n"
    )
    return with_url_btn(msg, "🔗 View Review", _g(review, "html_url"))

def on_pr_review_comment(ev: dict):
    action  = _g(ev, "action")
    repo    = _g(ev, "repository", "full_name")
    comment = ev.get("comment", {})
    pr      = ev.get("pull_request", {})
    icon    = {"created": "💬", "edited": "✏️", "deleted": "🗑️"}.get(action, "⚠️")
    purl    = _g(pr, "html_url")

    msg = (
        f"{icon} <b>PR Review Comment {esc(action)}</b>\n\n"
        f"📦 <b>Repository:</b> {repo_link(repo)}\n"
        f'🔀 <b>PR:</b> <a href="{purl}">{esc(_g(pr, "title"))}#{_g(pr, "number")}</a>\n'
        f"💭 <b>Comment:</b> {prose(_g(comment, 'body'))}\n"
    )
    return with_url_btn(msg, "🔗 View Comment", _g(comment, "html_url"))

def on_pr_review_thread(ev: dict):
    if not ev:
        return "💬 <b>No PR review thread data</b>", None
    pr     = ev.get("pull_request", {})
    repo   = _g(ev, "repository", "full_name")
    sender = _g(ev, "sender", "login")
    purl   = _g(pr, "html_url")

    msg = (
        f"💬 <b>PR Review Thread {esc(_g(ev, 'action'))}</b>\n\n"
        f"📦 <b>Repository:</b> {repo_link(repo)}\n"
        f'🔀 <b>PR:</b> <a href="{purl}">{esc(_g(pr, "title"))}#{_g(pr, "number")}</a>\n'
        f"👤 <b>By:</b> {user_link(sender)}"
    )
    return with_url_btn(msg, "🔗 View PR", purl)

def on_workflow_run(ev: dict):
    workflow = _g(ev, "workflow", "name")
    run      = ev.get("workflow_run", {})
    repo     = _g(ev, "repository", "full_name")
    sender   = _g(ev, "sender", "login")
    status   = _g(run, "status")
    concl    = _g(run, "conclusion")

    if status == "completed":
        icon, label = {
            "success":   ("✅", "Success"),
            "failure":   ("❌", "Failed"),
            "neutral":   ("⚖️", "Neutral"),
            "cancelled": ("⛔", "Cancelled"),
        }.get(concl, ("🏁", "Completed"))
    elif status == "in_progress":
        icon, label = "⏳", "Running"
    elif status == "queued":
        icon, label = "🔄", "Queued"
    else:
        icon, label = "⚠️", "Unknown"

    msg = (
        f"{icon} <b>{esc(workflow)} workflow</b>\n\n"
        f"📊 <b>Status:</b> {esc(label)}\n"
        f"📦 <b>Repository:</b> {repo_link(repo)}\n"
        f"👤 <b>By:</b> {user_link(sender)}"
    )
    return with_url_btn(msg, "🔗 View Run", _g(run, "html_url"))

def on_workflow_job(ev: dict):
    if not ev:
        return "⚙️ <b>No workflow job data</b>", None
    job    = ev.get("workflow_job", {})
    status = _g(job, "status")
    concl  = _g(job, "conclusion")
    icon, label = "⚙️", status.title() if status else ""

    if status == "completed" and concl == "success":
        icon, label = "✅", "Success"
    elif status == "completed" and concl == "failure":
        icon, label = "❌", "Failed"
    elif status == "in_progress":
        icon = "⏳"
    elif status == "queued":
        icon = "🔄"
    elif concl == "cancelled":
        icon, label = "⛔", "Cancelled"

    msg  = f"{icon} <b>Workflow Job {esc(label)}</b>\n\n"
    msg += f"📝 <b>Name:</b> {esc(_g(job, 'name'))}\n"
    msg += f"📦 <b>Repository:</b> {repo_link(_g(ev, 'repository', 'full_name'))}\n"
    started = _g(job, "started_at")
    if started:
        msg += f"⏱️ <b>Started:</b> {esc(str(started)[:16])}\n"
    completed = _g(job, "completed_at")
    if completed:
        msg += f"🏁 <b>Completed:</b> {esc(str(completed)[:16])}\n"
    runner = _g(job, "runner_name")
    if runner:
        msg += f"🖥️ <b>Runner:</b> {esc(runner)}\n"
    msg += f"👤 <b>By:</b> {user_link(_g(ev, 'sender', 'login'))}\n"
    return with_url_btn(msg, "🔗 View Job", _g(job, "html_url"))

def on_check_suite(ev: dict):
    if not ev:
        return "✅ <b>No check suite data</b>", None
    suite  = ev.get("check_suite", {})
    action = _g(ev, "action").title()
    msg    = f"✅ <b>Check Suite: {esc(action)}</b>\n\n"
    if suite:
        msg += f"📊 • <b>Status:</b> {esc(_g(suite, 'status'))}\n"
        concl = _g(suite, "conclusion")
        if concl:
            msg += f"🏁 • <b>Result:</b> {esc(concl)}\n"
    msg += f"\n📦 <b>Repository:</b> {repo_link(_g(ev, 'repository', 'full_name'))}\n"
    sl = _g(ev, "sender", "login")
    if sl:
        msg += f"👤 <b>Triggered by:</b> {esc(sl)}"
    return with_url_btn(msg, "🔗 View Details", _g(suite, "url"))
    
def on_check_run(ev: dict):
    if not ev:
        return "⚙️ <b>No check run data</b>", None
    check  = ev.get("check_run", {})
    action = _g(ev, "action").title()
    msg    = f"⚙️ <b>Check Run: {esc(action)}</b>\n\n"
    if check:
        msg += f"📝 • <b>Name:</b> {esc(_g(check, 'name'))}\n"
        msg += f"📊 • <b>Status:</b> {esc(_g(check, 'status'))}\n"
        concl = _g(check, "conclusion")
        if concl:
            msg += f"🏁 • <b>Result:</b> {esc(concl)}\n"
        started = _g(check, "started_at")
        if started:
            msg += f"⏱️ • <b>Started:</b> {esc(str(started)[:16])}\n"
        completed = _g(check, "completed_at")
        if completed:
            msg += f"🏁 • <b>Completed:</b> {esc(str(completed)[:16])}\n"
    msg += f"\n📦 <b>Repository:</b> {repo_link(_g(ev, 'repository', 'full_name'))}\n"
    sl = _g(ev, "sender", "login")
    if sl:
        msg += f"👤 <b>Triggered by:</b> {esc(sl)}"
    return with_url_btn(msg, "🔗 View Details", _g(check, "html_url"))

def on_deployment_status(ev: dict):
    if not ev:
        return "🚦 <b>No deployment status data</b>", None
    status = ev.get("deployment_status", {})
    msg    = f"🚦 <b>Deployment {esc(_g(status, 'state'))}</b>\n\n"
    desc   = _g(status, "description")
    if desc:
        msg += f"📊 <b>Status:</b> {prose(desc)}\n"
    msg += f"📦 <b>Repository:</b> {repo_link(_g(ev, 'repository', 'name'))}\n"
    sl = _g(ev, "sender", "login")
    if sl:
        msg += f"👤 <b>By:</b> {user_link(sl)}"
    return with_url_btn(msg, "🔗 View Deployment", _g(status, "deployment_url"))

def on_security_advisory(ev: dict):
    if not ev:
        return "⚠️ <b>No security advisory data</b>", None
    adv = ev.get("security_advisory", {})
    msg = f"⚠️ <b>Security Advisory {esc(_g(ev, 'action'))}</b>\n\n"
    if adv:
        msg += f"📝 <b>Summary:</b> {prose(_g(adv, 'summary'))}\n"
        sev = _g(adv, "severity")
        if sev:
            msg += f"🔥 <b>Severity:</b> {esc(sev)}\n"
        cve = _g(adv, "cve_id") or _g(adv, "cvss", "vector_string")
        if cve:
            msg += f"🆔 <b>CVE:</b> {esc(str(cve))}\n"
        adv_url = _g(adv, "url") or _g(adv, "html_url")
        if adv_url:
            msg += f'🔗 <a href="{adv_url}">View Advisory</a>\n'
    repo = ev.get("repository") or {}
    if isinstance(repo, dict) and repo.get("full_name"):
        msg += f"📦 <b>Repository:</b> {repo_link(repo['full_name'])}\n"
    sender = ev.get("sender") or {}
    if isinstance(sender, dict) and sender.get("login"):
        msg += f"👤 <b>By:</b> {user_link(sender['login'])}"
    return with_url_btn(msg, "🔗 View Advisory", _g(adv, "html_url"))


def on_sponsorship(ev: dict):
    action  = _g(ev, "action")
    sender  = ev.get("sender", {})
    changes = ev.get("changes") or {}
    msg     = f"💖 <b>Sponsorship {esc(action)}</b>\n\n👤 <b>Sponsor:</b> {user_link(_g(sender, 'login'))}\n"
    tier    = changes.get("tier")
    if tier and isinstance(tier, dict):
        msg += f"💎 <b>Tier:</b> <code>{esc(str(tier.get('from', '')))}</code> -> new_tier\n"
    return with_url_btn(msg, "🔗 View Sponsorship", _g(sender, "html_url"))

def on_installation(ev: dict):
    action = _g(ev, "action")
    sender = _g(ev, "sender", "login")
    if action == "created":
        msg = (
            "🎉 <b>New installation!</b> Welcome aboard! 🎉\n\n"
            "🤖 This bot will now post updates from the repositories you granted access to.\n\n"
            f"👤 Installation by {user_link(sender)}."
        )
    elif action == "deleted":
        msg = (
            "🗑️ <b>Installation uninstalled!</b> Goodbye! 👋\n\n"
            "⚠️ This bot will no longer post updates.\n\n"
            f"👤 Uninstalled by {user_link(sender)}."
        )
    else:
        msg = f"🤖 <b>Unknown installation action:</b> <code>{esc(action)}</code>"
    return msg, None


def on_merge_group(ev: dict):
    if not ev:
        return "🔀 <b>No merge group data</b>", None
    mg   = ev.get("merge_group", {})
    repo = _g(ev, "repository", "full_name")
    msg  = (
        f"🔀 <b>Merge Group {esc(_g(ev, 'action'))}</b>\n\n"
        f"📦 <b>Repository:</b> {repo_link(repo)}\n"
        f"🔑 <b>Head SHA:</b> <code>{esc(_g(mg, 'head_sha')[:7])}</code>"
    )
    return with_url_btn(msg, "🔗 View Repository", _g(ev, "repository", "html_url"))

def on_workflow_dispatch(ev: dict):
    ri       = ev.get("repository", {})
    repo     = _g(ri, "full_name")
    repo_url = _g(ri, "html_url")
    workflow = _g(ev, "workflow") or "Unnamed Workflow"
    sender   = _g(ev, "sender", "login")
    ref      = _g(ev, "ref")
    inputs   = ev.get("inputs") or {}
    istr     = ", ".join(f"{k}: {v}" for k, v in inputs.items()) if inputs else "No inputs"

    msg = (
        f"🚀 <b>{esc(workflow)} manually triggered</b>\n\n"
        f"📦 <b>Repository:</b> {repo_link(repo)}\n"
        f"🌿 <b>Branch:</b> {esc(ref)}\n"
        f"📝 <b>Inputs:</b> {esc(istr)}\n"
        f"👤 <b>By:</b> {user_link(sender)}"
    )
    return with_url_btn(msg, "🔗 View Repository", repo_url)

def on_repo_dispatch(ev: dict):
    ri     = ev.get("repository", {})
    repo   = _g(ri, "full_name")
    sender = _g(ev, "sender", "login")
    action = _g(ev, "action")
    branch = ev.get("branch") or _g(ri, "master_branch") or "default branch"

    payload_str = ""
    cp = ev.get("client_payload")
    if cp and isinstance(cp, dict) and cp:
        payload_str = f"\n📝 <b>Payload:</b> <code>{esc(json.dumps(cp))}</code>"

    msg = (
        f"🚀 <b>Repository Dispatch</b>\n\n"
        f"📦 <b>Repository:</b> {repo_link(repo)}\n"
        f"⚙️ <b>Action:</b> {esc(action)}\n"
        f"🌿 <b>Branch:</b> {esc(str(branch))}\n"
        f"👤 <b>By:</b> {user_link(sender)}{payload_str}"
    )
    return with_url_btn(msg, "🔗 View Repository", _g(ri, "html_url"))

EVENT_HANDLERS = {
    "push":                        on_push,
    "issues":                      on_issues,
    "pull_request":                on_pull_request,
    "issue_comment":               on_issue_comment,
    "pull_request_review":         on_pr_review,
    "pull_request_review_comment": on_pr_review_comment,
    "pull_request_review_thread":  on_pr_review_thread,
    "fork":                        on_fork,
    "star":                        on_star,
    "watch":                       on_watch,
    "gollum":                      on_gollum,
    "member":                      on_member,
    "repository":                  on_repository,
    "ping":                        on_ping,
    "create":                      on_create,
    "delete":                      on_delete,
    "release":                     on_release,
    "workflow_run":                on_workflow_run,
    "workflow_job":                on_workflow_job,
    "workflow_dispatch":           on_workflow_dispatch,
    "repository_dispatch":         on_repo_dispatch,
    "check_suite":                 on_check_suite,
    "check_run":                   on_check_run,
    "deployment_status":           on_deployment_status,
    "security_advisory":           on_security_advisory,
    "sponsorship":                 on_sponsorship,
    "installation":                on_installation,
    "public":                      on_public,
    "commit_comment":              on_commit_comment,
    "deploy_key":                  on_deploy_key,
    "merge_group":                 on_merge_group,
}


def route_event(event_type: str, payload: dict):
    handler = EVENT_HANDLERS.get(event_type)
    if handler is None:
        return None, None
    try:
        return handler(payload)
    except Exception:
        traceback.print_exc()
        return None, None