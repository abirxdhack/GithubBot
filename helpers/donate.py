import asyncio
import time
import uuid

from telethon import events

import config
from bot import Irene
from helpers.buttons import SmartButtons
from helpers.logger import LOGGER


DONATION_TEXT = (
    "<b>Why support GitHub Notify Bot?</b>\n"
    "<b>━━━━━━━━━━━━━━━━━━</b>\n"
    "🌟 <b>Love the service?</b>\n"
    "Your support helps keep <b>GitHub Notify Bot</b> fast, reliable, and free for everyone.\n"
    "Even a small <b>Gift or Donation</b> makes a big difference! 💖\n\n"
    "👇 <b>Choose an amount to contribute:</b>\n\n"
    "<b>Why contribute?</b>\n"
    "More support = more motivation\n"
    "More motivation = better tools\n"
    "Better tools = more productivity\n"
    "More productivity = less wasted time\n"
    "Less wasted time = more done with <b>GitHub Notify Bot</b> 💡\n"
    "<b>More Muhahaha… 🤓🔥</b>"
)

PAYMENT_SUCCESS_TEXT = (
    "<b>✅ Donation Successful!</b>\n\n"
    "🎉 Huge thanks <b>{0}</b> for donating <b>{1}</b> ⭐️ to support <b>GitHub Notify Bot!</b>\n"
    "Your contribution helps keep everything running smooth and awesome 🚀\n\n"
    "<b>🧾 Transaction ID:</b> <code>{2}</code>"
)

ADMIN_NOTIFY_TEXT = (
    "<b>Hey New Donation Received 🤗</b>\n"
    "<b>━━━━━━━━━━━━━━━</b>\n"
    "<b>From:</b> {0}\n"
    "<b>Username:</b> {2}\n"
    "<b>UserID:</b> <code>{1}</code>\n"
    "<b>Amount:</b> {3} ⭐️\n"
    "<b>Transaction ID:</b> <code>{4}</code>\n"
    "<b>━━━━━━━━━━━━━━━</b>\n"
    "<b>Click Below Button If Need Refund 💸</b>"
)

INVOICE_CREATING_TEXT = "Generating invoice for {0} Stars...\nPlease wait ⏳"
INVOICE_READY_TEXT    = "<b>✅ Invoice for {0} Stars has been generated! You can now proceed to pay.</b>"
INVOICE_DUPE_TEXT     = "<b>🚫 Wait! Contribution Already in Progress!</b>"
INVOICE_FAIL_TEXT     = "<b>❌ Invoice Creation Failed! Try Again!</b>"
REFUND_OK_TEXT        = "<b>✅ Refund Successfully Completed!</b>\n\n<b>{0} Stars</b> have been refunded to <b><a href='tg://user?id={2}'>{1}</a></b>"
REFUND_FAIL_TEXT      = "<b>❌ Refund Failed!</b>\n\nFailed to refund <b>{0} Stars</b> to <b>{1}</b> (ID: <code>{2}</code>)\nError: {3}"

_active_invoices: dict = {}
_payment_data: dict    = {}


def get_donation_buttons(amount: int = 5):
    sb = SmartButtons()
    if amount == 5:
        sb.button(text=f"{amount} ⭐️", callback_data=f"donate_{amount}")
        sb.button(text="+5",            callback_data=f"donate_inc_{amount}")
    else:
        sb.button(text="-5",            callback_data=f"donate_dec_{amount}")
        sb.button(text=f"{amount} ⭐️", callback_data=f"donate_{amount}")
        sb.button(text="+5",            callback_data=f"donate_inc_{amount}")
    sb.button(text="🔙 Back", callback_data="about_me", position="footer")
    cols = 2 if amount == 5 else 3
    return sb.build_menu(b_cols=cols, f_cols=1)


def _back_btn():
    sb = SmartButtons()
    sb.button(text="🔙 Back", callback_data="about_me")
    return sb.build_menu(b_cols=1)


