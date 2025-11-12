"""Demo for the SingleSelect component.

Run this script to manually exercise the simple single-item selector.
The chosen item will be printed after the curses UI exits.
"""
from singleselect import SingleSelect


def make_items(n=40):
    return [f"Item {i}" for i in range(1, n + 1)]


def main():
    items = make_items(60)
    ss = SingleSelect(items, title='Single-select demo: pick one item')
    choice = ss.run()
    print('\nSelection result:')
    print(choice)


if __name__ == '__main__':
    main()
