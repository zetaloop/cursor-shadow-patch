"""
This module provides utility functions for the application.

It includes functions for:
- Path manipulation
- Platform-specific operations (Linux AppImage, macOS App Bundle)
- File operations
- General utility functions (UUID generation, MAC address generation, etc.)
- Colored console output
"""
import os
import re
import random
import shutil
import pathlib
import sqlite3
import platform
from uuid import uuid4
from stat import S_IWRITE

# --- Constants ---
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[96m"
PURPLE = "\033[95m"
RESET = "\033[0m"

REVERSE = "\033[7m"
NO_REVERSE = "\033[27m"

SYSTEM = platform.system()
if SYSTEM not in ("Windows", "Linux", "Darwin"):
    print(f"{RED}[ERR] Unsupported OS: {SYSTEM}{RESET}")
    input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}")
    exit()
if SYSTEM == "Windows":
    os.system("color")

globaldir: pathlib.Path | None = None # Ensure globaldir is typed for clarity


# --- Path Manipulation Functions ---
def path(path_str: str | pathlib.Path) -> pathlib.Path:
    """
    Converts a string or Path object to a resolved pathlib.Path object.
    Strips leading/trailing quotes and whitespace from strings.
    """
    if isinstance(path_str, str):
        path_str = path_str.strip().strip("'\"")
    return pathlib.Path(path_str).resolve()


def tmppath(base_tmp_dir: pathlib.Path) -> pathlib.Path:
    """
    Identifies a key profile/storage directory within the base temporary directory.
    Sets the global `globaldir` to this identified directory path.
    If specific subdirectories aren't found, `globaldir` defaults to `base_tmp_dir`.

    Args:
        base_tmp_dir: The application's base temporary/config directory 
                      (e.g., ~/.config/Cursor on Linux).

    Returns:
        The identified profile/storage directory path (also sets `globaldir`).
    """
    global globaldir
    
    if not base_tmp_dir.is_dir():
        print(f"{YELLOW}[WARN] Base temporary directory '{base_tmp_dir}' does not exist. Cleanup might be limited.{RESET}")
        globaldir = base_tmp_dir # Set to non-existent path, cleantmp will handle it
        return base_tmp_dir

    # List of common profile/user data directory names within Electron apps
    # Order implies preference if multiple exist (though unlikely to have both 'User' and 'Default')
    profile_dir_names = ["User Data", "Default", "User"] 

    identified_profile_dir = None
    for name in profile_dir_names:
        potential_dir = base_tmp_dir / name
        if potential_dir.is_dir():
            identified_profile_dir = potential_dir
            print(f"{BLUE}[INFO] Identified profile data directory for cleanup: {identified_profile_dir}{RESET}")
            break
    
    if identified_profile_dir:
        # Further check for common storage locations within the profile directory
        # This helps target cleanup more precisely if a generic profile dir like 'User' was found.
        global_storage_candidates = ["globalStorage", "Local Storage", "Session Storage", "databases", "IndexedDB"]
        # Check if any of these exist directly under the identified_profile_dir
        # For now, we'll use identified_profile_dir itself if it exists.
        # More complex logic could try to find THE MOST specific one, but that risks over-complication.
        globaldir = identified_profile_dir
    else:
        # If no common profile subdirectories are found, assume the base_tmp_dir itself is the main storage area.
        print(f"{BLUE}[INFO] No specific profile subdirectory (like 'User Data', 'Default', 'User') found in '{base_tmp_dir}'. Using base directory for cleanup.{RESET}")
        globaldir = base_tmp_dir
        
    return globaldir


