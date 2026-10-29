"""Help me chats: the tool loop with Sonnet, kept per site with tokens and cost (N8).

A turn appends the user's message, then asks the model and runs its tool calls until it
ends its turn, refuses, offers choices or reaches the step limit. Each response is
appended with its full content, unchanged, and the history only grows: thinking blocks
are bound to the conversation that produced them. Chats are JSON objects in the source
bucket, next to the site's source zip and outside it (N8-D3), written at the end of
every turn.
"""

import json
from datetime import UTC, datetime
from uuid import uuid4

from ..domain import DomainError
from ..site.store import MOUNT
from .prompt import SYSTEM
from .tools import HelpTools, tool_definitions

MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 16000
MAX_STEPS = 25
BETAS = ["server-side-fallback-2026-07-01"]
SCHEMA = 1
# US dollars per million tokens (Claude API, 2026-10-06). A 5-minute cache write costs
# 1.25 times the input price. Opus 5.5 is listed for refusal fallbacks.
PRICES = {
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.20},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20},
}
USAGE = {
    "input": "input_tokens",
    "output": "output_tokens",
    "cache_write": "cache_creation_input_tokens",
    "cache_read": "cache_read_input_tokens",
}


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def block_dict(block):
    """A response content block as sent back to the API, unchanged."""
    return block if isinstance(block, dict) else block.model_dump(mode="json", exclude_none=True)


def response_cost(model, counts):
    prices = PRICES.get(model)
    if prices is None:
        return None
    return sum(counts[name] * prices[name] for name in USAGE) / 1_000_000


class HelpStore:
    """Chats of a site as JSON objects in the source bucket: `sites/<id>/help/<chat>.json`."""

    def __init__(self, source_store):
        self.storage = source_store.storage

    def node(self, site_id, chat_id=None):
        path = f"{MOUNT}:sites/{site_id}/help"
        return self.storage.node(path + (f"/{chat_id}.json" if chat_id else ""))

    def save(self, chat):
        self.node(chat["site_id"], chat["chat_id"]).write_bytes(
            json.dumps(chat, ensure_ascii=False, sort_keys=True).encode("utf-8")
        )

    def load(self, site_id, chat_id):
        node = self.node(site_id, chat_id)
        if not node.exists():
            raise DomainError("not_found", f"No chat {chat_id}", resource_id=chat_id)
        chat = json.loads(node.read_bytes())
        if chat.get("schema") != SCHEMA or chat.get("site_id") != site_id:
            raise DomainError("conflict", "The chat belongs to another site or schema")
        return chat

    def chats(self, site_id):
        folder = self.node(site_id)
        if not folder.exists():
            return []
        found = [
            self.load(site_id, child.basename.removesuffix(".json")) for child in folder.children()
        ]
        return sorted(found, key=lambda chat: chat["created"])


class HelpService:
    """Help me for the site tab: chats, turns and their cost, as the operator's actions."""

    def __init__(self, sites, store, client, model=MODEL):
        self.sites, self.store, self.client, self.model = sites, store, client, model

    def require(self, identity, site_id, permission):
        if not identity:
            raise DomainError("unauthenticated", "An authenticated principal is required")
        self.sites.policy.require(identity, "site:" + site_id, permission)

    def chats(self, identity, site_id):
        self.require(identity, site_id, "read")
        chats = [summary(chat) for chat in self.store.chats(site_id)]
        total = sum(chat["cost"] or 0 for chat in chats)
        return {"chats": chats, "site_cost": total}

    def chat(self, identity, site_id, chat_id):
        self.require(identity, site_id, "read")
        chat = self.store.load(site_id, chat_id)
        return {**summary(chat), "items": display_items(chat["messages"])}

    def send(self, identity, site_id, text, chat_id=None):
        """Run one turn of a chat (a new one without `chat_id`); returns the chat as shown."""
        if not isinstance(text, str) or not text.strip():
            raise DomainError("invalid_input", "Write a message first")
        self.require(identity, site_id, "write")
        # Help me works under the editing lock of the user who opened it (d-editing-lock).
        self.sites.lock.require(site_id, identity)
        if chat_id is None:
            chat = {
                "schema": SCHEMA,
                "chat_id": uuid4().hex,
                "site_id": site_id,
                "identity": identity,
                "created": now(),
                "title": text.strip()[:60],
                "messages": [],
                "usage": dict.fromkeys(USAGE, 0),
                "cost": 0.0,
            }
        else:
            chat = self.store.load(site_id, chat_id)
        chat["messages"].append({"role": "user", "content": [{"type": "text", "text": text}]})
        try:
            chat["stop"] = self.turn(chat, HelpTools(self.sites, identity, site_id))
        finally:
            self.store.save(chat)
        return {**summary(chat), "items": display_items(chat["messages"])}

    def turn(self, chat, tools):
        for _step in range(MAX_STEPS):
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=[{"type": "text", "text": SYSTEM}],
                tools=tool_definitions(),
                messages=chat["messages"],
                thinking={"type": "adaptive"},
                output_config={"effort": "medium"},
                cache_control={"type": "ephemeral"},
                betas=BETAS,
                fallbacks="default",
            )
            content = [block_dict(block) for block in response.content]
            chat["messages"].append({"role": "assistant", "content": content})
            self.count(chat, response)
            if response.stop_reason != "tool_use":
                return response.stop_reason
            results, offered = [], False
            for block in content:
                if block["type"] != "tool_use":
                    continue
                result, error = tools.run(block["name"], block["input"], block["id"])
                offered = offered or (block["name"] == "offer_choices" and not error)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": result,
                        "is_error": error,
                    }
                )
            # All results of one response go back in one user message.
            chat["messages"].append({"role": "user", "content": results})
            if offered:
                # The user's pick is the next message, merged into this user turn.
                return "choices"
        return "step_limit"

    def count(self, chat, response):
        counts = {name: getattr(response.usage, field, None) or 0 for name, field in USAGE.items()}
        for name, value in counts.items():
            chat["usage"][name] += value
        cost = response_cost(response.model, counts)
        if cost is None or chat["cost"] is None:
            # A model without a known price makes the chat's cost unknown, not wrong.
            chat["cost"] = None
        else:
            chat["cost"] += cost


def summary(chat):
    return {
        "chat_id": chat["chat_id"],
        "title": chat["title"],
        "created": chat["created"],
        "identity": chat["identity"],
        "usage": chat["usage"],
        "cost": chat["cost"],
        "stop": chat.get("stop"),
    }


def display_items(messages):
    """What the chat pane shows: texts, choices and the actions of each turn."""
    items, calls = [], {}
    for message in messages:
        for block in message["content"]:
            kind = block["type"]
            if message["role"] == "user" and kind == "text":
                items.append({"kind": "user", "text": block["text"]})
            elif kind == "text" and block["text"].strip():
                items.append({"kind": "assistant", "text": block["text"]})
            elif kind == "tool_use":
                calls[block["id"]] = block["name"]
            elif kind == "tool_result":
                name = calls.get(block["tool_use_id"], "")
                if name == "offer_choices" and not block["is_error"]:
                    offered = json.loads(block["content"])
                    items.append(
                        {
                            "kind": "choices",
                            "question": offered["question"],
                            "kind_of_choice": offered["kind"],
                            "choices": offered["choices"],
                        }
                    )
                else:
                    items.append({"kind": "action", "name": name, "ok": not block["is_error"]})
    return items
