"""
chat_history_viewer.py
----------------------
Interactive CLI tool to browse, search, and export chat history from
the Accounting & Legal AI Chatbot SQLite database.

Usage:
    python chat_history_viewer.py                   # Interactive menu
    python chat_history_viewer.py --list            # List all conversations
    python chat_history_viewer.py --search <query>  # Search conversations
    python chat_history_viewer.py --id <conv_id>    # Show specific conversation
    python chat_history_viewer.py --export          # Export all to JSON
    python chat_history_viewer.py --stats           # Show statistics
"""

import sqlite3
import json
import sys
import os
import argparse

# Force UTF-8 output on Windows so emoji/special chars in messages don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime
from pathlib import Path

# ── Database path ─────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = _SCRIPT_DIR / "backend" / "data" / "chatbot.db"

COLORS = {
    "cyan":   "\033[96m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "gray":   "\033[90m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}

def c(color, text):
    """Colorize text for terminal output."""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


# ── Database helpers ──────────────────────────────────────────────────────────

def get_connection():
    if not DB_PATH.exists():
        print(c("red", f"[ERROR] Database not found at: {DB_PATH}"))
        print(c("yellow", "        Make sure the backend has been started at least once."))
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_all_conversations(conn, limit=None, mode=None):
    cursor = conn.cursor()
    sql = """
        SELECT c.id, c.title, c.mode, c.created_at, c.updated_at,
               c.llm_provider, c.llm_model,
               COUNT(m.id) AS msg_count,
               SUM(COALESCE(m.tokens_used, 0)) AS total_tokens
        FROM conversations c
        LEFT JOIN messages m ON c.id = m.conversation_id
    """
    params = []
    if mode:
        sql += " WHERE c.mode = ?"
        params.append(mode)
    sql += " GROUP BY c.id ORDER BY c.created_at DESC"
    if limit:
        sql += f" LIMIT {limit}"
    cursor.execute(sql, params)
    return cursor.fetchall()


def get_conversation_messages(conn, conv_id):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content, created_at, tokens_used, sources
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at
    """, (conv_id,))
    return cursor.fetchall()


def search_conversations(conn, query):
    cursor = conn.cursor()
    q = f"%{query}%"
    cursor.execute("""
        SELECT c.id, c.title, c.mode, c.created_at, c.llm_model,
               COUNT(m.id) AS msg_count
        FROM conversations c
        LEFT JOIN messages m ON c.id = m.conversation_id
        WHERE LOWER(c.title) LIKE LOWER(?)
           OR EXISTS (
               SELECT 1 FROM messages m2
               WHERE m2.conversation_id = c.id
               AND LOWER(m2.content) LIKE LOWER(?)
           )
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """, (q, q))
    return cursor.fetchall()


def get_stats(conn):
    cursor = conn.cursor()
    stats = {}

    cursor.execute("SELECT COUNT(*) FROM conversations;")
    stats["total_conversations"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages;")
    stats["total_messages"] = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(COALESCE(tokens_used, 0)) FROM messages;")
    stats["total_tokens"] = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT mode, COUNT(*) as cnt
        FROM conversations
        GROUP BY mode
        ORDER BY cnt DESC
    """)
    stats["by_mode"] = {row["mode"]: row["cnt"] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT llm_model, COUNT(*) as cnt
        FROM conversations
        WHERE llm_model IS NOT NULL
        GROUP BY llm_model
        ORDER BY cnt DESC
        LIMIT 5
    """)
    stats["top_models"] = [(row["llm_model"], row["cnt"]) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT DATE(created_at) as day, COUNT(*) as cnt
        FROM conversations
        GROUP BY day
        ORDER BY day DESC
        LIMIT 7
    """)
    stats["last_7_days"] = [(row["day"], row["cnt"]) for row in cursor.fetchall()]

    return stats


# ── Display helpers ───────────────────────────────────────────────────────────

def print_separator(char="-", width=80):
    print(c("gray", char * width))


def print_header(title):
    print()
    print(c("cyan", "=" * 80))
    print(c("cyan", f"  {title}"))
    print(c("cyan", "=" * 80))
    print()


def print_conversation_list(convs, title="CONVERSATIONS"):
    print_header(title)
    if not convs:
        print(c("yellow", "  No conversations found."))
        return

    for i, c_row in enumerate(convs, 1):
        title_str = (c_row["title"] or "Untitled")[:55]
        mode_color = {
            "fast": "green", "deep_research": "cyan",
            "analyst": "yellow"
        }.get(c_row["mode"], "gray")

        msg_count = c_row["msg_count"] or 0
        created = (c_row["created_at"] or "")[:16]

        mode_str = c(mode_color, c_row["mode"])
        info_str = c("gray", f"{msg_count} msgs  {created}")
        print(f"  {c('bold', str(i)):>4}.  {title_str:<55} {mode_str:>15}  {info_str}")
    print()