def apppath() -> pathlib.Path:
    """
    Determines the application's base resource path (usually containing 'out/main.js')
    based on the operating system.
    """
    def is_valid_apppath(base_path: pathlib.Path) -> bool:
        return (base_path / "out" / "main.js").exists()

    def find_cursor_in_system_path() -> pathlib.Path | None:
        system_paths = os.environ.get("PATH", "").split(os.pathsep)
        for p_str in system_paths:
            try:
                p_dir = path(p_str) 
                cursor_exec_names = ["cursor"]
                if SYSTEM == "Windows":
                    cursor_exec_names.append("cursor.exe")
                
                for exec_name in cursor_exec_names:
                    cursor_bin = p_dir / exec_name
                    if not cursor_bin.exists():
                        continue
                    if SYSTEM == "Windows":
                        app_base_candidate = p_dir.parent 
                        potential_app_path = app_base_candidate / "resources" / "app"
                        if is_valid_apppath(potential_app_path): return potential_app_path
                        potential_app_path_alt = p_dir / "resources" / "app"
                        if is_valid_apppath(potential_app_path_alt): return potential_app_path_alt
                    elif SYSTEM == "Darwin":
                        if cursor_bin.is_symlink():
                            try:
                                resolved_path = cursor_bin.resolve(strict=True)
                                if "Cursor.app/Contents/MacOS" in str(resolved_path):
                                    app_bundle_root = resolved_path
                                    while app_bundle_root.name != "MacOS" and app_bundle_root.parent != app_bundle_root:
                                        app_bundle_root = app_bundle_root.parent
                                    if app_bundle_root.name == "MacOS":
                                        app_bundle_root = app_bundle_root.parent.parent 
                                        resources_app_path = app_bundle_root / "Contents" / "Resources" / "app"
                                        if is_valid_apppath(resources_app_path): return resources_app_path
                            except Exception: pass
                    elif SYSTEM == "Linux":
                        app_base_candidate = p_dir.parent 
                        potential_app_path = app_base_candidate / "resources" / "app"
                        if is_valid_apppath(potential_app_path): return potential_app_path
                        potential_app_path_alt = p_dir / "resources" / "app"
                        if is_valid_apppath(potential_app_path_alt): return potential_app_path_alt
            except Exception: continue
        return None

    if SYSTEM == "Windows":
        localappdata = os.getenv("LOCALAPPDATA")
        if not localappdata:
            print(f"{RED}[ERR] %LOCALAPPDATA% environment variable not found.{RESET}")
            input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
        default_path = path(localappdata) / "Programs" / "cursor" / "resources" / "app"
        if is_valid_apppath(default_path):
            print(f"{GREEN}[OK]{RESET} Found Cursor at default Windows location: {default_path}"); return default_path
        program_files = os.getenv("ProgramFiles")
        if program_files:
            default_path_pf = path(program_files) / "Cursor" / "resources" / "app"
            if is_valid_apppath(default_path_pf):
                print(f"{GREEN}[OK]{RESET} Found Cursor in Program Files: {default_path_pf}"); return default_path_pf
        print(f"{YELLOW}[WARN] Cursor not found in default Windows locations. Searching PATH...{RESET}")
        if cursor_path_from_env := find_cursor_in_system_path():
            print(f"{GREEN}[OK]{RESET} Found Cursor via PATH: {cursor_path_from_env}"); return cursor_path_from_env
    elif SYSTEM == "Darwin":
        default_path = path("/Applications/Cursor.app/Contents/Resources/app")
        if is_valid_apppath(default_path):
            print(f"{GREEN}[OK]{RESET} Found Cursor at default macOS location: {default_path}"); return default_path
        user_apps_path = path("~/Applications/Cursor.app/Contents/Resources/app").expanduser()
        if is_valid_apppath(user_apps_path):
            print(f"{GREEN}[OK]{RESET} Found Cursor in user Applications folder: {user_apps_path}"); return user_apps_path
        print(f"{YELLOW}[WARN] Cursor not found in default macOS locations. Searching PATH...{RESET}")
        if cursor_path_from_env := find_cursor_in_system_path():
             print(f"{GREEN}[OK]{RESET} Found Cursor via PATH: {cursor_path_from_env}"); return cursor_path_from_env
    elif SYSTEM == "Linux":
        print(f"{BLUE}[INFO] On Linux, main.js is usually found inside an AppImage after extraction.{RESET}")
        print(f"{BLUE}[INFO] Searching for a non-AppImage system installation (fallback)...{RESET}")
        linux_system_paths = [
            path("/opt/Cursor/resources/app"), path("/usr/share/cursor/resources/app"),
            path("/opt/cursor/resources/app"), 
        ]
        for sys_path_candidate in linux_system_paths:
            if is_valid_apppath(sys_path_candidate):
                print(f"{GREEN}[OK]{RESET} Found potential system installation at: {sys_path_candidate}"); return sys_path_candidate
        if cursor_path_from_env := find_cursor_in_system_path():
            print(f"{GREEN}[OK]{RESET} Found potential Cursor installation via PATH: {cursor_path_from_env}"); return cursor_path_from_env
        print(f"{YELLOW}[WARN] No system-wide Cursor installation found by apppath(). AppImage usage is primary for Linux.{RESET}")

    print(f"{RED}[ERR] Cursor application resources path not found automatically for {SYSTEM}.{RESET}")
    print(f"{BLUE}[INFO] Please ensure Cursor is installed in a standard location, or provide the path to 'main.js' or AppImage manually if prompted.{RESET}")
    if SYSTEM != "Linux": input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    raise FileNotFoundError(f"Automatic apppath detection failed for {SYSTEM}.")


