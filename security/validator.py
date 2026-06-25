"""Validation helpers for actions: app whitelist, path checks, commands."""

import os
import shlex
import shutil
import difflib
import configparser
from typing import Optional, List, Tuple
from utils.config import get_config
from utils.logger import get_logger

logger = get_logger(__name__)


def _expand_list(bases) -> List[str]:
    out = []
    for b in bases or []:
        try:
            out.append(os.path.abspath(os.path.expanduser(b)))
        except Exception:
            continue
    return out


def is_app_allowed(app_name: str) -> Optional[str]:
    # Backwards-compatible wrapper around find_allowed_app
    res = find_allowed_app(app_name)
    if not res:
        return None
    _, path = res
    return path


def find_allowed_app(app_name: str) -> Optional[Tuple[str, str]]:
    """Return a tuple (matched_key, binary_path) for an allowed app name.
    Uses exact match, close-string matching, and substring matching against
    the configured `allowed_apps` keys. Returns None when no allowed app is
    matched or the binary isn't found on PATH.
    """
    if not app_name:
        return None
    
    # Reject fuzzy matching for known wrapper/system commands
    # These should never be treated as app launches
    wrapper_cmds = {
        'sudo', 'pkexec', 'gksu', 'gksudo', 'su', 'dbus-launch',
        'flatpak', 'snap', 'setsid', 'nohup', 'env', 'bash', 'sh',
        'sudo-exec', 'run', 'launch', 'started', 'launching'
    }
    if app_name.strip().lower() in wrapper_cmds:
        return None
    
    cfg = get_config() or {}
    apps = cfg.get('allowed_apps', {})
    allow_any = cfg.get('allow_any_app', False)

    # map lowercase key -> original key
    key_map = {k.lower(): k for k in apps.keys()}
    keys = list(key_map.keys())
    key = app_name.strip().lower()

    # exact match against configured allowed apps
    if key in key_map:
        original = key_map[key]
        bin_name = apps[original]
        path = shutil.which(bin_name)
        if path:
            return original, path
        logger.debug("Allowed app binary not found on PATH: %s", bin_name)
        return None

    # close/fuzzy match against configured allowed apps
    match = difflib.get_close_matches(key, keys, n=1, cutoff=0.75)
    if match:
        original = key_map[match[0]]
        bin_name = apps[original]
        path = shutil.which(bin_name)
        if path:
            logger.debug("Fuzzy matched app '%s' -> '%s'", app_name, original)
            return original, path

    # substring match against configured allowed apps
    for k_lower, original in key_map.items():
        if key in k_lower or k_lower in key:
            bin_name = apps[original]
            path = shutil.which(bin_name)
            if path:
                logger.debug("Substring matched app '%s' -> '%s'", app_name, original)
                return original, path

    # Helper: resolve an Exec= value from a .desktop file to a candidate binary
    def _resolve_exec_token(exec_field: str) -> Optional[str]:
        if not exec_field:
            return None
        try:
            toks = shlex.split(exec_field, posix=True)
        except Exception:
            toks = exec_field.split()
        # wrappers that typically invoke another binary as argument
        wrappers = {
            'pkexec', 'sudo', 'gksu', 'gksudo', 'su', 'dbus-launch',
            'flatpak', 'flatpak-spawn', 'snap', 'setsid', 'nohup', 'env'
        }
        for i, t in enumerate(toks):
            t = t.strip()
            if not t or t.startswith('%'):
                continue
            if '=' in t and not os.path.isabs(t):
                # skip env assignments like FOO=bar
                continue
            if t in ('sh', 'bash', '-c'):
                continue
            # if this token is a wrapper (or an absolute path to one), look for the real binary after it
            base_t = os.path.basename(t)
            if t in wrappers or base_t in wrappers:
                for j in range(i + 1, len(toks)):
                    tj = toks[j].strip()
                    if not tj or tj.startswith('%') or tj.startswith('-'):
                        continue
                    if '=' in tj and not os.path.isabs(tj):
                        continue
                    base_tj = os.path.basename(tj)
                    if base_tj in wrappers:
                        continue
                    if os.path.isabs(tj) and os.access(tj, os.X_OK):
                        return tj
                    p = shutil.which(tj)
                    if p:
                        base_p = os.path.basename(p).lower()
                        if base_p in wrappers:
                            continue
                        return tj
                # nothing useful after wrapper, continue scanning
                continue
            # if absolute path and executable (and not a wrapper)
            if os.path.isabs(t) and os.access(t, os.X_OK):
                return t
            # else try PATH
            p = shutil.which(t)
            if p:
                return t
        return None

    # scan .desktop entries for GUI apps
    def _scan_desktop_entries() -> List[dict]:
        out = []
        seen = set()
        xdg_dirs = os.environ.get('XDG_DATA_DIRS', '/usr/local/share/:/usr/share/').split(':')
        dirs = [os.path.join(d, 'applications') for d in xdg_dirs]
        dirs.append(os.path.expanduser('~/.local/share/applications'))
        for d in dirs:
            try:
                for name in os.listdir(d):
                    if not name.endswith('.desktop'):
                        continue
                    fp = os.path.join(d, name)
                    if fp in seen:
                        continue
                    seen.add(fp)
                    try:
                        parser = configparser.ConfigParser(interpolation=None)
                        with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                            parser.read_file(fh)
                        if 'Desktop Entry' not in parser:
                            continue
                        sec = parser['Desktop Entry']
                        nodisplay = sec.get('NoDisplay', '').lower() in ('true', '1', 'yes')
                        if nodisplay:
                            continue
                        name_val = sec.get('Name', '').strip()
                        generic = sec.get('GenericName', '').strip()
                        comment = sec.get('Comment', '').strip()
                        exec_field = sec.get('Exec', '').strip()
                        terminal = sec.get('Terminal', '').lower() in ('true', '1', 'yes')
                        cats = [c for c in sec.get('Categories', '').split(';') if c]
                        desktop_id = os.path.splitext(name)[0]
                        exec_bin = _resolve_exec_token(exec_field)
                        out.append({
                            'name': name_val,
                            'generic': generic,
                            'comment': comment,
                            'exec': exec_field,
                            'exec_bin': exec_bin,
                            'desktop_id': desktop_id,
                            'categories': cats,
                            'terminal': terminal,
                            'path': fp,
                        })
                    except Exception:
                        continue
            except Exception:
                continue
        return out

    # Try to prefer GUI apps declared via .desktop entries when searching
    if allow_any:
        entries = _scan_desktop_entries()
        entries_by_exec = { (e['exec_bin'] or '').lower(): e for e in entries if e.get('exec_bin') }
        entries_by_name = { (e['name'] or '').strip().lower(): e for e in entries if e.get('name') }
        entries_by_id = { (e['desktop_id'] or '').lower(): e for e in entries }

        # detect intent categories from user input
        intent_map = {
            'system monitor': ['System', 'SystemMonitor', 'SystemTools'],
            'system-monitor': ['System', 'SystemMonitor', 'SystemTools'],
            'monitor': ['SystemMonitor', 'SystemTools'],
            'task manager': ['SystemMonitor', 'System'],
            'taskmanager': ['SystemMonitor', 'System'],
            'process': ['SystemMonitor', 'System'],
            'processes': ['SystemMonitor', 'System'],
            'terminal': ['TerminalEmulator', 'Terminal'],
            'term': ['TerminalEmulator', 'Terminal'],
            'console': ['TerminalEmulator'],
            'file': ['FileManager'],
            'explorer': ['FileManager'],
            'browser': ['WebBrowser'],
            'web': ['WebBrowser'],
            'music': ['Audio', 'AudioVideo'],
            'spotify': ['Audio', 'AudioVideo'],
            'editor': ['TextEditor', 'Development'],
            'code': ['Development', 'TextEditor'],
        }
        desired_cats = set()
        for token, cats in intent_map.items():
            if token in key:
                for c in cats:
                    desired_cats.add(c.lower())

        # helper to resolve exec path for a candidate exec_bin
        def _resolve_exec_path(exec_bin: Optional[str]) -> Optional[str]:
            if not exec_bin:
                return None
            if os.path.isabs(exec_bin) and os.access(exec_bin, os.X_OK):
                return exec_bin
            p = shutil.which(exec_bin)
            if p:
                return p
            return None

        # Search priority: name/id/exec exact -> category-filtered fuzzy -> global fuzzy -> substring

        # 1) exact desktop name/id/exec match
        if key in entries_by_name:
            e = entries_by_name[key]
            p = _resolve_exec_path(e.get('exec_bin'))
            if p:
                return e.get('name') or e.get('desktop_id'), p
        if key in entries_by_id:
            e = entries_by_id[key]
            p = _resolve_exec_path(e.get('exec_bin'))
            if p:
                return e.get('name') or e.get('desktop_id'), p
        if key in entries_by_exec:
            e = entries_by_exec[key]
            p = _resolve_exec_path(e.get('exec_bin'))
            if p:
                return e.get('name') or e.get('desktop_id'), p

        # 2) prefer fuzzy/substring matches among category-filtered entries
        candidates = entries
        if desired_cats:
            filtered = []
            for e in entries:
                cats = [c.lower() for c in (e.get('categories') or [])]
                if any(dc == c for dc in desired_cats for c in cats):
                    filtered.append(e)
            if filtered:
                # Among category-matching entries, prefer those whose
                # name/exec/id best matches the user's input using fuzzy
                # matching, then substring; as a last resort pick the
                # first runnable entry.
                search_pool_f = []
                pool_map_f = {}
                for e in filtered:
                    if e.get('name'):
                        n = e['name'].lower()
                        search_pool_f.append(n)
                        pool_map_f[n] = e
                    if e.get('exec_bin'):
                        ex = (e['exec_bin'] or '').lower()
                        if ex not in pool_map_f:
                            search_pool_f.append(ex)
                            pool_map_f[ex] = e
                    if e.get('desktop_id'):
                        did = (e['desktop_id'] or '').lower()
                        if did not in pool_map_f:
                            search_pool_f.append(did)
                            pool_map_f[did] = e

                if search_pool_f:
                    m = difflib.get_close_matches(key, search_pool_f, n=1, cutoff=0.75)
                    if m:
                        e = pool_map_f.get(m[0])
                        if e:
                            p = _resolve_exec_path(e.get('exec_bin'))
                            if p:
                                return e.get('name') or e.get('desktop_id'), p

                # substring fallback among filtered candidates
                for s in search_pool_f:
                    if key in s or s in key:
                        e = pool_map_f.get(s)
                        if e:
                            p = _resolve_exec_path(e.get('exec_bin'))
                            if p:
                                return e.get('name') or e.get('desktop_id'), p

                # last resort: return first runnable filtered entry
                for e in filtered:
                    p = _resolve_exec_path(e.get('exec_bin'))
                    if p:
                        return e.get('name') or e.get('desktop_id'), p
                candidates = filtered

        # fuzzy match on candidate names and exec_bin
        search_pool = []
        pool_map = {}
        for e in candidates:
            if e.get('name'):
                n = e['name'].lower()
                search_pool.append(n)
                pool_map[n] = e
            if e.get('exec_bin'):
                ex = e['exec_bin'].lower()
                if ex not in pool_map:
                    search_pool.append(ex)
                    pool_map[ex] = e
            if e.get('desktop_id'):
                did = e['desktop_id'].lower()
                if did not in pool_map:
                    search_pool.append(did)
                    pool_map[did] = e

        if search_pool:
            m = difflib.get_close_matches(key, search_pool, n=1, cutoff=0.75)
            if m:
                e = pool_map.get(m[0])
                if e:
                    p = _resolve_exec_path(e.get('exec_bin'))
                    if p:
                        logger.debug("Fuzzy matched desktop app '%s' -> '%s'", app_name, e.get('name') or e.get('desktop_id'))
                        return e.get('name') or e.get('desktop_id'), p

        # substring match among candidates
        for s in search_pool:
            if key in s or s in key:
                e = pool_map.get(s)
                if e:
                    p = _resolve_exec_path(e.get('exec_bin'))
                    if p:
                        logger.debug("Substring matched desktop app '%s' -> '%s'", app_name, e.get('name') or e.get('desktop_id'))
                        return e.get('name') or e.get('desktop_id'), p

        # Final scoring among candidates: prefer entries whose Exec resolves
        # to a real GUI binary (not wrappers like env/pkexec), that match
        # the key/name, and that belong to desired categories.
        def _score_candidate(e):
            p = _resolve_exec_path(e.get('exec_bin'))
            if not p:
                return -9999.0
            base = os.path.basename(p).lower()
            low_wrappers = {'env', 'pkexec', 'sudo', 'gksu', 'gksudo', 'su', 'dbus-launch', 'flatpak', 'snap', 'setsid', 'nohup'}
            score = 0.0
            name = (e.get('name') or '').lower()
            did = (e.get('desktop_id') or '').lower()
            if base in low_wrappers:
                score -= 100.0
            # strong exact matches
            if key == name or key == did:
                score += 80.0
            # substring matches
            if key in name or name in key or key in did or did in key:
                score += 30.0
            # prefer monitor keyword when relevant
            if 'monitor' in name and ('monitor' in key or 'system' in key):
                score += 25.0
            # category boost
            cats = [c.lower() for c in (e.get('categories') or [])]
            if any(dc in cats for dc in desired_cats):
                score += 40.0
            # fuzzy similarity
            try:
                r = difflib.SequenceMatcher(None, key, name).ratio()
                score += r * 40.0
            except Exception:
                pass
            return score

        best = None
        best_score = -1e9
        for e in candidates:
            s = _score_candidate(e)
            if s > best_score:
                best_score = s
                best = e
        if best and best_score > -9000:
            p = _resolve_exec_path(best.get('exec_bin'))
            if p:
                return best.get('name') or best.get('desktop_id'), p

        # 3) fallback: only consider PATH executables that have a desktop entry
        # gather exec bins known from desktop entries
        desktop_exec_bins = { (e['exec_bin'] or '').lower() for e in entries if e.get('exec_bin') }

        # direct PATH check but prefer those with desktop entries
        path_direct = shutil.which(app_name)
        if path_direct:
            base = os.path.basename(path_direct).lower()
            if base in desktop_exec_bins:
                return app_name, path_direct

        # gather executable names on PATH (map lowercase->original)
        names = set()
        for d in os.environ.get('PATH', '').split(os.pathsep):
            try:
                for fname in os.listdir(d):
                    fpath = os.path.join(d, fname)
                    if os.path.isfile(fpath) and os.access(fpath, os.X_OK):
                        names.add(fname)
            except Exception:
                continue
        names_map = {n.lower(): n for n in names}
        if not names_map:
            logger.debug("No executables found on PATH while searching for: %s", app_name)
            return None

        # exact name on PATH but require desktop entry
        if key in names_map and key in desktop_exec_bins:
            original = names_map[key]
            path = shutil.which(original)
            if path:
                return original, path

        # fuzzy match against PATH names but require desktop entry
        path_keys = [k for k in list(names_map.keys()) if k in desktop_exec_bins]
        match = difflib.get_close_matches(key, path_keys, n=1, cutoff=0.75)
        if match:
            original = names_map[match[0]]
            path = shutil.which(original)
            if path:
                logger.debug("Fuzzy matched PATH app '%s' -> '%s'", app_name, original)
                return original, path

        # substring match against PATH names but require desktop entry
        for k_lower, original in names_map.items():
            if (key in k_lower or k_lower in key) and k_lower in desktop_exec_bins:
                path = shutil.which(original)
                if path:
                    logger.debug("Substring matched PATH app '%s' -> '%s'", app_name, original)
                    return original, path

    logger.debug("App not in allowed list or PATH/desktop entries: %s", key)
    return None


def is_path_allowed(path: str) -> bool:
    if not path:
        return False
    p = os.path.abspath(os.path.expanduser(path))
    cfg = get_config() or {}
    bases = _expand_list(cfg.get('allowed_folder_bases', []))
    for base in bases:
        try:
            if os.path.commonpath([base, p]) == base:
                return True
        except Exception:
            continue
    logger.debug("Path not allowed: %s (bases=%s)", p, bases)
    return False


def safe_split_command(cmd: str) -> Optional[List[str]]:
    if not cmd:
        return None
    try:
        parts = shlex.split(cmd)
    except Exception:
        return None
    if not parts:
        return None
    cfg = get_config() or {}
    allowed = cfg.get('allowed_commands', [])
    first = parts[0]
    if first not in allowed:
        logger.debug("Command not allowed: %s", first)
        return None
    return parts