async def _make_invoice(chat_id: int, user_id: int, quantity: int, msg_id: int):
    if _active_invoices.get(user_id):
        from helpers.botutils import send_message
        await send_message(chat_id, INVOICE_DUPE_TEXT, parse_mode="html")
        return

    try:
        _active_invoices[user_id] = True
        from telethon.tl.types import InputMediaInvoice, Invoice, LabeledPrice as TLPrice, DataJSON

        ts      = int(time.time())
        uid_str = str(uuid.uuid4())[:8]
        payload = f"ghnotify_donate_{user_id}_{quantity}_{ts}_{uid_str}"

        await Irene.send_message(
            chat_id,
            file=InputMediaInvoice(
                title="Support GitHub Notify Bot",
                description=f"Contribute {quantity} Stars to keep the bot fast and free 💫",
                invoice=Invoice(
                    currency="XTR",
                    prices=[TLPrice(label=f"⭐️ {quantity} Stars", amount=quantity)],
                    test=False,
                ),
                payload=payload.encode(),
                provider="",
                provider_data=DataJSON(data="{}"),
                start_param="donate",
            ),
        )

        await Irene.edit_message(
            chat_id, msg_id,
            INVOICE_READY_TEXT.format(quantity),
            parse_mode="html",
            buttons=_back_btn(),
        )
        LOGGER.info(f"Invoice created for {quantity} stars → user {user_id}")
    except Exception as e:
        LOGGER.error(f"_make_invoice error for user {user_id}: {e}")
        try:
            await Irene.edit_message(chat_id, msg_id, INVOICE_FAIL_TEXT, parse_mode="html", buttons=_back_btn())
        except Exception:
            from helpers.botutils import send_message
            await send_message(chat_id, INVOICE_FAIL_TEXT, parse_mode="html", buttons=_back_btn())
    finally:
        _active_invoices.pop(user_id, None)


@Irene.on(events.CallbackQuery(data=b"donate"))
async def _donate_show(event):
    try:
        await event.edit(DONATION_TEXT, parse_mode="html", buttons=get_donation_buttons(5), link_preview=False)
        await event.answer()
    except Exception as e:
        LOGGER.error(f"donate_show error: {e}")


@Irene.on(events.CallbackQuery(pattern=rb"donate_inc_(\d+)"))
async def _donate_inc(event):
    try:
        cur = int(event.data.decode().split("donate_inc_")[1])
        new = cur + 5
        await event.edit(DONATION_TEXT, parse_mode="html", buttons=get_donation_buttons(new), link_preview=False)
        await event.answer(f"Updated to {new} Stars")
    except Exception as e:
        LOGGER.error(f"donate_inc error: {e}")


@Irene.on(events.CallbackQuery(pattern=rb"donate_dec_(\d+)"))
async def _donate_dec(event):
    try:
        cur = int(event.data.decode().split("donate_dec_")[1])
        new = max(5, cur - 5)
        await event.edit(DONATION_TEXT, parse_mode="html", buttons=get_donation_buttons(new), link_preview=False)
        await event.answer(f"Updated to {new} Stars")
    except Exception as e:
        LOGGER.error(f"donate_dec error: {e}")


@Irene.on(events.CallbackQuery(pattern=rb"donate_(\d+)$"))
async def _donate_invoke(event):
    try:
        quantity = int(event.data.decode().split("donate_")[1])
        await event.edit(INVOICE_CREATING_TEXT.format(quantity), parse_mode="html")
        await event.answer("Generating invoice...")
        asyncio.get_event_loop().create_task(
            _make_invoice(event.chat_id, event.sender_id, quantity, event.message_id)
        )
    except Exception as e:
        LOGGER.error(f"donate_invoke error: {e}")
        await event.answer("❌ Failed to generate invoice!", alert=True)


