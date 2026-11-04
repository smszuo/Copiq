"""Plain-text output formatting -- no rich, per the CLI startup budget."""
from __future__ import annotations


def truncate(text: str, width: int = 50) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= width else text[: width - 3] + "..."


def print_list(items: list[dict]) -> None:
    print(f"{'ID':<6}{'Time':<10}Content")
    print("-" * 60)
    for item in items:
        time_part = item["createdAt"][11:16]  # HH:MM out of an ISO-8601 string
        print(f"{item['id']:<6}{time_part:<10}{truncate(item['content'])}")


def print_item(item: dict) -> None:
    print(f"ID:      {item['id']}")
    print(f"Time:    {item['createdAt']}")
    print(f"Source:  {item['source']} ({item['clientId']})")
    if item.get("hasPossibleSecret"):
        print("Flagged: possible secret -- use --ack to run AI actions on it")
    print()
    print(item["content"])
