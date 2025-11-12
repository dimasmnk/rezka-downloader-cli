import sys
import logging
import json
import getpass
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
import os
import signal

from pypdl import Pypdl
from HdRezkaApi import HdRezkaApi
from HdRezkaApi.types import TVSeries, Movie
from multiselect import MultiSelect
from singleselect import SingleSelect
from helper import choose_preferred_quality, get_session_file, save_session, load_session


def _sanitize_filename(name: str) -> str:
    # very small sanitizer
    return name.replace('/', '_').replace('\\', '_').strip()


def _get_content_length(url: str, timeout: float = 5.0) -> Optional[int]:
    """Try to determine the size (in bytes) of a remote resource.

    Attempts a HEAD request first. If Content-Length isn't present, falls
    back to a ranged GET to obtain Content-Range which contains the total
    size. Returns None if size cannot be determined.
    """
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout)
        if resp.status_code >= 200 and resp.status_code < 400:
            cl = resp.headers.get('Content-Length')
            if cl and cl.isdigit():
                return int(cl)
    except Exception:
        # ignore and try ranged GET
        pass

    # Some servers don't respond properly to HEAD. Try a ranged GET to
    # provoke a Content-Range header like: 'bytes 0-0/12345'
    try:
        headers = {'Range': 'bytes=0-0'}
        resp = requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=timeout)
        # Prefer Content-Range
        cr = resp.headers.get('Content-Range')
        if cr:
            # format: bytes 0-0/12345
            parts = cr.split('/')
            if len(parts) == 2 and parts[1].isdigit():
                return int(parts[1])
        # fallback to Content-Length from the ranged response
        cl = resp.headers.get('Content-Length')
        if cl and cl.isdigit():
            return int(cl)
    except Exception:
        pass

    return None


def _choose_translator_interactive(translators: Dict[int, Dict[str, Any]]):
    # translators: {id: {name, premium}}
    items = []
    for tid, info in translators.items():
        items.append({'id': tid, 'label': info.get('name', str(tid)), 'premium': info.get('premium', False)})

    ss = SingleSelect(items, title='Choose translator')
    choice = ss.run()
    if choice:
        return choice['id']

    # fallback: simple console input
    print("Translators:")
    list_items = list(items)
    for i, it in enumerate(list_items, start=1):
        print(f"{i}. {it['label']} (id={it['id']})")
    sel = input("Choose translator by number (or id): ").strip()
    if not sel:
        return None
    # try numeric index
    if sel.isdigit():
        si = int(sel)
        # if matches index
        if 1 <= si <= len(list_items):
            return list_items[si - 1]['id']
        # else maybe direct id
        return int(sel)
    # try matching by name
    for it in list_items:
        if it['label'] == sel:
            return it['id']
    return None


def _choose_seasons_episodes_interactive(series_info_for_translator: Dict[str, Any]):
    # series_info_for_translator contains 'seasons' and 'episodes' maps
    seasons = series_info_for_translator.get('seasons', {})
    episodes = series_info_for_translator.get('episodes', {})

    # Build items for MultiSelect
    items = []
    for s_num in sorted(seasons.keys()):
        season_label = seasons[s_num]
        eps = episodes.get(s_num, {})
        # Use episode text as label
        eps_list = [eps[e] for e in sorted(eps.keys())]
        items.append({'label': season_label, 'episodes': eps_list})

    ms = MultiSelect(items, title='Choose episodes (Right to open season)')
    selection = ms.run()
    if selection:
        # Map selection back to numeric season/episode ids
        chosen = []
        for sel in selection:
            # sel: {'season': season_label, 'episode': episode_text or None}
            season_label = sel.get('season')
            episode_text = sel.get('episode')
            # find season number
            s_num = next((k for k, v in seasons.items() if v == season_label), None)
            if s_num is None:
                continue
            if episode_text is None:
                # no episodes in this season (shouldn't normally happen) -> skip
                continue
            # find episode number by text
            eps_map = episodes.get(s_num, {})
            ep_num = next((k for k, v in eps_map.items() if v == episode_text), None)
            if ep_num is None:
                continue
            chosen.append((int(s_num), int(ep_num)))
        return chosen

    # fallback: user likely ran in non-curses terminal; download all episodes for this translator
    print("No interactive selection made; defaulting to all episodes for this translator.")
    chosen_all = []
    for s_num in sorted(seasons.keys()):
        for e_num in sorted(episodes.get(s_num, {}).keys()):
            chosen_all.append((int(s_num), int(e_num)))
    return chosen_all


