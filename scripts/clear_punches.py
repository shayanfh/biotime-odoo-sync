"""
clear_punches.py  --  standalone, no third-party dependencies

Delete raw_punches rows whose punch_time falls within a date range,
then print a summary of what remains.

Usage:
    python clear_punches.py --start 2026-06-08 --end 2026-06-09
    python clear_punches.py --start 2026-06-08 --end 2026-06-09 --dry-run
    python clear_punches.py --start 2026-06-08 --end 2026-06-09 --yes
    python clear_punches.py --start 2026-06-08 --end 2026-06-09 --db C:\\path\\to\\sync.db
"""

import sys
import os
import sqlite3


# ── .env reader (no python-dotenv, no re) ─────────────────────────────────────

def load_dotenv(path=".env"):
    try:
        f = open(path)
    except OSError:
        return
    with f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value


# ── argument parser (no argparse) ─────────────────────────────────────────────

def parse_args(argv):
    args = {
        "start": None,
        "end": None,
        "db": None,
        "dry_run": False,
        "yes": False,
    }
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--start" and i + 1 < len(argv):
            i += 1
            args["start"] = argv[i]
        elif a == "--end" and i + 1 < len(argv):
            i += 1
            args["end"] = argv[i]
        elif a == "--db" and i + 1 < len(argv):
            i += 1
            args["db"] = argv[i]
        elif a == "--dry-run":
            args["dry_run"] = True
        elif a == "--yes":
            args["yes"] = True
        elif a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        else:
            print("Unknown argument: " + a)
            sys.exit(1)
        i += 1
    return args


def validate_date(s, name):
    parts = s.split("-")
    if len(parts) != 3:
        print("ERROR: " + name + " must be YYYY-MM-DD, got: " + s)
        sys.exit(1)
    try:
        int(parts[0]); int(parts[1]); int(parts[2])
    except ValueError:
        print("ERROR: " + name + " must be YYYY-MM-DD, got: " + s)
        sys.exit(1)
    return s


def date_le(a, b):
    """Return True if date string a <= b (YYYY-MM-DD comparison is lexicographic)."""
    return a <= b


# ── database helpers ───────────────────────────────────────────────────────────

def open_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def db_path_from_url(url):
    """Extract file path from sqlite:///./sync.db style URL."""
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
        # handle ./sync.db  →  sync.db relative to cwd
        if path.startswith("./"):
            path = path[2:]
        elif path.startswith(".\\"):
            path = path[2:]
        return path
    # not a sqlite URL — return as-is and let sqlite3 fail with a clear message
    return url


def fetch_in_range(conn, start, end):
    cur = conn.execute(
        "SELECT id, biotime_id, emp_code, punch_time, status "
        "FROM raw_punches "
        "WHERE punch_time >= ? AND punch_time <= ? "
        "ORDER BY punch_time",
        (start + " 00:00:00", end + " 23:59:59"),
    )
    return cur.fetchall()


def delete_in_range(conn, start, end):
    cur = conn.execute(
        "DELETE FROM raw_punches "
        "WHERE punch_time >= ? AND punch_time <= ?",
        (start + " 00:00:00", end + " 23:59:59"),
    )
    conn.commit()
    return cur.rowcount


def db_report(conn):
    total = conn.execute("SELECT COUNT(*) FROM raw_punches").fetchone()[0]

    print()
    print("=" * 65)
    print("  DATABASE REPORT — current state")
    print("=" * 65)
    print("  Total records  : " + str(total))

    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM raw_punches "
        "GROUP BY status ORDER BY status"
    ).fetchall()
    if rows:
        print()
        print("  By status:")
        for r in rows:
            status = r[0] if r[0] else "(null)"
            print("    {:<16} {:>6}".format(status, r[1]))

    if total:
        earliest = conn.execute("SELECT MIN(punch_time) FROM raw_punches").fetchone()[0]
        latest   = conn.execute("SELECT MAX(punch_time) FROM raw_punches").fetchone()[0]
        print()
        print("  Earliest punch : " + str(earliest))
        print("  Latest punch   : " + str(latest))

    emp_count = conn.execute(
        "SELECT COUNT(DISTINCT emp_code) FROM raw_punches"
    ).fetchone()[0]
    print("  Employees      : " + str(emp_count))
    print("=" * 65)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

    args = parse_args(sys.argv)

    if not args["start"] or not args["end"]:
        print("ERROR: --start and --end are required.")
        print(__doc__)
        sys.exit(1)

    start = validate_date(args["start"], "--start")
    end   = validate_date(args["end"],   "--end")

    if not date_le(start, end):
        print("ERROR: --start must be before or equal to --end")
        sys.exit(1)

    db_url  = args["db"] or os.environ.get("DATABASE_URL") or "sqlite:///./sync.db"
    db_file = db_path_from_url(db_url)

    if not os.path.isabs(db_file):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_file = os.path.join(script_dir, db_file)

    if not os.path.exists(db_file):
        print("ERROR: database file not found: " + db_file)
        sys.exit(1)

    conn = open_db(db_file)

    try:
        punches = fetch_in_range(conn, start, end)

        print()
        print("=" * 65)
        print("  Range    : " + start + "  ->  " + end)
        print("  Database : " + db_file)
        print("  Found    : " + str(len(punches)) + " punch record(s) in this range")
        if args["dry_run"]:
            print("  Mode     : DRY RUN (nothing will be deleted)")
        print("=" * 65)

        if not punches:
            print()
            print("  Nothing to delete.")
            db_report(conn)
            return

        # print table
        print()
        print("  {:<5} {:<22} {:<15} {:<12} {}".format(
            "#", "punch_time", "emp_code", "status", "biotime_id"
        ))
        print("  " + "-" * 63)
        for i, p in enumerate(punches, 1):
            print("  {:<5} {:<22} {:<15} {:<12} {}".format(
                i, str(p[3]), str(p[2]), str(p[4]), str(p[1])
            ))

        if args["dry_run"]:
            print()
            print("  [DRY RUN] No records were deleted.")
            db_report(conn)
            return

        if not args["yes"]:
            try:
                answer = raw_input if sys.version_info[0] < 3 else input
                answer = answer("\nDelete " + str(len(punches)) + " record(s)? [y/N] ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\nAborted.")
                sys.exit(0)
            if answer != "y":
                print("Aborted.")
                sys.exit(0)

        deleted = delete_in_range(conn, start, end)
        print()
        print("  Deleted " + str(deleted) + " record(s).")

        db_report(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
