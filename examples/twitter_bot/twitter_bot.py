#!/usr/bin/env python3
"""OpenJarvis Twitter Bot — @OpenJarvisAI reactive mention handler.

Listens for @mentions and responds: answers questions, creates GitHub issues
for bugs/feature requests, acknowledges praise, ignores spam. Like @grok.

Usage:
    python examples/twitter_bot/twitter_bot.py --demo
    python examples/twitter_bot/twitter_bot.py --live
    python examples/twitter_bot/twitter_bot.py --live --index-docs
"""

from __future__ import annotations

import signal
import sys
import threading

import click

DEMO_TWEETS = [
    {
        "id": "1000000000000000001",
        "author": "alice_dev",
        "text": "@OpenJarvisAI how do I add a new channel integration?",
    },
    {
        "id": "1000000000000000002",
        "author": "bob_user",
        "text": "@OpenJarvisAI bug: the memory_search tool crashes when the index is empty",
    },
    {
        "id": "1000000000000000003",
        "author": "carol_eng",
        "text": "@OpenJarvisAI it would be great to have a built-in scheduler UI",
    },
    {
        "id": "1000000000000000004",
        "author": "dave_fan",
        "text": "@OpenJarvisAI just discovered this project, absolutely love it!",
    },
    {
        "id": "1000000000000000005",
        "author": "spambot99",
        "text": "@OpenJarvisAI BUY CRYPTO NOW 🚀🚀🚀 LINK IN BIO",
    },
]

# Voice rules included in every per-call prompt so the model always sees them
_VOICE = (
    "Rules for your reply:\n"
    "- all lowercase. no capitalization.\n"
    "- <=280 characters.\n"
    "- no emojis. no hashtags.\n"
    "- casual and direct, like a dev helping another dev.\n"
    "- do not invent URLs, issue numbers, stats, or commands.\n"
    "- use facts from memory_search results. never say 'no info found'.\n"
)


def _build_question_prompt(author: str, tweet_id: str, text: str) -> str:
    return (
        "You are @OpenJarvisAI. Someone asked a question.\n\n"
        f"Tweet from @{author} (tweet ID: {tweet_id}):\n"
        f'"{text}"\n\n'
        "1. call memory_search to find the answer.\n"
        "2. memory_search WILL return results — use them. the results "
        "contain the real answer. never say 'no info found' or 'check the docs' "
        "— the answer is in the search results. compose your reply from "
        "the facts returned.\n"
        f'3. call channel_send with conversation_id="{tweet_id}".\n\n'
        + _VOICE
    )


def _build_bug_prompt(author: str, tweet_id: str, text: str) -> str:
    return (
        "You are @OpenJarvisAI. Someone reported a bug.\n\n"
        f"Tweet from @{author} (tweet ID: {tweet_id}):\n"
        f'"{text}"\n\n'
        "1. call http_request to create a github issue:\n"
        "   url: https://api.github.com/repos/open-jarvis/OpenJarvis/issues\n"
        "   method: POST\n"
        '   headers: {"Authorization": "Bearer $GITHUB_TOKEN", '
        '"Accept": "application/vnd.github+json"}\n'
        f'   body: {{"title": "<short title>", "body": "reported via twitter '
        f"by @{author}: {text}\", "
        '"labels": ["bug", "from-twitter"]}}\n'
        f'2. call channel_send with conversation_id="{tweet_id}" and a short '
        "reply like: \"opened an issue for this — we'll look into it. "
        'thanks for the report"\n\n'
        "do NOT include a github issue URL in your reply — you don't know "
        "the issue number yet.\n\n"
        + _VOICE
    )


def _build_feature_prompt(author: str, tweet_id: str, text: str) -> str:
    return (
        "You are @OpenJarvisAI. Someone requested a feature.\n\n"
        f"Tweet from @{author} (tweet ID: {tweet_id}):\n"
        f'"{text}"\n\n'
        "1. call http_request to create a github issue:\n"
        "   url: https://api.github.com/repos/open-jarvis/OpenJarvis/issues\n"
        "   method: POST\n"
        f'   body: {{"title": "feature request: <title>", "body": "requested '
        f"via twitter by @{author}: {text}\", "
        '"labels": ["enhancement", "from-twitter"]}}\n'
        f'2. call channel_send with conversation_id="{tweet_id}" and a short '
        "reply like: \"love this idea — opened an issue to track it\"\n\n"
        "do NOT include a github issue URL in your reply — you don't know "
        "the issue number yet.\n\n"
        + _VOICE
    )


