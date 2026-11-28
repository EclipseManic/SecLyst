from __future__ import annotations

import argparse
import getpass

from .providers.credentials import CredentialStore


def credentials_command(args: argparse.Namespace) -> int:
    store = CredentialStore()
    if args.action == "status":
        for provider in sorted({*args.providers, "virustotal", "urlscan", "hybrid_analysis", "filescan"}):
            print(f"{provider}: {'configured' if store.configured(provider) else 'not configured'}")
        return 0
    provider = args.provider
    if args.action == "set":
        value = getpass.getpass(f"{provider} credential: ").strip()
        if not value:
            raise SystemExit("Credential cannot be empty.")
        store.set(provider, value)
        print(f"{provider}: configured")
        return 0
    store.remove(provider)
    print(f"{provider}: removed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m seclyst_backend")
    commands = parser.add_subparsers(dest="command", required=True)
    credentials = commands.add_parser("credentials", help="manage provider credentials")
    actions = credentials.add_subparsers(dest="action", required=True)
    status = actions.add_parser("status")
    status.add_argument("providers", nargs="*", default=[])
    for action in ("set", "remove"):
        command = actions.add_parser(action)
        command.add_argument("provider")
    args = parser.parse_args()
    if args.command == "credentials":
        return credentials_command(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
