"""Demo for the MultiSelect component.

Run this script to manually exercise the UI. It will build a long list of seasons
and episodes so you can test scrolling, expand/collapse with Right/Left arrows,
toggle selection with Space, and finish with Enter. The resulting selection is
printed to stdout after the curses UI exits.
"""
from multiselect import MultiSelect


def make_items(num_seasons=20, eps_per_season=12):
    items = []
    for s in range(1, num_seasons + 1):
        eps = [f'Episode {e}' for e in range(1, eps_per_season + 1)]
        items.append({'label': f'Season {s}', 'episodes': eps})
    return items


def main():
    items = make_items(num_seasons=30, eps_per_season=15)
    # Demonstrate single-select mode (only one episode or season can be selected)
    ms = MultiSelect(items, title='Single-select demo: pick items')
    selection = ms.run()
    print('\nSelection result:')
    for sel in selection:
        print(sel)


if __name__ == '__main__':
    main()