def main():
    if len(sys.argv) < 2:
        print("Please provide one argument <url> or use 'login' to authenticate")
        sys.exit(1)

    # Special separated command: `login` will perform an interactive login and
    # store the session cookies for later use by the main flow.
    # Usage: python downloader.py login [base_url]
    if sys.argv[1] == 'login':
        base = sys.argv[2] if len(sys.argv) > 2 else 'https://hdrezka.ag/'
        login = input('Login: ').strip()
        pwd = getpass.getpass('Password: ')
        if not login:
            print('No login provided. Aborting.')
            sys.exit(1)

        print('Logging in...')
        try:
            rezka = HdRezkaApi(base)
            # try to call login (implementation provided by HdRezkaApi)
            # Some versions may raise on failure or return False.
            res = rezka.login(login, pwd)
        except Exception as e:
            print(f'Login failed: {e}')
            sys.exit(2)

        # Try to extract cookies from the HdRezkaApi instance in a few ways
        cookies: Optional[Dict[str, str]] = None
        try:
            if hasattr(rezka, 'cookies') and isinstance(rezka.cookies, dict):
                cookies = rezka.cookies
            elif hasattr(rezka, 'session'):
                sess = getattr(rezka, 'session')
                if hasattr(sess, 'cookies'):
                    try:
                        cookies = {k: v for k, v in sess.cookies.items()}
                    except Exception:
                        cookies = None
        except Exception:
            cookies = None

        if not cookies:
            # If we could not find cookies, but login indicated success, try
            # to ask HdRezkaApi to provide them via make_cookies helper if
            # available (some versions expose make_cookies). Otherwise warn and
            # exit.
            if hasattr(HdRezkaApi, 'make_cookies'):
                try:
                    # Some APIs expect a user-id/password-hash; best-effort
                    cookies = HdRezkaApi.make_cookies(login, pwd)
                except Exception:
                    cookies = None

        if not cookies:
            print('Could not obtain session cookies after login. Stored session not created.')
            sys.exit(3)

        # Persist session into user's folder `~/rezka-downloader-cli`
        try:
            path = save_session(cookies)
            print(f'Session saved to {path}')
            sys.exit(0)
        except Exception as e:
            print(f'Failed to save session: {e}')
            sys.exit(4)

    url = sys.argv[1]
    print(f"URL: {url}")

    # If a saved session exists, pass cookies into HdRezkaApi so premium
    # qualities available only to logged-in users can be used. We keep this
    # separate from the `login` command so the main flow remains unchanged.
    rezka = None
    try:
        cookies = load_session()
        if cookies:
            rezka = HdRezkaApi(url, cookies=cookies)
    except Exception:
        rezka = None

    if rezka is None:
        rezka = HdRezkaApi(url)

    # 2. Get translators
    translators = rezka.translators
    if not translators:
        print("No translators found for this title.")
        sys.exit(1)

    # 3. Ask what translator
    translator_id = _choose_translator_interactive(translators)
    if translator_id is None:
        print("No translator chosen. Exiting.")
        sys.exit(1)

    print(f"Selected translator id: {translator_id}")

    # Prepare downloader
    disabled_logger = logging.getLogger('pypdl_disabled')
    disabled_logger.disabled = True
    # allow_reuse=True so we can call .start() multiple times without the
    # internal event loop shutting down after the first download
    dl = Pypdl(allow_reuse=True, logger=disabled_logger)

    # Track temporary files for in-progress downloads so we can clean them
    # up if the process is cancelled part-way through.
    current_temp_files = set()

    # Cleanup helper used by signal handlers and finalizers. Keeps logic in
    # one place so behavior is consistent for KeyboardInterrupt and signals.
    def _cleanup_and_exit(signame: Optional[str] = None):
        try:
            dl.shutdown()
        except Exception:
            pass

        # First, try to remove any temp files we explicitly tracked. pypdl
        # may create multiple segment files named like '<name>.mp4.part.0',
        # '<name>.mp4.part.1' etc. Remove the exact tmp name and any files
        # matching the pattern tmp + '*'.
        for tmp in list(current_temp_files):
            try:
                p = Path(tmp)
                # remove the exact file if present
                if p.exists():
                    p.unlink()
                    print(f"Removed partial file: {tmp}")
                # remove any segment/temp files that start with this name
                for f in p.parent.glob(p.name + '*'):
                    try:
                        if f.exists():
                            f.unlink()
                            print(f"Removed partial file: {f}")
                    except Exception:
                        print(f"Failed to remove partial file: {f}")
            except Exception:
                print(f"Failed to remove partial file: {tmp}")

        # As a fallback, remove any leftover files matching the common
        # pattern used by pypdl for partial mp4 downloads in the current
        # directory. This helps when temp files exist but weren't tracked
        # due to an unexpected interruption.
        try:
            cwd = Path('.')
            for f in cwd.glob('*.mp4.part*'):
                try:
                    f.unlink()
                    print(f"Removed partial file: {f}")
                except Exception:
                    print(f"Failed to remove partial file: {f}")
        except Exception:
            # don't fail cleanup if globbing fails for any reason
            pass

        if signame:
            print(f"Exiting due to signal: {signame}")
        # Exit with non-zero to indicate interruption
        try:
            sys.exit(1)
        except SystemExit:
            # ensure exit even if sys.exit is intercepted
            os._exit(1)

    def _signal_handler(signum, frame):
        try:
            name = signal.Signals(signum).name
        except Exception:
            name = str(signum)
        _cleanup_and_exit(name)

    # Register common termination signals so we can remove partial files
    # if the user sends SIGINT/SIGTERM (Ctrl-C or kill). Ignore failures
    # if signals can't be registered in this environment.
    try:
        signal.signal(signal.SIGINT, _signal_handler)
    except Exception:
        pass
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
    except Exception:
        pass

    # Utility to download a single stream
    def download_stream(stream, out_name: str):
        quality = choose_preferred_quality(stream.videos.keys())
        if not quality:
            # pick first available
            keys = list(stream.videos.keys())
            quality = keys[0] if keys else None
        if not quality:
            print(f"No available quality for {out_name}")
            return
        links = stream(quality)
        if not links:
            print(f"No links for quality {quality} for {out_name}")
            return

        # If there are multiple links for the same quality, prefer the one
        # with the largest Content-Length (when available). Fall back to the
        # first link if sizes can't be determined.
        if len(links) == 1:
            link = links[0]
        else:
            best_link = None
            best_size = -1
            for l in links:
                try:
                    size = _get_content_length(l)
                except Exception:
                    size = None
                if size is not None and size > best_size:
                    best_size = size
                    best_link = l
            link = best_link if best_link is not None else links[0]
        fname = _sanitize_filename(out_name) + '.mp4'
        tmp_name = fname + '.part'
        print(f"Downloading {out_name} -> {fname} ({quality})")
        try:
            # Register the final filename so the cleanup logic can find any
            # partial files that pypdl may create (e.g. '<name>.mp4.part.*').
            current_temp_files.add(fname)

            # Download into a temporary file first, then move into place on
            # success. This avoids leaving many half-finished .mp4 files in
            # the working directory when the user interrupts the process.
            dl.start(link, file_path=tmp_name, segments=32, retries=8)

            # If download completed successfully, atomically rename into
            # the final filename.
            try:
                Path(tmp_name).replace(Path(fname))
            except Exception:
                # Fallback: try simple rename
                try:
                    os.replace(tmp_name, fname)
                except Exception:
                    # If rename fails, leave the temp file but report it.
                    print(f"Warning: failed to rename {tmp_name} to {fname}")
        except KeyboardInterrupt:
            # Propagate keyboard interrupt after ensuring cleanup in outer
            # finally block (which will remove any known temp files).
            raise
        except Exception as e:
            print(f"Download failed for {out_name}: {e}")
            # On any failure, try to remove any partial files matching the
            # pattern we expect pypdl to create for this download.
            try:
                for f in Path('.').glob(f"{fname}.part*"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
            except Exception:
                pass
        finally:
            # No longer consider this filename active
            current_temp_files.discard(fname)

    try:
        # 4. If series: get seasons and episodes for selected translator
        if rezka.type == TVSeries:
            s_info = rezka.seriesInfo
            if translator_id not in s_info:
                print("Chosen translator has no series info or is not available for this translator.")
                sys.exit(1)

            translator_series = s_info[translator_id]
            chosen_eps = _choose_seasons_episodes_interactive(translator_series)
            if not chosen_eps:
                print("No episodes chosen. Exiting.")
                sys.exit(1)

            # 5. Get streams with highest quality and 6. Download
            for season_num, episode_num in chosen_eps:
                try:
                    stream = rezka.getStream(season=season_num, episode=episode_num, translation=translator_id)
                except Exception as e:
                    print(f"Failed to get stream for S{season_num}E{episode_num}: {e}")
                    continue
                title = f"{rezka.name} - S{int(season_num):02}E{int(episode_num):02}"
                download_stream(stream, title)

        elif rezka.type == Movie:
            # Movie: just get stream for chosen translator
            try:
                stream = rezka.getStream(translation=translator_id)
            except Exception as e:
                print(f"Failed to get stream for movie: {e}")
                sys.exit(1)
            title = rezka.name
            download_stream(stream, title)

        else:
            print("Unsupported content type")
    finally:
        # Ensure we properly shutdown the downloader event loop/threads
        try:
            dl.shutdown()
        except Exception:
            pass

        # Remove any leftover temporary files created for interrupted
        # downloads. We only remove files we created and tracked above to
        # avoid deleting unrelated files in the directory.
        for tmp in list(current_temp_files):
            try:
                p = Path(tmp)
                if p.exists():
                    p.unlink()
                    print(f"Removed partial file: {tmp}")
            except Exception:
                print(f"Failed to remove partial file: {tmp}")


if __name__ == "__main__":
    main()