def print_full_conversation(conn, conv_id):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
    conv = cursor.fetchone()

    if not conv:
        print(c("red", f"[ERROR] Conversation {conv_id!r} not found."))
        return

    print_header(f"CONVERSATION: {conv['title'] or 'Untitled'}")
    print(f"  ID:       {c('gray', conv['id'])}")
    print(f"  Mode:     {c('cyan', conv['mode'])}")
    print(f"  Model:    {c('gray', conv['llm_model'] or 'unknown')}")
    print(f"  Provider: {c('gray', conv['llm_provider'] or 'unknown')}")
    print(f"  Created:  {c('gray', (conv['created_at'] or '')[:19])}")
    print()

    messages = get_conversation_messages(conn, conv_id)

    if not messages:
        print(c("yellow", "  (No messages in this conversation)"))
        return

    print(f"  {c('bold', str(len(messages)))} messages\n")
    print_separator()

    for i, msg in enumerate(messages, 1):
        role = msg["role"]
        if role == "user":
            label = c("green", "[USER]")
        elif role == "assistant":
            label = c("cyan", "[ASSISTANT]")
        else:
            label = c("gray", f"[{role.upper()}]")

        ts = (msg["created_at"] or "")[:19]
        tokens = f"  {c('gray', str(msg['tokens_used']) + ' tokens')}" if msg["tokens_used"] else ""
        print(f"\n[{i}] {label}  {c('gray', ts)}{tokens}")
        print_separator("-")
        print(msg["content"])

        # Display sources if present
        raw_sources = msg["sources"]
        if raw_sources:
            sources = raw_sources if isinstance(raw_sources, list) else json.loads(raw_sources)
            if sources:
                print()
                print(c("yellow", f"  📚 Sources ({len(sources)}):"))
                for j, src in enumerate(sources, 1):
                    # Support multiple ingestion metadata keys (original_name, original_filename, filename, source, doc_id)
                    name = (
                        src.get("original_name")
                        or src.get("original_filename")
                        or src.get("filename")
                        or src.get("source")
                        or src.get("doc_id")
                        or "Unknown"
                    )
                    score = src.get("score")
                    domain = src.get("domain", "")
                    score_str = f"  score={score:.3f}" if score is not None else ""
                    domain_str = f"  [{domain}]" if domain else ""
                    print(c("gray", f"    {j}. {name}{domain_str}{score_str}"))

    print()
    print_separator("=")


def print_stats(conn):
    stats = get_stats(conn)

    print_header("DATABASE STATISTICS")

    print(c("bold", "  Overview"))
    print(f"    Total conversations:  {c('cyan', str(stats['total_conversations']))}")
    print(f"    Total messages:       {c('cyan', str(stats['total_messages']))}")
    tokens_str = f"{stats['total_tokens']:,}"
    print(f"    Total tokens used:    {c('cyan', tokens_str)}")
    print()

    print(c("bold", "  Conversations by Mode"))
    for mode, cnt in stats["by_mode"].items():
        bar = "#" * min(cnt, 40)
        print(f"    {mode:20} {c('cyan', str(cnt)):>6}  {c('gray', bar)}")
    print()

    print(c("bold", "  Top Models"))
    for model, cnt in stats["top_models"]:
        print(f"    {(model or 'unknown')[:45]:45} {c('gray', str(cnt))}")
    print()

    print(c("bold", "  Activity (last 7 days)"))
    for day, cnt in stats["last_7_days"]:
        bar = "#" * min(cnt, 40)
        print(f"    {day}  {c('cyan', str(cnt)):>4}  {c('gray', bar)}")
    print()


