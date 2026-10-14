"""Down Memory Lane: a Slack bot that turns a description into a childhood photo of you.

Mention the bot (or DM it) with a description, e.g.
    @Down Memory Lane my 5-year-old self on a beach
It replies in the same thread with the generated image and a Regenerate button.
Runs over Socket Mode, so it needs no public URL.
"""
import json
import logging
import re
import time

import replicate
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import config
import generator
from prompts import build_prompt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

# The placeholder token lets tests import this module; a real run requires SLACK_BOT_TOKEN.
app = App(token=config.SLACK_BOT_TOKEN or "xoxb-not-configured",
          token_verification_enabled=bool(config.SLACK_BOT_TOKEN))

MENTION = re.compile(r"<@[A-Z0-9]+>")
REGENERATE_ACTION = "regenerate"
BUTTON_VALUE_LIMIT = 1900  # Slack caps button values at 2000 characters

HELP_TEXT = (
    "Describe the memory you'd like to see, for example:\n"
    "• `my 2-year-old self in my house's backyard`\n"
    "• `my 5-year-old self on a beach`\n"
    "• `my 10-year-old self in a classroom`"
)


def strip_mention(text):
    return MENTION.sub("", text or "").strip()


def friendly_error(error):
    """Plain-language message for a failed generation."""
    text = str(error).lower()
    if "nsfw" in text or "safety" in text:
        return "That description was blocked by the image safety filter. Please try a different one."
    if isinstance(error, replicate.exceptions.ModelError):
        return "The image model couldn't create that one. Please try again or rephrase it."
    return "Something went wrong while creating your image. Please try again in a moment."


def result_blocks(description, prompt, seconds):
    """Caption + Regenerate button posted under the image."""
    return [
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"*Prompt used:* {prompt}\n_Created in {seconds:.0f}s_"},
        ]},
        {"type": "actions", "elements": [{
            "type": "button",
            "action_id": REGENERATE_ACTION,
            "text": {"type": "plain_text", "text": "🔄 Regenerate"},
            "value": json.dumps({"description": description[:BUTTON_VALUE_LIMIT]}),
        }]},
    ]


def set_reaction(client, channel, ts, remove=None, add=None):
    """Swap status emoji on the user's message; never let a reaction failure stop the reply."""
    for method, name in ((client.reactions_remove, remove), (client.reactions_add, add)):
        if name:
            try:
                method(channel=channel, timestamp=ts, name=name)
            except Exception as e:  # e.g. already_reacted, missing scope
                log.warning("reaction %s failed: %s", name, e)


def handle_request(client, channel, thread_ts, user, description, source_ts=None):
    """Generate an image for `description` and post it in the thread.

    `source_ts` is the user's own message; it gets ⏳ while working and ✅/❌ after.
    """
    if not description or description.lower() in ("help", "hi", "hello"):
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=HELP_TEXT)
        return

    prompt = build_prompt(description, config.TRIGGER_WORD)
    log.info("user=%s description=%r prompt=%r", user, description, prompt)

    if source_ts:
        set_reaction(client, channel, source_ts, add="hourglass_flowing_sand")
    status = client.chat_postMessage(
        channel=channel, thread_ts=thread_ts,
        text="Creating your memory… ⏳ This usually takes 20–40 seconds.",
    )

    started = time.monotonic()
    try:
        image = generator.generate(prompt)
    except Exception as e:
        log.exception("generation failed")
        client.chat_update(channel=channel, ts=status["ts"], text=f"⚠️ {friendly_error(e)}")
        if source_ts:
            set_reaction(client, channel, source_ts, remove="hourglass_flowing_sand", add="x")
        return
    seconds = time.monotonic() - started

    client.files_upload_v2(
        channel=channel, thread_ts=thread_ts,
        file=image, filename="memory.png", title=description[:250],
        alt_txt=description[:1000],
        initial_comment=f"<@{user}> here's your memory: _{description}_",
    )
    client.chat_postMessage(
        channel=channel, thread_ts=thread_ts,
        text="Want another take?", blocks=result_blocks(description, prompt, seconds),
    )
    client.chat_delete(channel=channel, ts=status["ts"])
    if source_ts:
        set_reaction(client, channel, source_ts, remove="hourglass_flowing_sand", add="white_check_mark")


# --- Slack listeners ------------------------------------------------------------
# Bolt acknowledges events before running listeners, so slow generation is fine here.

@app.event("app_mention")
def on_mention(event, client):
    handle_request(
        client, event["channel"], event.get("thread_ts") or event["ts"],
        event["user"], strip_mention(event.get("text")), source_ts=event["ts"],
    )


@app.event("message")
def on_direct_message(event, client):
    # Only plain user messages in a DM; skip edits, bot messages and channel chatter.
    if event.get("channel_type") != "im" or event.get("subtype") or event.get("bot_id"):
        return
    handle_request(
        client, event["channel"], event.get("thread_ts") or event["ts"],
        event["user"], strip_mention(event.get("text")), source_ts=event["ts"],
    )


@app.action(REGENERATE_ACTION)
def on_regenerate(ack, body, client):
    ack()  # buttons must be acknowledged within 3 seconds
    message = body["message"]
    description = json.loads(body["actions"][0]["value"])["description"]
    handle_request(
        client, body["channel"]["id"], message.get("thread_ts") or message["ts"],
        body["user"]["id"], description,
    )


if __name__ == "__main__":
    config.require("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "REPLICATE_API_TOKEN", "REPLICATE_MODEL")
    log.info("Using model %s", generator.model_ref())
    SocketModeHandler(app, config.SLACK_APP_TOKEN).start()
