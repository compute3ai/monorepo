#!/usr/bin/env python3
"""
Migrate bot data from SQLite to PostgreSQL.

Handles schema differences:
- Old: context_id (string UUID)
- New: thread_id (FK to threads table)

Creates threads from unique context_ids found in messages.
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from dotenv import load_dotenv
import os

def parse_args():
    parser = argparse.ArgumentParser(description='Migrate bot SQLite to PostgreSQL')
    parser.add_argument('--db', required=True, help='Path to SQLite database file')
    parser.add_argument('--env', required=True, help='Path to .env file with PostgreSQL credentials')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be done without executing')
    return parser.parse_args()


def get_pg_connection(env_path: str):
    """Load .env and create PostgreSQL connection."""
    load_dotenv(env_path)

    import psycopg

    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT', '5432')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    dbname = os.getenv('DB_NAME')
    sslmode = os.getenv('DB_SSLMODE', 'require')

    if not all([host, user, password, dbname]):
        print(f"Error: Missing DB credentials in {env_path}")
        print(f"  DB_HOST={host}, DB_USER={user}, DB_NAME={dbname}")
        sys.exit(1)

    conninfo = f"host={host} port={port} user={user} password={password} dbname={dbname} sslmode={sslmode}"
    return psycopg.connect(conninfo)


def migrate(sqlite_path: str, env_path: str, dry_run: bool = False):
    """Main migration logic."""

    # Connect to SQLite
    print(f"Reading from SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    # Check if threads table exists in SQLite (new schema)
    sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='threads'")
    has_threads_table = sqlite_cur.fetchone() is not None
    print(f"SQLite has threads table: {has_threads_table}")

    # Load users
    sqlite_cur.execute("SELECT * FROM users")
    users = [dict(row) for row in sqlite_cur.fetchall()]
    print(f"Found {len(users)} users")

    # Load messages
    sqlite_cur.execute("SELECT * FROM messages ORDER BY created_at")
    messages = [dict(row) for row in sqlite_cur.fetchall()]
    print(f"Found {len(messages)} messages")

    # Build threads from context_ids (if no threads table)
    threads = []
    context_to_thread = {}  # context_id -> thread dict

    if has_threads_table:
        # Load existing threads
        sqlite_cur.execute("SELECT * FROM threads")
        threads = [dict(row) for row in sqlite_cur.fetchall()]
        for t in threads:
            context_to_thread[t['id']] = t
        print(f"Loaded {len(threads)} existing threads")
    else:
        # Create threads from unique context_ids in messages
        print("Creating threads from context_ids...")

        # Group messages by context_id to find first message (for title) and chat_id
        context_info = {}  # context_id -> {chat_id, first_msg, created_at, updated_at}

        for msg in messages:
            ctx_id = msg.get('context_id')
            if not ctx_id:
                continue

            if ctx_id not in context_info:
                context_info[ctx_id] = {
                    'chat_id': msg['chat_id'],
                    'first_msg': msg['content'] if msg['role'] == 'user' else None,
                    'created_at': msg['created_at'],
                    'updated_at': msg['created_at'],
                }
            else:
                # Update with latest timestamp
                context_info[ctx_id]['updated_at'] = msg['created_at']
                # Set title from first user message if not set
                if not context_info[ctx_id]['first_msg'] and msg['role'] == 'user':
                    context_info[ctx_id]['first_msg'] = msg['content']

        # Also include current_context_id from users (even if no messages yet)
        for user in users:
            ctx_id = user.get('current_context_id')
            if ctx_id and ctx_id not in context_info:
                context_info[ctx_id] = {
                    'chat_id': user['chat_id'],
                    'first_msg': None,
                    'created_at': user.get('created_at') or datetime.utcnow().isoformat(),
                    'updated_at': user.get('created_at') or datetime.utcnow().isoformat(),
                }

        # Create thread objects
        for ctx_id, info in context_info.items():
            title = None
            if info['first_msg']:
                title = info['first_msg'][:50]
                if len(info['first_msg']) > 50:
                    title += '...'

            thread = {
                'id': ctx_id,  # Use context_id as thread_id
                'chat_id': info['chat_id'],
                'title': title,
                'created_at': info['created_at'],
                'updated_at': info['updated_at'],
            }
            threads.append(thread)
            context_to_thread[ctx_id] = thread

        print(f"Created {len(threads)} threads from context_ids")

    sqlite_conn.close()

    if dry_run:
        print("\n=== DRY RUN - Would migrate: ===")
        print(f"  {len(users)} users")
        print(f"  {len(threads)} threads")
        print(f"  {len(messages)} messages")
        return

    # Connect to PostgreSQL
    print(f"\nConnecting to PostgreSQL using {env_path}")
    pg_conn = get_pg_connection(env_path)
    pg_cur = pg_conn.cursor()

    try:
        # Clear existing data (in correct order due to FKs)
        print("Clearing existing data...")
        pg_cur.execute("DELETE FROM messages")
        pg_cur.execute("UPDATE users SET current_thread_id = NULL")
        pg_cur.execute("DELETE FROM threads")
        pg_cur.execute("DELETE FROM users")
        pg_conn.commit()

        # Insert users (without current_thread_id first)
        print("Inserting users...")
        for user in users:
            pg_cur.execute("""
                INSERT INTO users (chat_id, api_key, model, webhook_secret, free, created_at, current_thread_id)
                VALUES (%s, %s, %s, %s, %s, %s, NULL)
            """, (
                user['chat_id'],
                user.get('api_key'),
                user.get('model'),
                user.get('webhook_secret'),
                user.get('free', 0),
                user.get('created_at'),
            ))
        pg_conn.commit()
        print(f"  Inserted {len(users)} users")

        # Insert threads
        print("Inserting threads...")
        for thread in threads:
            pg_cur.execute("""
                INSERT INTO threads (id, chat_id, title, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                thread['id'],
                thread['chat_id'],
                thread.get('title'),
                thread.get('created_at'),
                thread.get('updated_at'),
            ))
        pg_conn.commit()
        print(f"  Inserted {len(threads)} threads")

        # Update users with current_thread_id
        print("Updating user current_thread_id...")
        updated = 0
        for user in users:
            ctx_id = user.get('current_context_id')
            if ctx_id and ctx_id in context_to_thread:
                pg_cur.execute("""
                    UPDATE users SET current_thread_id = %s WHERE chat_id = %s
                """, (ctx_id, user['chat_id']))
                updated += 1
        pg_conn.commit()
        print(f"  Updated {updated} users with current_thread_id")

        # Insert messages (map context_id -> thread_id)
        print("Inserting messages...")
        inserted = 0
        skipped = 0
        for msg in messages:
            ctx_id = msg.get('context_id')

            # Skip context_marker messages (not needed in new schema)
            if msg.get('role') == 'context_marker':
                skipped += 1
                continue

            if not ctx_id or ctx_id not in context_to_thread:
                skipped += 1
                continue

            pg_cur.execute("""
                INSERT INTO messages (chat_id, thread_id, message_id, role, content, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                msg['chat_id'],
                ctx_id,  # thread_id = context_id (we used same ID)
                msg.get('message_id'),
                msg['role'],
                msg['content'],
                msg.get('created_at'),
            ))
            inserted += 1

        pg_conn.commit()
        print(f"  Inserted {inserted} messages, skipped {skipped}")

        print("\n✅ Migration complete!")

    except Exception as e:
        pg_conn.rollback()
        print(f"\n❌ Error during migration: {e}")
        raise
    finally:
        pg_cur.close()
        pg_conn.close()


def main():
    args = parse_args()

    if not os.path.exists(args.db):
        print(f"Error: SQLite database not found: {args.db}")
        sys.exit(1)

    if not os.path.exists(args.env):
        print(f"Error: .env file not found: {args.env}")
        sys.exit(1)

    migrate(args.db, args.env, args.dry_run)


if __name__ == '__main__':
    main()
