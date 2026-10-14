import json
from unittest.mock import MagicMock

import pytest
import replicate

import app as bot


@pytest.fixture
def client():
    c = MagicMock()
    c.chat_postMessage.return_value = {"ts": "status.ts"}
    return c


def reactions(client, method):
    return [call.kwargs["name"] for call in getattr(client, method).call_args_list]


def test_strip_mention():
    assert bot.strip_mention("<@U123ABC> my 5-year-old self on a beach") == "my 5-year-old self on a beach"


def test_success_posts_image_and_regenerate_button_in_thread(client, monkeypatch):
    monkeypatch.setattr(bot.config, "TRIGGER_WORD", "TOK")  # independent of the local .env
    monkeypatch.setattr(bot.generator, "generate", lambda prompt: b"PNG")
    bot.handle_request(client, "C1", "111.1", "U1", "my 5-year-old self on a beach", source_ts="111.1")

    upload = client.files_upload_v2.call_args.kwargs
    assert upload["file"] == b"PNG" and upload["thread_ts"] == "111.1" and upload["channel"] == "C1"

    buttons_msg = client.chat_postMessage.call_args_list[-1].kwargs
    button = buttons_msg["blocks"][1]["elements"][0]
    assert button["action_id"] == "regenerate"
    assert json.loads(button["value"]) == {"description": "my 5-year-old self on a beach"}
    assert "TOK" in buttons_msg["blocks"][0]["elements"][0]["text"]  # shows the prompt used

    client.chat_delete.assert_called_once_with(channel="C1", ts="status.ts")
    assert reactions(client, "reactions_add") == ["hourglass_flowing_sand", "white_check_mark"]
    assert reactions(client, "reactions_remove") == ["hourglass_flowing_sand"]


def test_failure_shows_friendly_error_and_x_reaction(client, monkeypatch):
    def boom(prompt):
        raise replicate.exceptions.ModelError(MagicMock(error="NSFW content detected"))
    monkeypatch.setattr(bot.generator, "generate", boom)
    bot.handle_request(client, "C1", "111.1", "U1", "something", source_ts="111.1")

    update = client.chat_update.call_args.kwargs
    assert update["ts"] == "status.ts" and "safety filter" in update["text"]
    client.files_upload_v2.assert_not_called()
    assert reactions(client, "reactions_add") == ["hourglass_flowing_sand", "x"]


@pytest.mark.parametrize("text", ["", "help"])
def test_empty_or_help_posts_examples(client, text):
    bot.handle_request(client, "C1", "111.1", "U1", text)
    assert "5-year-old self on a beach" in client.chat_postMessage.call_args.kwargs["text"]
    client.files_upload_v2.assert_not_called()


def test_reaction_failure_does_not_stop_reply(client, monkeypatch):
    monkeypatch.setattr(bot.generator, "generate", lambda prompt: b"PNG")
    client.reactions_add.side_effect = Exception("missing_scope")
    bot.handle_request(client, "C1", "111.1", "U1", "on a beach", source_ts="111.1")
    client.files_upload_v2.assert_called_once()


def test_regenerate_button_reuses_description_in_same_thread(client, monkeypatch):
    calls = []
    monkeypatch.setattr(bot, "handle_request", lambda *a, **k: calls.append(a))
    ack = MagicMock()
    body = {
        "message": {"ts": "222.2", "thread_ts": "111.1"},
        "channel": {"id": "C1"},
        "user": {"id": "U2"},
        "actions": [{"value": json.dumps({"description": "on a beach"})}],
    }
    bot.on_regenerate(ack=ack, body=body, client=client)
    ack.assert_called_once()
    assert calls == [(client, "C1", "111.1", "U2", "on a beach")]


def test_dm_listener_ignores_bot_and_channel_messages(client, monkeypatch):
    calls = []
    monkeypatch.setattr(bot, "handle_request", lambda *a, **k: calls.append(a))
    bot.on_direct_message({"channel_type": "channel", "text": "hi", "ts": "1", "user": "U1", "channel": "C1"}, client)
    bot.on_direct_message({"channel_type": "im", "bot_id": "B1", "text": "hi", "ts": "1", "channel": "D1"}, client)
    assert calls == []
    bot.on_direct_message({"channel_type": "im", "text": "on a beach", "ts": "1", "user": "U1", "channel": "D1"}, client)
    assert calls == [(client, "D1", "1", "U1", "on a beach")]
