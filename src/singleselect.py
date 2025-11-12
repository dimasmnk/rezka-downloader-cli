"""Simple terminal single-select component (curses).

Usage:
    from singleselect import SingleSelect

    items = ['one', 'two', 'three']
    ss = SingleSelect(items, title='Pick one')
    choice = ss.run()  # returns the chosen item or None

Controls:
    Up/Down - move
    Enter   - choose
    q / ESC - cancel (returns None)
"""
from __future__ import annotations

import curses
from typing import Any, List, Optional


class SingleSelect:
    def __init__(self, items: List[Any], title: str = "Select") -> None:
        self.items = items
        self.title = title

    def _label_of(self, item: Any) -> str:
        if isinstance(item, dict):
            return str(item.get('label') or item.get('title') or item.get('name') or item)
        return str(item)

    def run(self) -> Optional[Any]:
        try:
            return curses.wrapper(self._curses_main)
        except Exception:
            # If curses is not available or fails, return None
            return None

    def _curses_main(self, stdscr) -> Optional[Any]:
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)

        current = 0
        top = 0

        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()

            # Draw title
            stdscr.addnstr(0, 0, self.title, w - 1, curses.A_BOLD)

            visible_height = max(0, h - 2)

            # Handle empty list
            if not self.items:
                stdscr.addnstr(1, 0, "(no items)", w - 1)
                instr = "Enter: none  q/ESC: cancel"
                stdscr.addnstr(h - 1, 0, instr[: w - 1], w - 1)
                stdscr.refresh()
                key = stdscr.getch()
                if key in (27, ord('q')):
                    return None
                elif key in (curses.KEY_ENTER, 10, 13):
                    return None
                else:
                    continue

            # Ensure current in range
            if current >= len(self.items):
                current = max(0, len(self.items) - 1)
            if current < 0:
                current = 0

            # Adjust top for scrolling
            if current < top:
                top = current
            elif current >= top + visible_height:
                top = current - visible_height + 1

            # Draw visible rows
            for idx in range(top, min(len(self.items), top + visible_height)):
                y = 1 + (idx - top)
                label = self._label_of(self.items[idx])
                line = f"  {label}"
                if idx == current:
                    stdscr.addnstr(y, 0, line, w - 1, curses.A_REVERSE)
                else:
                    stdscr.addnstr(y, 0, line, w - 1)

            # Footer
            instr = "Up/Down: move  Enter: select  q/ESC: cancel"
            stdscr.addnstr(h - 1, 0, instr[: w - 1], w - 1)

            stdscr.refresh()

            key = stdscr.getch()
            if key in (curses.KEY_UP, ord('k')):
                current -= 1
                if current < 0:
                    # wrap to last
                    current = len(self.items) - 1
            elif key in (curses.KEY_DOWN, ord('j')):
                current += 1
                if current >= len(self.items):
                    # wrap to first
                    current = 0
            elif key in (curses.KEY_ENTER, 10, 13):
                return self.items[current]
            elif key in (27, ord('q')):
                return None
