"""Offline/scheduled feed commands only. No HTTP/MCP service in Phase 1."""
import argparse
import json
import logging
import os
import sys
import psycopg

from .builder import build
from .database import health, migrate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['migrate','build','health'])
    parser.add_argument('--raw-dir',default=os.environ.get('RIGBYS_RAW_DIR','tmp/raw'))
    parser.add_argument('--force-research',action='store_true')
    parser.add_argument('--resume-raw',action='store_true',help='Recover successful public requests from the last 12h')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    dsn=os.environ.get('DATABASE_URL')
    if not dsn:
        parser.error('DATABASE_URL must be set in the environment')
    try:
        with psycopg.connect(dsn,autocommit=True) as conn:
            migrate(conn)
            if args.command=='build':
                result=build(conn,args.raw_dir,args.force_research,args.resume_raw)
            elif args.command=='health':
                result=health(conn)
            else:
                result={'migration_status':'ok'}
            print(json.dumps(result,sort_keys=True))
    except Exception as exc:
        # Never print a connection exception or raw DSN.
        print(json.dumps({'status':'failed','error_type':type(exc).__name__}),file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    sys.exit(main())
