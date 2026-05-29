import argparse

from app.core.security import generate_api_key, hash_api_key
from app.db.repositories import UserRepository
from app.db.session import SessionLocal


def create_api_key(name: str) -> None:
    api_key = generate_api_key()
    with SessionLocal() as session:
        UserRepository(session).create(name=name, api_key_hash=hash_api_key(api_key))
        session.commit()

    print(f"Created API key for {name}:")
    print(api_key)


def main() -> None:
    parser = argparse.ArgumentParser(description="Taskflow Orchestrator admin CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_key_parser = subparsers.add_parser("create-api-key")
    create_key_parser.add_argument("--name", default="demo-user")

    args = parser.parse_args()
    if args.command == "create-api-key":
        create_api_key(args.name)


if __name__ == "__main__":
    main()