def _build_praise_prompt(author: str, tweet_id: str, text: str) -> str:
    return (
        "You are @OpenJarvisAI. Someone said something nice.\n\n"
        f"Tweet from @{author} (tweet ID: {tweet_id}):\n"
        f'"{text}"\n\n'
        f'call channel_send with conversation_id="{tweet_id}" and a genuine, '
        "short thank-you. be real, not corporate.\n\n"
        + _VOICE
    )


def _classify_mention(text: str) -> str:
    """Simple keyword-based classification to avoid wasting a model turn."""
    lower = text.lower()
    if any(w in lower for w in ["bug:", "bug ", "crash", "error", "fails", "broken", "segfault"]):
        return "BUG_REPORT"
    if any(w in lower for w in ["feature", "would love", "would be great", "wish", "please add", "can you add", "any plans"]):
        return "FEATURE_REQUEST"
    if any(w in lower for w in ["love", "amazing", "awesome", "impressed", "great work", "switched from", "incredible"]):
        return "PRAISE"
    if any(w in lower for w in ["buy", "crypto", "income", "free download", "link in bio", "10x", "guaranteed"]):
        return "SPAM"
    return "QUESTION"


def _run_demo(model: str, engine_key: str) -> None:
    """Process sample mentions through the agent without Twitter API access."""
    try:
        from openjarvis import Jarvis
    except ImportError:
        click.echo(
            "Error: openjarvis is not installed. "
            "Install it with:  uv sync --extra dev",
            err=True,
        )
        sys.exit(1)

    click.echo("OpenJarvis Twitter Bot — Demo Mode (reactive only)")
    click.echo(f"Model: {model}  |  Engine: {engine_key}")
    click.echo("=" * 60)
    click.echo(f"Processing {len(DEMO_TWEETS)} sample mentions...\n")

    try:
        j = Jarvis(model=model, engine_key=engine_key)
    except Exception as exc:
        click.echo(
            f"Error: could not initialize Jarvis — {exc}\n\n"
            "Make sure your engine is running. For Ollama:\n"
            "  ollama serve\n"
            "  ollama pull qwen3:32b\n\n"
            "For cloud engines, ensure API keys are set in your .env file.",
            err=True,
        )
        sys.exit(1)

    try:
        for idx, tweet in enumerate(DEMO_TWEETS, 1):
            mention_type = _classify_mention(tweet["text"])
            click.echo(
                f"  [{idx}/{len(DEMO_TWEETS)}] [{mention_type}] @{tweet['author']}: "
                f"{tweet['text'][:60]}...",
            )

            if mention_type == "SPAM":
                click.echo("           -> [ignored]")
                click.echo()
                continue

            if mention_type == "QUESTION":
                prompt = _build_question_prompt(tweet["author"], tweet["id"], tweet["text"])
                tools = ["memory_search", "channel_send"]
            elif mention_type == "BUG_REPORT":
                prompt = _build_bug_prompt(tweet["author"], tweet["id"], tweet["text"])
                tools = ["http_request", "channel_send"]
            elif mention_type == "FEATURE_REQUEST":
                prompt = _build_feature_prompt(tweet["author"], tweet["id"], tweet["text"])
                tools = ["http_request", "channel_send"]
            else:
                prompt = _build_praise_prompt(tweet["author"], tweet["id"], tweet["text"])
                tools = ["channel_send"]

            response = j.ask(
                prompt,
                agent="orchestrator",
                tools=tools,
                temperature=0.4,
            )
            click.echo(f"           -> {response[:120]}")
            click.echo()
    except Exception as exc:
        click.echo(f"Error during processing: {exc}", err=True)
        sys.exit(1)
    finally:
        j.close()

    click.echo("Demo complete.")


