"""Reusable terminal multi-select with expandable sublists (curses).

Usage:
    from multiselect import MultiSelect

    items = [
        { 'label': 'Season 1', 'episodes': ['E1', 'E2', 'E3'] },
        { 'label': 'Season 2', 'episodes': ['E1', 'E2'] },
    ]
    ms = MultiSelect(items, title='Choose seasons (Right to open episodes)')
    selection = ms.run()

API:
    MultiSelect(items, title:str)
    run() -> List[dict] where each dict is { 'season': season_label, 'episode': episode_label or None }

Controls:
    Up/Down - move
    Right   - expand season (show episodes)
    Left    - collapse season (hide episodes)
    Space   - toggle selection on focused item
    Enter   - finish and return selection
    q / ESC - cancel (returns empty list)

This component is intentionally dependency-free and uses curses from the stdlib.
"""
from __future__ import annotations

import curses
from typing import Any, Dict, List, Optional, Tuple


class MultiSelect:
    def __init__(self, items: List[Dict[str, Any]], title: str = "Select", multiple: bool = True) -> None:
        # items: list of dicts with 'label' and optional 'episodes' (list)
        self.items = items
        self.title = title
        # allow only one selection when multiple is False
        self.multiple = multiple

        # UI state
        self.expanded = [False] * len(items)
        # selected entries are tuples (season_idx, episode_idx_or_None)
        self.selected: set[Tuple[int, Optional[int]]] = set()

        # build flattened view on demand

    def _build_rows(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for si, it in enumerate(self.items):
            rows.append({
                'type': 'season',
                's_idx': si,
                'e_idx': None,
                'label': str(it.get('label', it.get('title', it.get('name', str(it))))),
            })
            if self.expanded[si]:
                eps = it.get('episodes') or it.get('items') or []
                for ei, ep in enumerate(eps):
                    rows.append({
                        'type': 'episode',
                        's_idx': si,
                        'e_idx': ei,
                        'label': str(ep),
                    })
        return rows

    def _toggle_select(self, s_idx: int, e_idx: Optional[int]) -> None:
        # If toggling a season (e_idx is None) with episodes, toggle all episodes
        # (when multiple selection is allowed). When multiple is False, enforce
        # single-selection: selecting any item clears previous selection and
        # only that item remains selected. For season rows that have episodes,
        # single-select will select the first episode as a convenience.
        eps = self.items[s_idx].get('episodes') or self.items[s_idx].get('items') or []
        if not self.multiple:
            # single-select mode: make the toggled item the only selection
            if e_idx is None:
                if not eps:
                    key = (s_idx, None)
                    if key in self.selected:
                        self.selected.clear()
                    else:
                        self.selected.clear()
                        self.selected.add(key)
                else:
                    # season has episodes: select the first episode
                    key = (s_idx, 0)
                    if key in self.selected:
                        self.selected.clear()
                    else:
                        self.selected.clear()
                        self.selected.add(key)
            else:
                key = (s_idx, e_idx)
                if key in self.selected:
                    self.selected.clear()
                else:
                    self.selected.clear()
                    self.selected.add(key)
            return

        # multiple selection mode (existing behavior)
        if e_idx is None:
            if not eps:
                key = (s_idx, None)
                if key in self.selected:
                    self.selected.remove(key)
                else:
                    self.selected.add(key)
            else:
                # If all eps selected -> unselect all, otherwise select all
                all_selected = all(((s_idx, i) in self.selected) for i in range(len(eps)))
                if all_selected:
                    for i in range(len(eps)):
                        self.selected.discard((s_idx, i))
                else:
                    for i in range(len(eps)):
                        self.selected.add((s_idx, i))
        else:
            key = (s_idx, e_idx)
            if key in self.selected:
                self.selected.remove(key)
            else:
                self.selected.add(key)

    def _toggle_expand(self, s_idx: int) -> None:
        self.expanded[s_idx] = not self.expanded[s_idx]

    def run(self) -> List[Dict[str, Optional[str]]]:
        try:
            return curses.wrapper(self._curses_main)
        except Exception:
            # If curses fails (e.g., running in unsupported terminal), return empty
            return []

    def _curses_main(self, stdscr) -> List[Dict[str, Optional[str]]]:
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)

        current = 0
        top = 0

        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            rows = self._build_rows()

            # Title
            stdscr.addnstr(0, 0, self.title, w - 1, curses.A_BOLD)
            visible_height = h - 2

            # Ensure current in range
            if current >= len(rows):
                current = max(0, len(rows) - 1)
            if current < 0:
                current = 0

            # Adjust top for scrolling
            if current < top:
                top = current
            elif current >= top + visible_height:
                top = current - visible_height + 1

            # Draw rows
            for idx in range(top, min(len(rows), top + visible_height)):
                r = rows[idx]
                y = 1 + (idx - top)

                # Determine marker: season marker should show selected if any episode
                # in that season is selected (or the season key for empty seasons).
                marker = '[ ]'
                if r['type'] == 'season':
                    sidx = r['s_idx']
                    eps = self.items[sidx].get('episodes') or self.items[sidx].get('items') or []
                    if eps:
                        # show tri-state marker: none '[ ]', partial '[-]', all '[x]'
                        selected_count = sum(1 for i in range(len(eps)) if (sidx, i) in self.selected)
                        if selected_count == 0:
                            marker = '[ ]'
                        elif selected_count == len(eps):
                            marker = '[x]'
                        else:
                            marker = '[-]'
                    else:
                        if (sidx, None) in self.selected:
                            marker = '[x]'

                    exp_ch = '+' if not self.expanded[sidx] else '-'
                    label = f"{exp_ch} {r['label']}"
                else:
                    if (r['s_idx'], r['e_idx']) in self.selected:
                        marker = '[x]'
                    label = f"  - {r['label']}"

                line = f"{marker} {label}"

                if idx == current:
                    stdscr.addnstr(y, 0, line, w - 1, curses.A_REVERSE)
                else:
                    stdscr.addnstr(y, 0, line, w - 1)

            # Footer / instructions
            instr = "Up/Down: move  Right: expand  Left: collapse  Space: toggle  a: toggle all  Enter: OK  q/ESC: cancel  [-]=partial"
            stdscr.addnstr(h - 1, 0, instr[: w - 1], w - 1)

            stdscr.refresh()

            key = stdscr.getch()
            if key in (curses.KEY_UP, ord('k')):
                if rows:
                    current -= 1
                    if current < 0:
                        # wrap to last
                        current = len(rows) - 1
                else:
                    current = 0
            elif key in (curses.KEY_DOWN, ord('j')):
                if rows:
                    current += 1
                    if current >= len(rows):
                        # wrap to first
                        current = 0
                else:
                    current = 0
            elif key in (ord('a'), ord('A')):
                # Toggle all items in the list (select all / clear all).
                # Only meaningful in multiple-selection mode. In single-select
                # mode, behave like toggling the focused item.
                if not rows:
                    continue
                if not self.multiple:
                    r = rows[current]
                    self._toggle_select(r['s_idx'], r['e_idx'])
                else:
                    # build set of all possible selectable keys
                    all_keys = set()
                    for s_idx, it in enumerate(self.items):
                        eps = it.get('episodes') or it.get('items') or []
                        if eps:
                            for i in range(len(eps)):
                                all_keys.add((s_idx, i))
                        else:
                            all_keys.add((s_idx, None))

                    if all_keys and all_keys.issubset(self.selected):
                        # all selected -> clear them
                        for k in list(all_keys):
                            self.selected.discard(k)
                    else:
                        # select everything
                        for k in all_keys:
                            self.selected.add(k)
            elif key in (curses.KEY_RIGHT, ):  # expand
                if rows:
                    r = rows[current]
                    if r['type'] == 'season':
                        self.expanded[r['s_idx']] = True
                        # move to first child if exists
                        # rebuild rows and advance current to next row (episode)
                        rows = self._build_rows()
                        # find position of next row corresponding to first episode
                        # scan from current+1
                        if current + 1 < len(rows) and rows[current + 1]['type'] == 'episode':
                            current = current + 1
            elif key in (curses.KEY_LEFT, ):  # collapse
                if rows:
                    r = rows[current]
                    if r['type'] == 'season':
                        self.expanded[r['s_idx']] = False
                    else:
                        # if on episode, move focus to parent season
                        sidx = r['s_idx']
                        # find position of season row for this sidx
                        rows = self._build_rows()
                        for i, rr in enumerate(rows):
                            if rr['type'] == 'season' and rr['s_idx'] == sidx:
                                current = i
                                break
            elif key in (ord(' '),):
                if rows:
                    r = rows[current]
                    self._toggle_select(r['s_idx'], r['e_idx'])
            if key in (curses.KEY_ENTER, 10, 13):
                # return selection as list of dicts grouped by season; if all
                # episodes of a season are selected return a single entry with
                # episode: None, otherwise return per-episode entries.
                out: List[Dict[str, Optional[str]]] = []
                for s_idx, it in enumerate(self.items):
                    season_label = str(it.get('label') or it.get('title') or it.get('name') or s_idx)
                    eps = it.get('episodes') or it.get('items') or []
                    if eps:
                        # Always return per-episode entries for selected episodes.
                        for i, ep in enumerate(eps):
                            if (s_idx, i) in self.selected:
                                out.append({'season': season_label, 'episode': str(ep)})
                    else:
                        if (s_idx, None) in self.selected:
                            out.append({'season': season_label, 'episode': None})
                return out
            elif key in (27, ord('q')):  # ESC or q
                return []