def jspath(p_str: str | pathlib.Path | None) -> pathlib.Path:
    """Determines the path to the main.js file."""
    if p_str:
        resolved_js_path = path(p_str)
        if not resolved_js_path.exists():
            print(f"{RED}[ERR] Provided main.js path does not exist: '{resolved_js_path}'{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
        if not resolved_js_path.is_file() or resolved_js_path.name != "main.js":
            print(f"{RED}[ERR] Provided path is not a file named 'main.js': '{resolved_js_path}'{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
        print(f"{GREEN}[OK]{RESET} Using user-provided main.js path: {resolved_js_path}"); return resolved_js_path
    else:
        try:
            base_app_path = apppath()
            main_js_path = base_app_path / "out" / "main.js"
            if not main_js_path.exists():
                print(f"{RED}[ERR] Automatically detected main.js not found at: '{main_js_path}'. Base: {base_app_path}{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
            print(f"{GREEN}[OK]{RESET} Automatically found main.js: {main_js_path}"); return main_js_path
        except FileNotFoundError as e:
            print(f"{RED}[ERR] Could not automatically determine main.js location: {e}{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()

# --- AppImage (Linux) ---
def appimagepath(p_str: str | None) -> pathlib.Path:
    """Finds or validates the path to the Cursor AppImage on Linux."""
    assert SYSTEM == "Linux", "Critical: AppImage functions are only for Linux."
    appimage_path_resolved = None
    if not p_str:
        print(f"{BLUE}[INFO] No AppImage path provided, searching common locations...{RESET}")
        search_paths = [path("."), path("~/Applications").expanduser(), path("~/bin").expanduser(), path("~/.local/bin").expanduser(), path("~/Downloads").expanduser(), path("~/Desktop").expanduser(), path("~").expanduser(), path("/opt"), path("/usr/local/bin")]
        env_paths = os.environ.get("PATH", "").split(os.pathsep); [search_paths.append(path(env_p)) for env_p in env_paths if env_p]
        seen_paths = set(); unique_search_paths = [sp for sp in search_paths if not (sp in seen_paths or seen_paths.add(sp))]
        found_appimages = []
        for search_dir in unique_search_paths:
            if not search_dir.exists() or not search_dir.is_dir(): continue
            try:
                for file_item in search_dir.iterdir():
                    if not file_item.is_file(): continue
                    name_lower = file_item.name.lower()
                    if name_lower.startswith("cursor") and name_lower.endswith(".appimage"):
                        stem = name_lower[:-9]
                        if len(stem) == 6 or (len(stem) > 6 and not stem[6].isalpha()): found_appimages.append(file_item)
            except OSError: continue
        if not found_appimages: print(f"{RED}[ERR] Cursor AppImage not found automatically.{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
        elif len(found_appimages) == 1: appimage_path_resolved = found_appimages[0]
        else:
            print(f"{YELLOW}[WARN] Multiple potential Cursor AppImages found:{RESET}"); [print(f"  {i+1}. {ap}") for i, ap in enumerate(found_appimages)]
            try:
                choice = int(input(f"{PURPLE}Please select: {RESET}").strip()) - 1
                if not (0 <= choice < len(found_appimages)): raise ValueError("Out of range.")
                appimage_path_resolved = found_appimages[choice]
            except ValueError as e: print(f"{RED}[ERR] Invalid selection: {e}{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    else:
        appimage_path_resolved = path(p_str)
        if not appimage_path_resolved.exists(): print(f"{RED}[ERR] Provided AppImage path does not exist: '{appimage_path_resolved}'{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
        if not (appimage_path_resolved.is_file() and appimage_path_resolved.name.lower().endswith(".appimage")): print(f"{RED}[ERR] Provided path is not a valid .AppImage file: '{appimage_path_resolved}'{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    print(f"{GREEN}[OK]{RESET} Using AppImage: {appimage_path_resolved}"); return appimage_path_resolved

def appimage_unpack(appimage_path: pathlib.Path) -> pathlib.Path:
    """Unpacks an AppImage to 'squashfs-root'."""
    assert SYSTEM == "Linux", "AppImage only on Linux."
    target_extract_dir = path(".") / "squashfs-root"; appimage_in_cwd = appimage_path; copied_to_cwd = False
    if appimage_path.parent != path("."):
        try:
            temp_name = appimage_path.name; shutil.copy2(appimage_path, path(".") / temp_name); appimage_in_cwd = path(".") / temp_name; copied_to_cwd = True
            print(f"{BLUE}[INFO] Copied AppImage to CWD for extraction: {appimage_in_cwd}{RESET}")
        except Exception as e: print(f"{RED}[ERR] Failed to copy AppImage to CWD: {e}{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    try: os.chmod(appimage_in_cwd, 0o755)
    except Exception as e: print(f"{RED}[ERR] Failed to make AppImage executable: {e}{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    if target_extract_dir.exists(): print(f"{YELLOW}[WARN] Removing existing 'squashfs-root'...{RESET}"); shutil.rmtree(target_extract_dir)
    print(f"{BLUE}[INFO] Unpacking '{appimage_in_cwd}'...{RESET}"); errorlevel = os.system(f'"{appimage_in_cwd}" --appimage-extract')
    if errorlevel != 0: print(f"{RED}[ERR] Failed to unpack AppImage (code: {errorlevel}).{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    if copied_to_cwd: try: os.remove(appimage_in_cwd); print(f"{BLUE}[INFO] Removed temp AppImage copy.{RESET}")
        except OSError as e: print(f"{YELLOW}[WARN] Could not remove temp AppImage copy: {e}{RESET}")
    if not target_extract_dir.is_dir(): print(f"{RED}[ERR] 'squashfs-root' not found after extraction.{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    print(f"{GREEN}[OK]{RESET} AppImage unpacked to -> {target_extract_dir.resolve()}"); return target_extract_dir

def appimage_repack(appimage_path_target: pathlib.Path, extract_dir: pathlib.Path) -> None:
    """Repacks 'squashfs-root' into an AppImage."""
    assert SYSTEM == "Linux", "AppImage only on Linux."
    assert extract_dir.name == "squashfs-root" and extract_dir.is_dir(), "Invalid extract_dir."
    print(f"\n{BLUE}[INFO] Repacking from '{extract_dir}' to '{appimage_path_target}'{RESET}")
    if not shutil.which("wget"): print(f"{RED}[ERR] wget not found.{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    appimagetool_path = path(".") / "appimagetool-x86_64.AppImage"; dl_path = path(".") / "appimagetool.downloading"
    if dl_path.exists(): os.remove(dl_path)
    if not appimagetool_path.exists():
        print(f"{YELLOW}[WARN] appimagetool not found.{RESET}")
        dl_choice = input(f"{PURPLE}Download appimagetool? (Y/n): {RESET}").strip().lower()
        if dl_choice == "" or dl_choice == "y":
            print(f"{BLUE}[INFO] Downloading appimagetool...{RESET}")
            url = "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage" # Verify occasionally
            ec = os.system(f"wget --no-verbose --show-progress {url} -O \"{dl_path}\"")
            if ec != 0: print(f"{RED}[ERR] Download failed (code: {ec}). Manual: {url}{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
            os.chmod(dl_path, 0o755); os.rename(dl_path, appimagetool_path); print(f"{GREEN}[OK]{RESET} appimagetool downloaded.")
        else: print(f"{RED}[ERR] appimagetool required.{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    if not os.access(appimagetool_path, os.X_OK): os.chmod(appimagetool_path, 0o755)
    appimage_path_target.parent.mkdir(parents=True, exist_ok=True)
    if appimage_path_target.exists(): backup(appimage_path_target, force=True)
    print(f"{BLUE}[INFO] Running appimagetool...{RESET}")
    ec = os.system(f'"{appimagetool_path.resolve()}" "{extract_dir.resolve()}" "{appimage_path_target.resolve()}"')
    if ec != 0: print(f"{RED}[ERR] Failed to repack AppImage (code: {ec}).{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    print(f"{GREEN}[OK]{RESET} AppImage repacked: {appimage_path_target}"); shutil.rmtree(extract_dir); print(f"{GREEN}[OK]{RESET} Removed temp dir: {extract_dir}")

def appimage_detect_jspath(unpacked_dir: pathlib.Path) -> pathlib.Path:
    """Detects main.js in unpacked AppImage."""
    assert unpacked_dir.is_dir(), "Unpacked dir not found."
    print(f"{BLUE}[INFO] Searching for main.js in {unpacked_dir}{RESET}")
    hardcoded = ["resources/app/out/main.js", "usr/share/cursor/resources/app/out/main.js", "opt/cursor/resources/app/out/main.js", "app/resources/app/out/main.js"]
    for rel_path in hardcoded:
        if (p := unpacked_dir / rel_path).exists() and p.is_file(): print(f"{GREEN}[OK]{RESET} Found main.js: {p}"); return p
    print(f"{BLUE}[INFO] Not in predefined. Globbing '**/out/main.js'...{RESET}"); results = list(unpacked_dir.glob("**/out/main.js"))
    if not results: print(f"{YELLOW}[WARN] No '**/out/main.js'. Globbing '**/main.js'...{RESET}"); results = list(unpacked_dir.glob("**/main.js"))
    if not results: print(f"{RED}[ERR] main.js not found via glob in {unpacked_dir}{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    if len(results) == 1: print(f"{GREEN}[OK]{RESET} Found main.js (glob): {results[0]}"); return results[0]
    print(f"{YELLOW}[WARN] Multiple main.js (glob):{RESET}"); [print(f"  - {p}") for p in results]
    preferred = [p for p in results if "resources/app" in str(p)]
    if preferred: results = preferred
    results.sort(key=lambda p: len(str(p))); print(f"{GREEN}[OK]{RESET} Selected main.js (shortest/preferred): {results[0]}"); return results[0]

# --- App Bundle (macOS) ---
def appbundle_movetmp(bundle_path: pathlib.Path) -> pathlib.Path:
    assert SYSTEM == "Darwin" and bundle_path.exists() and bundle_path.is_dir() and bundle_path.name.endswith(".app")
    tmp_path = bundle_path.parent / (bundle_path.name + ".tmp")
    if tmp_path.exists(): print(f"{YELLOW}[WARN] Temp bundle exists. Removing...{RESET}"); shutil.rmtree(tmp_path)
    print(f"{BLUE}[INFO] Copying '{bundle_path}' to '{tmp_path}'...{RESET}"); shutil.copytree(bundle_path, tmp_path, symlinks=True); print(f"{GREEN}[OK]{RESET} Copied to temp."); return tmp_path
def appbundle_moveback(tmp_path: pathlib.Path, orig_path: pathlib.Path) -> None:
    assert SYSTEM == "Darwin" and tmp_path.exists() and tmp_path.is_dir() and tmp_path.name.endswith(".app.tmp")
    if orig_path.exists(): backup(orig_path, force=True)
    print(f"{BLUE}[INFO] Moving '{tmp_path}' to '{orig_path}'...{RESET}")
    if orig_path.exists(): shutil.rmtree(orig_path)
    shutil.move(str(tmp_path), str(orig_path)); print(f"{GREEN}[OK]{RESET} Moved back.")
def appbundle_unsign(bundle_path: pathlib.Path) -> None:
    assert SYSTEM == "Darwin" and bundle_path.exists()
    print(f"{BLUE}[INFO] Unsigning '{bundle_path}'...{RESET}"); ec = os.system(f"codesign --remove-signature \"{bundle_path}\"")
    if ec!=0: print(f"{RED}[ERR] Failed to unsign (code: {ec}). Xcode tools?{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    print(f"{GREEN}[OK]{RESET} Unsigned.")
def appbundle_sign(bundle_path: pathlib.Path) -> None:
    assert SYSTEM == "Darwin" and bundle_path.exists()
    print(f"{BLUE}[INFO] Ad-hoc signing '{bundle_path}'...{RESET}"); ec = os.system(f"codesign --force --deep --sign - \"{bundle_path}\"")
    if ec!=0: print(f"{RED}[ERR] Failed to sign (code: {ec}). Xcode tools?{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
    print(f"{GREEN}[OK]{RESET} Signed.")
def appbundle_from_jspath(js_path: pathlib.Path) -> pathlib.Path:
    curr = js_path.resolve()
    for _ in range(6): # Max depth for typical .app/Contents/Resources/app/out/main.js
        if curr.name.endswith(".app") and (curr / "Contents").is_dir(): return curr
        if curr.parent == curr: break
        curr = curr.parent
    print(f"{RED}[ERR] Could not derive .app from '{js_path}'.{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
def appbundle_to_jspath(bundle_path: pathlib.Path) -> pathlib.Path:
    assert bundle_path.is_dir() and bundle_path.name.endswith(".app")
    return bundle_path / "Contents" / "Resources" / "app" / "out" / "main.js"

# --- File Operation Functions ---
def remove_readonly(file_path: pathlib.Path) -> None:
    try: os.chmod(file_path, os.stat(file_path).st_mode | S_IWRITE)
    except OSError: pass 
def load(file_path: pathlib.Path) -> bytes:
    print(f"{BLUE}[INFO] Loading: {file_path}{RESET}")
    try:
        with open(file_path, "rb") as f: content = f.read()
        print(f"{GREEN}[OK]{RESET} Loaded {len(content)} bytes from {file_path.name}"); return content
    except Exception as e: print(f"{RED}[ERR] Failed to load {file_path}: {e}{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
def save(file_path: pathlib.Path, data: bytes) -> None:
    print(f"\n{BLUE}[INFO] Saving to: {file_path}{RESET}")
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True); remove_readonly(file_path)
        with open(file_path, "wb") as f: f.write(data)
        print(f"{GREEN}[OK]{RESET} Saved {len(data)} bytes to {file_path.name}")
    except Exception as e: print(f"{RED}[ERR] Failed to save {file_path}: {e}{RESET}"); input(f"\n{REVERSE}Press Enter to exit...{NO_REVERSE}"); exit()
def backup(target_path: pathlib.Path, force: bool = False) -> None:
    if not target_path.exists(): print(f"{YELLOW}[WARN] Cannot backup missing: {target_path.name}{RESET}"); return
    bak_path = target_path.with_name(target_path.name + ".bak")
    print(f"\n{BLUE}[INFO] Backing up '{target_path.name}' to '{bak_path.name}'{RESET}")
    if bak_path.exists():
        if force: print(f"{YELLOW}[WARN] Overwriting existing backup.{RESET}"); shutil.rmtree(bak_path) if bak_path.is_dir() else os.remove(bak_path)
        else: print(f"{BLUE}[INFO] Backup exists. Skipping.{RESET}"); return
    try:
        if target_path.is_dir(): shutil.copytree(target_path, bak_path, symlinks=True)
        else: shutil.copy2(target_path, bak_path)
        print(f"{GREEN}[OK]{RESET} Backup created: {bak_path.name}")
    except Exception as e: print(f"{RED}[ERR] Backup failed for {target_path.name}: {e}{RESET}")

# --- Utility Functions ---
def pause() -> None: input(f"\n{REVERSE}Press Enter to continue...{NO_REVERSE}")
def uuid() -> str: return str(uuid4())
def randomuuid(val: str | None) -> str:
    if not val: new_id = uuid(); print(f"{BLUE}[INFO] Generated UUID: {new_id}{RESET}"); return new_id
    return val
def macaddr(val: str | None) -> str:
    invalid = {"00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff", "ac:de:48:00:11:22"}
    if not val or val.lower() in invalid:
        fo = random.choice([i for i in range(256) if (i % 4 == 2)])
        new_mac = f"{fo:02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}"
        print(f"{BLUE}[INFO] Generated MAC: {new_mac}{RESET}"); return new_mac
    return val
def chk(data: bytes, probes: list[bytes]) -> bool: return any(p in data for p in probes)

# --- Cleanup Functions ---
def cleanlog(*args, **kwargs) -> None: return # Deprecated
def cleantmp(base_tmp_dir: pathlib.Path) -> None:
    """
    Cleans common cache and temporary file/directory patterns within the identified
    application temporary/profile directory.
    """
    global globaldir # Uses globaldir set by tmppath
    
    # tmppath is called by patcher.py before calling this, or should be.
    # For robustness, ensure tmppath is called if globaldir is not yet set.
    if globaldir is None: # If tmppath hasn't been successfully run or was reset
        print(f"{YELLOW}[WARN] globaldir not set. Attempting to set it via tmppath before cleaning.{RESET}")
        tmppath(base_tmp_dir) # Attempt to set globaldir

    # Determine the actual directory to clean. globaldir is now a directory.
    # If tmppath failed to find a specific subdir, globaldir might be base_tmp_dir itself or None.
    target_cleanup_root_dir = globaldir if globaldir and globaldir.is_dir() else base_tmp_dir

    if not target_cleanup_root_dir.is_dir():
        print(f"{YELLOW}[WARN] Target cleanup directory '{target_cleanup_root_dir}' does not exist or is not a directory. Skipping cleanup.{RESET}")
        return

    print(f"{BLUE}[INFO] Starting cleanup in directory: {target_cleanup_root_dir}{RESET}")

    # More comprehensive list of cache/temp patterns common in Electron/VSCode apps
    # Order can matter if patterns overlap (e.g. "Cache" before "Code Cache/*")
    # Globs are relative to target_cleanup_root_dir
    cleanup_patterns = [
        # Top-level directories
        "Cache", "Code Cache", "GPUCache", "Session Storage", "Local Storage", 
        "IndexedDB", "databases", "blob_storage", "Service Worker", "DawnCache", # Dawn is Chrome's new WebGPU cache
        # Top-level files
        "Cookies", "Cookies-journal", "*.log", "*.tmp", 
        # Deeper common patterns (if not caught by top-level dir removal)
        "*/Cache/*", "*/Code Cache/*", "*/GPUCache/*",
        # Specific to some apps but good to include
        "network", # Often contains cookies.sqlite or similar
        "*.cursor_config", # Original pattern
        "*.sqlite-shm", "*.sqlite-wal", # SQLite temp files, ensure they are not globbed too broadly
    ]
    
    # Handle specific SQLite journal files if the main DB was targeted by tmppath previously
    # This part might be redundant if globaldir is now always a directory.
    if globaldir and globaldir.is_file() and globaldir.name.endswith("b"): # If globaldir is a specific DB file from old tmppath
         db_journal_shm = globaldir.with_suffix(globaldir.suffix + "-shm")
         db_journal_wal = globaldir.with_suffix(globaldir.suffix + "-wal")
         if db_journal_shm.exists(): cleanup_patterns.append(db_journal_shm.name)
         if db_journal_wal.exists(): cleanup_patterns.append(db_journal_wal.name)


    cleaned_items_count = 0
    for pattern_str in cleanup_patterns:
        try:
            # Iterate over items matching the glob pattern within the target_cleanup_root_dir
            for item_path in target_cleanup_root_dir.glob(pattern_str):
                try:
                    if item_path.is_dir():
                        print(f"{BLUE}[INFO] Removing directory: {item_path.relative_to(target_cleanup_root_dir)}{RESET}")
                        shutil.rmtree(item_path)
                        cleaned_items_count += 1
                    elif item_path.is_file():
                        print(f"{BLUE}[INFO] Removing file: {item_path.relative_to(target_cleanup_root_dir)}{RESET}")
                        remove_readonly(item_path) # Ensure writable
                        item_path.unlink()
                        cleaned_items_count += 1
                except Exception as e_item:
                    print(f"{RED}[ERR] Failed to remove '{item_path.relative_to(target_cleanup_root_dir)}': {e_item}{RESET}")
        except Exception as e_glob: # Error during glob itself
            print(f"{RED}[ERR] Error processing glob pattern '{pattern_str}': {e_glob}{RESET}")

    if cleaned_items_count > 0:
        print(f"{GREEN}[OK]{RESET} Temporary file/directory cleanup complete. {cleaned_items_count} item(s) removed from '{target_cleanup_root_dir}'.")
    else:
        print(f"{BLUE}[INFO] No cache/temporary items matching defined patterns found in '{target_cleanup_root_dir}'.{RESET}")


def replace(
    data: bytes, pattern: str | bytes, replacement: str | bytes, probe: str | bytes
) -> tuple[bytes, bool, bool]: 
    if isinstance(pattern, str): pattern_bytes = pattern.encode('utf-8')
    else: pattern_bytes = pattern
    if isinstance(replacement, str): replacement_bytes = replacement.encode('utf-8')
    else: replacement_bytes = replacement
    if isinstance(probe, str): probe_bytes = probe.encode('utf-8')
    else: probe_bytes = probe
    assert isinstance(pattern_bytes, bytes) and isinstance(replacement_bytes, bytes) and isinstance(probe_bytes, bytes)
    try:
        main_regex = re.compile(pattern_bytes, re.DOTALL)
        probe_regex = re.compile(probe_bytes, re.DOTALL)
    except re.error as e:
        print(f"{RED}[ERR] Regex compilation failed: {e}{RESET}\nPattern: {pattern_bytes.decode(errors='ignore')}\nProbe: {probe_bytes.decode(errors='ignore')}{RESET}")
        return data, False, False
    main_pattern_found_initially = bool(main_regex.search(data))
    probe_pattern_found_initially = bool(probe_regex.search(data))
    modified_data = data; patch_applied_this_run = False
    pattern_str_for_log = pattern_bytes.decode(errors='ignore'); replacement_str_for_log = replacement_bytes.decode(errors='ignore')
    print(f"{BLUE}[INFO] Patch attempt: '{pattern_str_for_log[:70]}...' => '{replacement_str_for_log[:70]}...'{RESET}")
    if probe_pattern_found_initially:
        print(f"{BLUE}[INFO] Probe found. Overwriting...{RESET}")
        modified_data, num_probe_replacements = probe_regex.subn(replacement_bytes, modified_data)
        if num_probe_replacements > 0: print(f"{GREEN}[OK]{RESET} Overwrote {num_probe_replacements} probed section(s)."); patch_applied_this_run = True
    if main_pattern_found_initially:
        current_data_for_main_patch = modified_data 
        modified_data, num_main_replacements = main_regex.subn(replacement_bytes, current_data_for_main_patch)
        if num_main_replacements > 0 and current_data_for_main_patch != modified_data:
            print(f"{GREEN}[OK]{RESET} Patched {num_main_replacements} main pattern instance(s)."); patch_applied_this_run = True
        elif not patch_applied_this_run: print(f"{YELLOW}[WARN] Main pattern <{pattern_str_for_log[:70]}...> found, but no changes made.{RESET}")
    if not main_pattern_found_initially and not probe_pattern_found_initially:
        print(f"{YELLOW}[WARN] Neither main nor probe pattern <{pattern_str_for_log[:70]}...> found. SKIPPED.{RESET}"); return data, False, False 
    if not patch_applied_this_run and (main_pattern_found_initially or probe_pattern_found_initially):
        print(f"{BLUE}[INFO] Pattern <{pattern_str_for_log[:70]}...> detected, but no data change (replacement may be identical).{RESET}")
    return modified_data, main_pattern_found_initially or probe_pattern_found_initially, patch_applied_this_run

if __name__ == "__main__":
    print(f"{BLUE}--- _utils.py Self-Test Mode ---{RESET}")
    dummy_tmp_root = path("./csp_dummy_temp_root")
    if dummy_tmp_root.exists(): shutil.rmtree(dummy_tmp_root)
    dummy_tmp_root.mkdir(parents=True, exist_ok=True)
    
    # Create dummy structure for tmppath and cleantmp
    (dummy_tmp_root / "User Data" / "Cache").mkdir(parents=True, exist_ok=True)
    (dummy_tmp_root / "User Data" / "Local Storage").mkdir(parents=True, exist_ok=True)
    with open(dummy_tmp_root / "User Data" / "Cache" / "data_1", "w") as f: f.write("cache_data")
    with open(dummy_tmp_root / "User Data" / "Local Storage" / "leveldb", "w") as f: f.write("ls_data")
    with open(dummy_tmp_root / "User Data" / "some.log", "w") as f: f.write("log_data")
    (dummy_tmp_root / "GPUCache").mkdir(parents=True, exist_ok=True)

    print(f"\n{YELLOW}Testing tmppath and cleantmp with base: {dummy_tmp_root}{RESET}")
    # tmppath will set globaldir. It should identify "User Data" or dummy_tmp_root.
    identified_path_for_cleanup = tmppath(dummy_tmp_root) 
    print(f"tmppath identified: {identified_path_for_cleanup}, globaldir set to: {globaldir}")
    
    cleantmp(dummy_tmp_root) # This will use the globaldir set by tmppath above.

    # Assertions for cleanup (example, depends on exact patterns and tmppath behavior)
    # If globaldir became ".../User Data", then items inside it should be gone.
    # If globaldir became dummy_tmp_root, then GPUCache should be gone.
    if globaldir == (dummy_tmp_root / "User Data"):
        assert not (dummy_tmp_root / "User Data" / "Cache").exists(), "Cache dir should be removed"
        assert not (dummy_tmp_root / "User Data" / "Local Storage").exists(), "Local Storage dir should be removed"
        assert not (dummy_tmp_root / "User Data" / "some.log").exists(), "Log file should be removed"
    elif globaldir == dummy_tmp_root:
         assert not (dummy_tmp_root / "GPUCache").exists(), "GPUCache dir should be removed if globaldir was base"
    else:
        print(f"{YELLOW}[WARN] Could not reliably assert cleanup due to tmppath result.{RESET}")

    shutil.rmtree(dummy_tmp_root) # Clean up self-test directory
    print(f"\n{GREEN}[OK] _utils.py cleanup self-tests finished.{RESET}")
    pause()