def _index_docs(j) -> None:  # noqa: ANN001
    """Pre-index docs/ and README.md into memory for RAG."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    docs_dir = root / "docs"
    readme = root / "README.md"

    files_to_index: list[pathlib.Path] = []
    if readme.exists():
        files_to_index.append(readme)
    if docs_dir.is_dir():
        files_to_index.extend(sorted(docs_dir.rglob("*.md")))

    if not files_to_index:
        click.echo("No docs found to index.")
        return

    click.echo(f"Indexing {len(files_to_index)} doc files into memory...")
    for fpath in files_to_index:
        try:
            text = fpath.read_text(encoding="utf-8")
            chunk_size = 2000
            for i in range(0, len(text), chunk_size):
                chunk = text[i : i + chunk_size]
                j.ask(
                    f"Store this documentation excerpt from {fpath.name}:\n\n{chunk}",
                    agent="orchestrator",
                    tools=["memory_store"],
                    temperature=0.1,
                )
        except Exception as exc:
            click.echo(f"  Warning: could not index {fpath.name}: {exc}")
    click.echo("Indexing complete.\n")


def _run_live(model: str, engine_key: str, index_docs: bool) -> None:
    """Connect to Twitter and handle mentions in real time."""
    try:
        from openjarvis import Jarvis
        from openjarvis.channels.twitter_channel import TwitterChannel
    except ImportError:
        click.echo(
            "Error: openjarvis is not installed. "
            "Install it with:  uv sync --extra dev",
            err=True,
        )
        sys.exit(1)

    click.echo("OpenJarvis Twitter Bot — Live Mode (reactive only)")
    click.echo(f"Model: {model}  |  Engine: {engine_key}")
    click.echo("=" * 60)

    try:
        j = Jarvis(model=model, engine_key=engine_key)
    except Exception as exc:
        click.echo(f"Error: could not initialize Jarvis — {exc}", err=True)
        sys.exit(1)

    if index_docs:
        _index_docs(j)

    channel = TwitterChannel()
    channel.connect()

    if channel.status().value == "error":
        click.echo(
            "Error: could not connect to Twitter.\n"
            "Ensure these env vars are set:\n"
            "  TWITTER_BEARER_TOKEN\n"
            "  TWITTER_API_KEY / TWITTER_API_SECRET\n"
            "  TWITTER_ACCESS_TOKEN / TWITTER_ACCESS_SECRET\n"
            "  TWITTER_BOT_USER_ID",
            err=True,
        )
        j.close()
        sys.exit(1)

    click.echo("Connected to Twitter. Listening for @mentions...")
    click.echo("Press Ctrl+C to stop.\n")

    def _handle_mention(msg):  # noqa: ANN001
        """Process an incoming mention through the agent."""
        mention_type = _classify_mention(msg.content)
        click.echo(f"  [{mention_type}] @{msg.sender}: {msg.content[:80]}")

        if mention_type == "SPAM":
            click.echo("  -> [ignored]\n")
            return

        if mention_type == "QUESTION":
            prompt = _build_question_prompt(msg.sender, msg.message_id, msg.content)
            tools = ["memory_search", "channel_send"]
        elif mention_type == "BUG_REPORT":
            prompt = _build_bug_prompt(msg.sender, msg.message_id, msg.content)
            tools = ["http_request", "channel_send"]
        elif mention_type == "FEATURE_REQUEST":
            prompt = _build_feature_prompt(msg.sender, msg.message_id, msg.content)
            tools = ["http_request", "channel_send"]
        else:
            prompt = _build_praise_prompt(msg.sender, msg.message_id, msg.content)
            tools = ["channel_send"]

        try:
            response = j.ask(
                prompt,
                agent="orchestrator",
                tools=tools,
                temperature=0.4,
            )
            click.echo(f"  -> {response[:120]}\n")
        except Exception as exc:
            click.echo(f"  Error processing mention: {exc}")

    channel.on_message(_handle_mention)

    # Block until interrupted
    stop = threading.Event()

    def _signal_handler(sig, frame):  # noqa: ANN001
        click.echo("\nShutting down...")
        stop.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    stop.wait()

    channel.disconnect()
    j.close()
    click.echo("Stopped.")


@click.command()
@click.option(
    "--model",
    default="qwen3:32b",
    show_default=True,
    help="Model to use for mention handling.",
)
@click.option(
    "--engine",
    "engine_key",
    default="ollama",
    show_default=True,
    help="Engine backend (ollama, cloud, vllm, etc.).",
)
@click.option(
    "--demo",
    is_flag=True,
    default=False,
    help="Run in demo mode with sample mentions (no Twitter API required).",
)
@click.option(
    "--live",
    is_flag=True,
    default=False,
    help="Run in live mode, polling Twitter for real mentions.",
)
@click.option(
    "--index-docs",
    is_flag=True,
    default=False,
    help="Pre-index docs/ and README.md into memory before starting.",
)
def main(
    model: str,
    engine_key: str,
    demo: bool,
    live: bool,
    index_docs: bool,
) -> None:
    """OpenJarvis Twitter bot — reactive @OpenJarvisAI mention handler.

    Polls for @mentions, classifies them (question, bug, feature request,
    praise, spam), and responds appropriately — including creating GitHub
    issues for bug reports and feature requests. Similar to how @grok works.

    \b
    Demo mode (no Twitter credentials needed):
        python examples/twitter_bot/twitter_bot.py --demo

    \b
    Live mode (requires Twitter + GitHub credentials):
        python examples/twitter_bot/twitter_bot.py --live
        python examples/twitter_bot/twitter_bot.py --live --index-docs
    """
    if demo:
        _run_demo(model, engine_key)
    elif live:
        _run_live(model, engine_key, index_docs)
    else:
        click.echo(
            "Please specify --demo or --live mode.\n"
            "Run with --help for usage details.",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
