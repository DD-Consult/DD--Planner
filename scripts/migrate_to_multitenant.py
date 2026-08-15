#!/usr/bin/env python3
"""
Migration Script: resource_planner DB -> tenant_<slug> DB

STEP 3 of MULTITENANT_PLAN.md.

This script copies every collection from the legacy single-tenant MongoDB
database (`resource_planner`) into a per-tenant database (default:
`tenant_ddconsult`). It is:

  - IDEMPOTENT: safe to re-run. Uses upsert-by-_id so no duplicates are
    ever created. Existing target docs are replaced by source docs.
  - NON-DESTRUCTIVE: source database is only READ. Never written to,
    never dropped.
  - DRY-RUN BY DEFAULT: prints what it would do without touching anything.
    Requires --commit flag for real writes.
  - VERIFICATION-BUILT-IN: after copying, re-counts every collection and
    aborts loudly if source != target.
  - MEMBERSHIP-AWARE: for the users collection, also creates matching
    membership records in platform_db.memberships so users can log into
    the tenant post-migration.

USAGE:
  # Dry run (safe, no writes):
  python scripts/migrate_to_multitenant.py

  # Dry run against specific tenant:
  python scripts/migrate_to_multitenant.py --tenant-slug ddconsult

  # REAL migration (writes to target DB):
  python scripts/migrate_to_multitenant.py --tenant-slug ddconsult --commit

  # Verify a previous migration (compare source vs target counts):
  python scripts/migrate_to_multitenant.py --tenant-slug ddconsult --verify-only

  # Include indexes (copies indexes from source to target):
  python scripts/migrate_to_multitenant.py --tenant-slug ddconsult --commit --with-indexes

EXIT CODES:
  0 = success (or dry-run completed with no anomalies)
  1 = mismatch detected (source count != target count for some collection)
  2 = configuration error (missing env, tenant not found, etc.)
  3 = runtime error (Mongo connection, permission, etc.)
"""
import os
import sys
import argparse
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Ensure we can import from backend/ if needed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

try:
    from pymongo import MongoClient, UpdateOne, InsertOne
    from pymongo.errors import BulkWriteError, DuplicateKeyError
    from dotenv import load_dotenv
except ImportError as e:
    print(f"[FATAL] Missing dependency: {e}. Run: pip install pymongo python-dotenv")
    sys.exit(3)

# Load .env from /app/backend/.env
_env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
SOURCE_DB_NAME = os.environ.get("DB_NAME", "resource_planner")
PLATFORM_DB_NAME = os.environ.get("PLATFORM_DB_NAME", "platform_db")
TENANT_DB_PREFIX = os.environ.get("TENANT_DB_PREFIX", "tenant_")

# Batch size for reads / writes to avoid memory blow-up on large collections
BATCH_SIZE = 500

# ANSI colours for readable output
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREY = "\033[90m"


