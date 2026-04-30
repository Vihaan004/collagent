import sys

from collagent.session import Session

_BANNER = """\
╭─────────────────────────────────╮
│  Collagent  ·  Canvas Assistant │
│  type 'exit' or Ctrl+C to quit  │
╰─────────────────────────────────╯"""

_DIVIDER = "─" * 40


def main() -> None:
    print(_BANNER)
    session = Session()

    while True:
        print()
        try:
            user_input = input("YOU: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            sys.exit(0)

        if user_input.lower() in {"exit", "quit", "q"}:
            print("Goodbye!")
            sys.exit(0)

        if not user_input:
            continue

        print(_DIVIDER)
        session.send(user_input)
        print(_DIVIDER)


if __name__ == "__main__":
    main()