def export_to_json(conn, output_path=None):
    convs = get_all_conversations(conn)
    output = {
        "export_date": datetime.now().isoformat(),
        "total_conversations": len(convs),
        "conversations": [],
    }

    for conv in convs:
        messages = get_conversation_messages(conn, conv["id"])
        output["conversations"].append({
            "id": conv["id"],
            "title": conv["title"],
            "mode": conv["mode"],
            "provider": conv["llm_provider"],
            "model": conv["llm_model"],
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
            "message_count": len(messages),
            "messages": [
                {
                    "role": m["role"],
                    "content": m["content"],
                    "timestamp": m["created_at"],
                    "tokens_used": m["tokens_used"],
                    "sources": (
                        m["sources"] if isinstance(m["sources"], list)
                        else json.loads(m["sources"]) if m["sources"] else []
                    ),
                }
                for m in messages
            ],
        })

    if output_path is None:
        output_path = str(_SCRIPT_DIR / "chat_history_export.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(c("green", f"\n  ✅ Exported {len(convs)} conversations to:"))
    print(c("gray", f"     {output_path}\n"))


# ── Interactive menu ──────────────────────────────────────────────────────────

def interactive_menu(conn):
    while True:
        print()
        print(c("cyan", "+------------------------------------------+"))
        print(c("cyan", "|  Chat History Viewer                     |"))
        print(c("cyan", "+------------------------------------------+"))
        print(c("cyan", "|  1. List recent conversations (20)       |"))
        print(c("cyan", "|  2. Search conversations                 |"))
        print(c("cyan", "|  3. Open conversation by ID/number       |"))
        print(c("cyan", "|  4. Show statistics                      |"))
        print(c("cyan", "|  5. Filter by mode                       |"))
        print(c("cyan", "|  6. Export all to JSON                   |"))
        print(c("cyan", "|  0. Exit                                 |"))
        print(c("cyan", "+------------------------------------------+"))
        print()

        choice = input(c("bold", "  Enter choice: ")).strip()

        if choice == "0":
            print(c("green", "\n  Goodbye!\n"))
            break

        elif choice == "1":
            convs = get_all_conversations(conn, limit=20)
            print_conversation_list(convs, "RECENT CONVERSATIONS (20)")
            # Let user pick one to open
            pick = input(c("bold", "  Enter number to open (or Enter to skip): ")).strip()
            if pick.isdigit() and 1 <= int(pick) <= len(convs):
                print_full_conversation(conn, convs[int(pick) - 1]["id"])

        elif choice == "2":
            query = input(c("bold", "  Search query: ")).strip()
            if query:
                results = search_conversations(conn, query)
                print_conversation_list(results, f"SEARCH RESULTS: '{query}'")
                if results:
                    pick = input(c("bold", "  Enter number to open (or Enter to skip): ")).strip()
                    if pick.isdigit() and 1 <= int(pick) <= len(results):
                        print_full_conversation(conn, results[int(pick) - 1]["id"])

        elif choice == "3":
            val = input(c("bold", "  Enter conversation ID or list number: ")).strip()
            if val.isdigit():
                convs = get_all_conversations(conn, limit=int(val))
                if convs:
                    print_full_conversation(conn, convs[-1]["id"])
            else:
                print_full_conversation(conn, val)

        elif choice == "4":
            print_stats(conn)

        elif choice == "5":
            print(c("gray", "  Modes: fast, analyst, deep_research"))
            mode = input(c("bold", "  Mode: ")).strip()
            convs = get_all_conversations(conn, mode=mode)
            print_conversation_list(convs, f"CONVERSATIONS — MODE: {mode}")
            if convs:
                pick = input(c("bold", "  Enter number to open (or Enter to skip): ")).strip()
                if pick.isdigit() and 1 <= int(pick) <= len(convs):
                    print_full_conversation(conn, convs[int(pick) - 1]["id"])

        elif choice == "6":
            export_to_json(conn)

        else:
            print(c("yellow", "  Invalid choice, try again."))


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Chat History Viewer — Browse the Accounting & Legal AI Chatbot history"
    )
    parser.add_argument("--list", action="store_true", help="List recent conversations")
    parser.add_argument("--search", metavar="QUERY", help="Search conversations by title or content")
    parser.add_argument("--id", metavar="CONV_ID", help="Show full conversation by ID")
    parser.add_argument("--export", action="store_true", help="Export all conversations to JSON")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--limit", type=int, default=20, help="Number of conversations to list (default: 20)")
    parser.add_argument("--mode", help="Filter by mode: fast, analyst, deep_research")
    parser.add_argument("--db", help="Override database path")

    args = parser.parse_args()

    # Allow DB path override
    if args.db:
        global DB_PATH
        DB_PATH = Path(args.db)

    conn = get_connection()

    try:
        if args.list:
            convs = get_all_conversations(conn, limit=args.limit, mode=args.mode)
            print_conversation_list(convs, f"RECENT CONVERSATIONS ({args.limit})")

        elif args.search:
            results = search_conversations(conn, args.search)
            print_conversation_list(results, f"SEARCH RESULTS: '{args.search}'")

        elif args.id:
            print_full_conversation(conn, args.id)

        elif args.export:
            export_to_json(conn)

        elif args.stats:
            print_stats(conn)

        else:
            # Default: interactive menu
            interactive_menu(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