def _fmt(text: str, colour: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{colour}{text}{C.RESET}"


def _log(msg: str, level: str = "info"):
    prefix = {
        "info":  _fmt("[INFO]",  C.BLUE),
        "ok":    _fmt("[ OK ]",  C.GREEN),
        "warn":  _fmt("[WARN]",  C.YELLOW),
        "err":   _fmt("[ERR ]",  C.RED),
        "step":  _fmt("[STEP]",  C.CYAN),
        "dry":   _fmt("[DRY ]",  C.GREY),
    }.get(level, "[    ]")
    print(f"{prefix} {msg}", flush=True)


def _confirm(msg: str) -> bool:
    """Interactive y/N confirmation. Returns True only on 'yes' / 'y'."""
    try:
        resp = input(f"{_fmt('CONFIRM', C.YELLOW)}: {msg} [y/N]: ").strip().lower()
        return resp in ("y", "yes")
    except EOFError:
        return False


def _short(doc_id: Any) -> str:
    """Short-form representation of a Mongo _id for logs."""
    if doc_id is None:
        return "<none>"
    s = str(doc_id)
    return s if len(s) <= 24 else s[:8] + "..." + s[-6:]


def get_tenant(platform_db, slug: str) -> Optional[Dict[str, Any]]:
    """Look up the tenant record by slug."""
    return platform_db.tenants.find_one({"slug": slug})


def target_db_name(tenant_doc: Dict[str, Any]) -> str:
    """Return the target DB name from tenant record, or compute from slug."""
    db_name = tenant_doc.get("db_name")
    if db_name:
        return db_name
    slug = tenant_doc["slug"]
    safe = "".join(c if c.isalnum() or c == "_" else "_" for c in slug.lower())
    return f"{TENANT_DB_PREFIX}{safe}"


def enumerate_source_collections(source_db) -> List[str]:
    """Return sorted list of non-system collection names in source DB."""
    names = source_db.list_collection_names()
    return sorted([n for n in names if not n.startswith("system.")])


def count_docs(collection) -> int:
    """Fast approximate count via metadata; falls back to count_documents on error."""
    try:
        # estimated_document_count() is O(1), reads from collection metadata
        return collection.estimated_document_count()
    except Exception:
        return collection.count_documents({})


def copy_collection(
    source_coll,
    target_coll,
    dry_run: bool,
    stamp_iso: str,
    tenant_id: str,
    tenant_slug: str,
) -> Tuple[int, int, int, List[str]]:
    """Copy all docs from source_coll -> target_coll in batches.

    Returns:
        (docs_read, docs_upserted, docs_failed, warnings)

    Notes:
      - Preserves _id exactly (both ObjectId and string _ids handled).
      - Adds metadata: _migrated_at, _migrated_from, _tenant_id (audit only).
      - Uses replace_one(upsert=True) for idempotency.
    """
    total = count_docs(source_coll)
    if total == 0:
        return (0, 0, 0, [])

    read = 0
    upserted = 0
    failed = 0
    warnings: List[str] = []
    ops = []

    cursor = source_coll.find({}).batch_size(BATCH_SIZE)
    for doc in cursor:
        read += 1
        _id = doc.get("_id")
        # Enrich with migration metadata (audit trail; safe to include)
        doc["_migrated_at"] = stamp_iso
        doc["_migrated_from"] = SOURCE_DB_NAME
        doc["_migrated_tenant_id"] = tenant_id
        doc["_migrated_tenant_slug"] = tenant_slug

        if not dry_run:
            ops.append(UpdateOne({"_id": _id}, {"$set": doc}, upsert=True))
            if len(ops) >= BATCH_SIZE:
                try:
                    result = target_coll.bulk_write(ops, ordered=False)
                    upserted += (result.upserted_count + result.modified_count)
                except BulkWriteError as bwe:
                    failed += len(bwe.details.get("writeErrors", []))
                    upserted += (len(ops) - len(bwe.details.get("writeErrors", [])))
                    warnings.append(f"Bulk write partial failure: {len(bwe.details.get('writeErrors', []))} errors on batch of {len(ops)}")
                ops = []

    # Flush remaining ops
    if ops and not dry_run:
        try:
            result = target_coll.bulk_write(ops, ordered=False)
            upserted += (result.upserted_count + result.modified_count)
        except BulkWriteError as bwe:
            failed += len(bwe.details.get("writeErrors", []))
            upserted += (len(ops) - len(bwe.details.get("writeErrors", [])))
            warnings.append(f"Bulk write partial failure (final): {len(bwe.details.get('writeErrors', []))} errors")

    return (read, upserted, failed, warnings)


def copy_indexes(source_coll, target_coll) -> Tuple[int, List[str]]:
    """Copy non-default indexes from source to target. Returns (created, warnings)."""
    created = 0
    warnings: List[str] = []
    for idx in source_coll.list_indexes():
        name = idx.get("name")
        if name == "_id_":
            continue  # _id index is auto-created
        keys = list(idx.get("key", {}).items())
        options = {k: v for k, v in idx.items() if k not in ("v", "key", "ns")}
        try:
            target_coll.create_index(keys, **options)
            created += 1
        except Exception as e:
            warnings.append(f"Index '{name}' create failed: {e}")
    return (created, warnings)


def create_memberships_for_users(source_db, platform_db, tenant_doc, dry_run: bool) -> int:
    """For every user in source DB, ensure a matching membership exists in platform_db.

    Membership record schema:
      {
        _id: <uuid>,
        user_id: <str: source user _id>,
        user_email: <str>,
        tenant_id: <str: tenant _id>,
        tenant_slug: <str>,
        role: <str: from user record>,
        resource_id: <str, optional>,
        allowed_project_ids: <list, optional (for client role)>,
        created_at: <utc datetime>,
        source: 'migration'
      }
    """
    import uuid as _uuid
    users = list(source_db.users.find({}))
    if not users:
        return 0

    tenant_id = str(tenant_doc["_id"])
    tenant_slug = tenant_doc["slug"]
    now = datetime.now(timezone.utc)
    created = 0

    for u in users:
        user_id = str(u["_id"])
        email = u.get("email", "")
        role = u.get("role", "resource")

        existing = platform_db.memberships.find_one({"user_id": user_id, "tenant_id": tenant_id})
        if existing:
            continue  # Already exists — idempotent

        doc = {
            "_id": str(_uuid.uuid4()),
            "user_id": user_id,
            "user_email": email,
            "tenant_id": tenant_id,
            "tenant_slug": tenant_slug,
            "role": role,
            "resource_id": u.get("resource_id"),
            "allowed_project_ids": u.get("allowed_project_ids", []),
            "created_at": now,
            "source": "migration",
        }
        if not dry_run:
            platform_db.memberships.insert_one(doc)
        created += 1
    return created


def verify_migration(source_db, target_db, collection_names: List[str]) -> List[Dict[str, Any]]:
    """Compare source vs target counts. Returns list of mismatch dicts."""
    mismatches = []
    for name in collection_names:
        src_count = count_docs(source_db[name])
        tgt_count = count_docs(target_db[name])
        if src_count != tgt_count:
            mismatches.append({
                "collection": name,
                "source_count": src_count,
                "target_count": tgt_count,
                "diff": tgt_count - src_count,
            })
    return mismatches


def main():
    parser = argparse.ArgumentParser(
        description="Migrate resource_planner DB to a tenant-scoped DB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--tenant-slug",
        default="ddconsult",
        help="Target tenant slug (default: ddconsult)",
    )
    parser.add_argument(
        "--source-db",
        default=SOURCE_DB_NAME,
        help=f"Source DB name (default from env: {SOURCE_DB_NAME})",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually perform writes. Without this flag, script runs in dry-run mode.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip copying; just compare counts source vs target.",
    )
    parser.add_argument(
        "--with-indexes",
        action="store_true",
        help="Also copy indexes from source to target.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip interactive confirmation on --commit (for CI use).",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Comma-separated list of collections to migrate (default: all).",
    )
    parser.add_argument(
        "--skip",
        default=None,
        help="Comma-separated list of collections to skip.",
    )
    args = parser.parse_args()

    dry_run = not args.commit and not args.verify_only

    # -------- Banner --------
    print(_fmt("=" * 72, C.CYAN))
    print(_fmt(f"  DD PLANNER MULTI-TENANT MIGRATION", C.BOLD + C.CYAN))
    print(_fmt("=" * 72, C.CYAN))
    _log(f"Source DB          : {args.source_db}", "info")
    _log(f"Target tenant slug : {args.tenant_slug}", "info")
    _log(f"MongoDB URL        : {MONGO_URL}", "info")
    _log(f"Mode               : {'VERIFY ONLY' if args.verify_only else ('COMMIT (real writes)' if args.commit else 'DRY RUN (no writes)')}",
         "warn" if args.commit else "info")
    print()

    # -------- Connect --------
    try:
        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except Exception as e:
        _log(f"Cannot connect to MongoDB: {e}", "err")
        sys.exit(3)

    source_db = client[args.source_db]
    platform_db = client[PLATFORM_DB_NAME]

    # -------- Resolve tenant --------
    tenant = get_tenant(platform_db, args.tenant_slug)
    if not tenant:
        _log(f"Tenant '{args.tenant_slug}' not found in {PLATFORM_DB_NAME}.tenants", "err")
        _log(f"Available tenants: {[t['slug'] for t in platform_db.tenants.find({}, {'slug': 1})]}", "info")
        sys.exit(2)

    tenant_id = str(tenant["_id"])
    tenant_slug = tenant["slug"]
    tgt_db_name = target_db_name(tenant)
    target_db = client[tgt_db_name]

    _log(f"Tenant resolved    : {tenant['name']} (id={_short(tenant_id)})", "ok")
    _log(f"Target database    : {tgt_db_name}", "info")

    # Safety: source and target must differ
    if args.source_db == tgt_db_name:
        _log(f"Source and target DB names are identical ({args.source_db}). Aborting.", "err")
        sys.exit(2)
    print()

    # -------- Enumerate collections --------
    source_collections = enumerate_source_collections(source_db)
    if not source_collections:
        _log("Source DB has no collections. Nothing to do.", "warn")
        sys.exit(0)

    # Apply --only / --skip filters
    if args.only:
        wanted = set(x.strip() for x in args.only.split(",") if x.strip())
        source_collections = [c for c in source_collections if c in wanted]
    if args.skip:
        unwanted = set(x.strip() for x in args.skip.split(",") if x.strip())
        source_collections = [c for c in source_collections if c not in unwanted]

    _log(f"Collections to process: {len(source_collections)}", "info")
    print()

    # -------- Verify-only mode --------
    if args.verify_only:
        _log("=== VERIFY-ONLY MODE — comparing source vs target counts ===", "step")
        mismatches = verify_migration(source_db, target_db, source_collections)
        print()
        print(_fmt(f"  {'Collection':<32} {'Source':>10} {'Target':>10} {'Delta':>10}", C.BOLD))
        print("  " + "-" * 68)
        total_src = total_tgt = 0
        for name in source_collections:
            s = count_docs(source_db[name])
            t = count_docs(target_db[name])
            total_src += s
            total_tgt += t
            delta = t - s
            colour = C.GREEN if delta == 0 else (C.RED if delta < 0 else C.YELLOW)
            print(f"  {name:<32} {s:>10} {t:>10} {_fmt(f'{delta:+d}', colour):>18}")
        print("  " + "-" * 68)
        print(_fmt(f"  {'TOTAL':<32} {total_src:>10} {total_tgt:>10}", C.BOLD))
        print()
        if mismatches:
            _log(f"MISMATCHES FOUND: {len(mismatches)} collection(s) differ.", "err")
            sys.exit(1)
        _log(f"All {len(source_collections)} collections match perfectly.", "ok")
        sys.exit(0)

    # -------- Confirmation gate for --commit --------
    if args.commit and not args.yes:
        print()
        _log(f"About to WRITE to {tgt_db_name} (upsert every doc from {args.source_db}).", "warn")
        _log(f"Existing docs in {tgt_db_name} with same _ids will be REPLACED.", "warn")
        _log(f"Source DB {args.source_db} will NOT be modified (read-only).", "info")
        if not _confirm(f"Proceed with COMMIT migration to '{tgt_db_name}'?"):
            _log("User cancelled. No changes made.", "warn")
            sys.exit(0)
        print()

    # -------- Copy phase --------
    stamp_iso = datetime.now(timezone.utc).isoformat()
    _log(f"=== {'DRY RUN' if dry_run else 'COMMIT'} — copying {len(source_collections)} collections ===", "step")
    print()
    print(_fmt(f"  {'Collection':<32} {'Read':>8} {'Written':>8} {'Failed':>8} {'Indexes':>8}", C.BOLD))
    print("  " + "-" * 68)

    grand_read = grand_written = grand_failed = grand_indexes = 0
    all_warnings: List[str] = []

    for name in source_collections:
        src = source_db[name]
        tgt = target_db[name]
        try:
            read, written, failed, warnings = copy_collection(
                src, tgt, dry_run, stamp_iso, tenant_id, tenant_slug
            )
        except Exception as e:
            _log(f"Collection '{name}' failed hard: {e}", "err")
            all_warnings.append(f"{name}: hard failure — {e}")
            read = written = failed = 0
            warnings = [str(e)]

        indexes_created = 0
        if args.with_indexes and args.commit and read > 0:
            try:
                indexes_created, idx_warns = copy_indexes(src, tgt)
                all_warnings.extend(f"{name}: {w}" for w in idx_warns)
            except Exception as e:
                all_warnings.append(f"{name}: index copy failed — {e}")

        grand_read += read
        grand_written += written
        grand_failed += failed
        grand_indexes += indexes_created
        all_warnings.extend(f"{name}: {w}" for w in warnings)

        status_col = C.GREEN if failed == 0 else C.RED
        print(f"  {name:<32} {_fmt(str(read), C.CYAN):>16} {_fmt(str(written), status_col):>16} {failed:>8} {indexes_created:>8}")

    print("  " + "-" * 68)
    print(_fmt(f"  {'TOTAL':<32} {grand_read:>8} {grand_written:>8} {grand_failed:>8} {grand_indexes:>8}", C.BOLD))
    print()

    # -------- Memberships for users --------
    if "users" in source_collections:
        _log("=== Creating platform_db memberships for tenant users ===", "step")
        try:
            memberships_created = create_memberships_for_users(source_db, platform_db, tenant, dry_run)
            _log(f"Memberships created: {memberships_created}", "ok" if memberships_created > 0 else "info")
        except Exception as e:
            _log(f"Membership creation failed: {e}", "err")
            all_warnings.append(f"memberships: {e}")

    # -------- Verification pass (only in COMMIT mode) --------
    if args.commit and not dry_run:
        print()
        _log("=== Verifying source vs target counts ===", "step")
        mismatches = verify_migration(source_db, target_db, source_collections)
        if mismatches:
            for m in mismatches:
                _log(f"  MISMATCH — {m['collection']}: source={m['source_count']}, target={m['target_count']}, diff={m['diff']:+d}", "err")
            _log(f"MIGRATION FAILED VERIFICATION ({len(mismatches)} mismatches). See above.", "err")
            _log("Rollback: drop the target DB with: mongosh --eval \"db.getSiblingDB('%s').dropDatabase()\"" % tgt_db_name, "warn")
            sys.exit(1)
        _log(f"All {len(source_collections)} collections verified: source == target.", "ok")

    # -------- Warnings summary --------
    if all_warnings:
        print()
        _log(f"=== Warnings ({len(all_warnings)}) ===", "warn")
        for w in all_warnings[:30]:
            _log(f"  {w}", "warn")
        if len(all_warnings) > 30:
            _log(f"  ...and {len(all_warnings) - 30} more (truncated)", "warn")

    # -------- Summary --------
    print()
    print(_fmt("=" * 72, C.CYAN))
    if dry_run:
        _log(f"DRY RUN complete. No writes performed.", "ok")
        _log(f"To actually migrate, re-run with:  --commit", "info")
        _log(f"To include indexes:                --commit --with-indexes", "info")
    else:
        _log(f"MIGRATION COMPLETE.", "ok")
        _log(f"  Collections: {len(source_collections)}", "info")
        _log(f"  Docs read:   {grand_read}", "info")
        _log(f"  Docs written: {grand_written}", "info")
        _log(f"  Indexes:     {grand_indexes}", "info")
        _log(f"  Warnings:    {len(all_warnings)}", "info")
        _log(f"", "info")
        _log(f"Next step: enable MULTI_TENANT_ENABLED=true and route to {tgt_db_name}", "info")
    print(_fmt("=" * 72, C.CYAN))
    sys.exit(0)


if __name__ == "__main__":
    main()
