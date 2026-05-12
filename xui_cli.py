#!/usr/bin/env python3
import argparse, json
from app.xui import XUIClient

def main():
    p=argparse.ArgumentParser(description='3x-ui API CLI')
    p.add_argument('--host', required=True); p.add_argument('--username', required=True); p.add_argument('--password', required=True); p.add_argument('--web-base-path', default='')
    sp=p.add_subparsers(dest='cmd', required=True)
    c=sp.add_parser('call'); c.add_argument('method'); c.add_argument('path'); c.add_argument('--data', default='{}')
    a=sp.add_parser('add-client'); a.add_argument('--inbound-id', type=int, required=True); a.add_argument('--email', required=True); a.add_argument('--total-gb', type=float, required=True); a.add_argument('--expiry-ms', type=int, required=True); a.add_argument('--comment', default='')
    args=p.parse_args(); cli=XUIClient(args.host,args.username,args.password,args.web_base_path)
    if args.cmd=='call': print(json.dumps(cli.call(args.method,args.path,json=json.loads(args.data)), indent=2))
    else: print(json.dumps(cli.add_client(args.inbound_id,args.email,args.total_gb,args.expiry_ms,args.comment), indent=2))
if __name__=='__main__': main()