@Irene.on(events.CallbackQuery(pattern=rb"refund_(.+)"))
async def _donate_refund(event):
    if event.sender_id != config.ADMIN_ID:
        await event.answer("❌ You don't have permission to refund!", alert=True)
        return
    try:
        payment_id = event.data.decode().split("refund_")[1]
        info       = _payment_data.get(payment_id)
        if not info:
            await event.answer("❌ Payment data not found!", alert=True)
            return

        from telethon.tl.functions.payments import RefundStarsChargeRequest
        result = await Irene(RefundStarsChargeRequest(
            user_id=await Irene.get_input_entity(info["user_id"]),
            charge_id=info["charge_id"],
        ))

        if result:
            await event.edit(
                REFUND_OK_TEXT.format(info["amount"], info["full_name"], info["user_id"]),
                parse_mode="html",
            )
            _payment_data.pop(payment_id, None)
            await event.answer("✅ Refund processed!")
            LOGGER.info(f"Refunded {info['amount']} stars to user {info['user_id']}")
        else:
            await event.answer("❌ Refund failed!", alert=True)
    except Exception as e:
        LOGGER.error(f"donate_refund error: {e}")
        await event.answer("❌ Refund failed!", alert=True)


from telethon.tl.types import UpdateBotPrecheckoutQuery, UpdateBotShippingQuery


@Irene.on(events.Raw(types=UpdateBotPrecheckoutQuery))
async def _pre_checkout(event):
    try:
        from telethon.tl.functions.messages import SetBotPrecheckoutResultsRequest
        await Irene(SetBotPrecheckoutResultsRequest(query_id=event.query_id, success=True, error=None))
    except Exception as e:
        LOGGER.error(f"pre_checkout error: {e}")
        try:
            from telethon.tl.functions.messages import SetBotPrecheckoutResultsRequest
            await Irene(SetBotPrecheckoutResultsRequest(query_id=event.query_id, success=False, error="Payment processing failed."))
        except Exception:
            pass


@Irene.on(events.Raw(types=UpdateBotShippingQuery))
async def _shipping(event):
    try:
        from telethon.tl.functions.messages import SetBotShippingResultsRequest
        await Irene(SetBotShippingResultsRequest(query_id=event.query_id, error=None, shipping_options=[]))
    except Exception as e:
        LOGGER.error(f"shipping_handler error: {e}")


async def handle_successful_payment(event):
    try:
        action    = getattr(event.message, "action", None)
        payment   = action if action else getattr(event.message, "payment_info", None)
        if not payment:
            return

        user_id      = event.sender_id
        chat_id      = event.chat_id
        sender       = await event.get_sender()
        full_name    = f"{sender.first_name or ''} {getattr(sender, 'last_name', '') or ''}".strip() or "Unknown"
        username     = f"@{sender.username}" if getattr(sender, "username", None) else "@N/A"
        total_amount = getattr(payment, "total_amount", 0)
        charge_id    = getattr(payment, "telegram_payment_charge_id", str(uuid.uuid4()))
        payment_id   = str(uuid.uuid4())[:16]

        _payment_data[payment_id] = {
            "user_id": user_id, "full_name": full_name,
            "username": username, "amount": total_amount, "charge_id": charge_id,
        }

        from helpers.botutils import send_message
        await send_message(chat_id, PAYMENT_SUCCESS_TEXT.format(full_name, total_amount, charge_id), parse_mode="html")

        sb = SmartButtons()
        sb.button(text=f"Refund {total_amount} ⭐️", callback_data=f"refund_{payment_id}")
        try:
            await send_message(config.ADMIN_ID, ADMIN_NOTIFY_TEXT.format(full_name, user_id, username, total_amount, charge_id), parse_mode="html", buttons=sb.build_menu(b_cols=1))
        except Exception as e:
            LOGGER.error(f"Failed to notify admin: {e}")
    except Exception as e:
        LOGGER.error(f"handle_successful_payment error: {e}")
