"""
Cursor Shadow Patcher

This script modifies the Cursor application's main.js file to customize
certain identifiers like machine ID, MAC address, etc. It supports
Windows, Linux (AppImage), and macOS.
"""
import os
import _utils # Import the refactored _utils module

# --- Patch Definitions ---
# Centralized definitions for all patches to be applied.
# Each key is a patch identifier, and the value is a dictionary containing:
# - "find_pattern": Regex to find the code segment to replace.
# - "replace_template": A template string for the replacement. Uses "{value}" as a placeholder
#                       for the user-provided or generated value. Includes CSP comments.
# - "probe_pattern": Regex to detect if this patch (or a similar one) has already been applied.
# - "prompt_message": Message shown to the user when asking for input.
# - "value_generator": A function from _utils (e.g., randomuuid, macaddr) to generate a default
#                      value if the user provides no input.
# - "csp_id": A unique identifier (e.g., "csp1") used in comments for the patch.

# General notes on regex changes:
# - \s* and \s+ are used to allow flexible whitespace.
# - Character classes like \w+ are used for identifiers where possible, but cautiously.
# - Non-greedy quantifiers (.*?, *?) are preferred.
# - Increased flexibility in the number of characters for dynamic parts (e.g., .{0,80} instead of .{0,50}).
# - Patterns are made to be more resilient to minification (e.g., removal of comments, some variable renaming).
PATCH_DEFINITIONS = {
    "machine_id": {
        "find_pattern": r"=\s*[\w\.$_]+\s*\([^)]+\{[^}]*?timeout\s*:\s*[\d\.e\+\-]+[^}]*?\}\s*\)\s*\.\s*[\w\.$_]+\s*\(\s*\)\s*,",
        "replace_template": '=/*{csp_id}*/"{value}"/*{csp_id_end}*/,',
        "probe_pattern": r"=\s*/\*csp1\*/[^/]+\/\*1csp\*/\s*,",
        "prompt_message": "MachineId",
        "value_generator": _utils.randomuuid,
        "csp_id": "csp1",
        "csp_id_end": "1csp",
    },
    "mac_address": {
        "find_pattern": r"(function\s+\w+\s*\([^)]*\)\s*\{)\s*const\s+\w+\s*=\s*\w+\(\);\s*for\s*\(\s*const\s+\w+\s*in\s*\w+\s*\)\s*\{.*?"Unable\s+to\s+retrieve\s+mac\s+address.*?\s*throw\s+new\s+Error\s*\([^)]*\);\s*(\})",
        "replace_template": '\\1return/*{csp_id}*/"{value}"/*{csp_id_end}*/;\\2',
        "probe_pattern": r"(function\s+\w+\s*\([^)]*\)\s*\{)\s*return\s*/\*csp2\*/[^/]+\/\*2csp\*/;\s*(\})",
        "prompt_message": "Mac Address",
        "value_generator": _utils.macaddr,
        "csp_id": "csp2",
        "csp_id_end": "2csp",
    },
    "sqm_id": {
        "find_pattern": r"return\s*\([\w\.$_]+\.GetStringRegKey\s*\(\s*['\"]HKEY_LOCAL_MACHINE['\"]\s*,\s*[\w\.$_]+\s*,\s*['\"]MachineId['\"]\s*\)\s*\|\|\s*['\"]{2}\s*\)",
        "replace_template": 'return/*{csp_id}*/"{value}"/*{csp_id_end}*/',
        "probe_pattern": r"return\s*/\*csp3\*/[^/]+\/\*3csp\*/", 
        "prompt_message": "Windows SQM Id",
        "value_generator": lambda _=None: "",
        "csp_id": "csp3",
        "csp_id_end": "3csp",
        "os_specific": "Windows"
    },
    "dev_device_id": {
        "find_pattern": r"return\s+(?:await\s+)?(?:\(\s*await\s+)?import\s*\(\s*['\"]@vscode\/deviceid['\"]\s*\)\s*\)\s*\.getDeviceId\s*\(\s*\)",
        "replace_template": 'return/*{csp_id}*/"{value}"/*{csp_id_end}*/',
        "probe_pattern": r"return\s*/\*csp4\*/[^/]+\/\*4csp\*/",
        "prompt_message": "devDeviceId",
        "value_generator": _utils.randomuuid,
        "csp_id": "csp4",
        "csp_id_end": "4csp",
    },
}

# --- Individual Patching Functions ---

def apply_single_patch(
    data: bytes,
    patch_name: str,
    definition: dict
) -> tuple[bytes, bool, bool]: # Returns: modified_data, was_applicable, was_successful
    """
    Applies a single defined patch to the data.

    Args:
        data: The current byte string of main.js content.
        patch_name: The name of the patch (e.g., "machine_id").
        definition: The dictionary containing patterns and templates for this patch.

    Returns:
        A tuple: (modified_data, was_patch_applicable, was_patch_successful)
    """
    patch_title = patch_name.replace('_', ' ').title()
    _utils.print(f"\n{_utils.PURPLE}--- Configuring {patch_title} ---{_utils.RESET}")

    is_applicable = True
    if definition.get("os_specific") and definition["os_specific"] != _utils.SYSTEM:
        _utils.print(f"{_utils.BLUE}[INFO]{_utils.RESET} Skipping {patch_title} patch: Only applicable on {definition['os_specific']}.")
        is_applicable = False
        return data, is_applicable, False # Data unchanged, not applicable, not successful
    
    user_input_value = input(
        f"{_utils.PURPLE}{definition['prompt_message']}: {_utils.RESET}(leave blank = { 'random' if definition['value_generator'] != _utils.macaddr else 'random MAC' if definition['value_generator'] == _utils.macaddr else 'empty' if definition['prompt_message'] == 'Windows SQM Id' else 'random uuid'}) "
    ).strip()

    value_to_patch = definition["value_generator"](user_input_value) if not user_input_value else user_input_value
    
    if patch_name == "sqm_id" and not user_input_value:
        value_to_patch = "" 
    
    replace_string = definition["replace_template"].format(
        value=value_to_patch,
        csp_id=definition["csp_id"],
        csp_id_end=definition["csp_id_end"]
    )

    modified_data, main_pattern_found, patch_applied = _utils.replace(
        data,
        definition["find_pattern"],
        replace_string,
        definition["probe_pattern"],
    )

    if not main_pattern_found and not patch_applied : # Check if replace function indicated pattern not found (and no probe was found either)
        _utils.print(f"{_utils.BLUE}[INFO]{_utils.RESET} The pattern for '{patch_title}' was not found. This might be because you are using a new or significantly changed version of Cursor. If issues persist, the script's regex patterns may need updating.")
        return modified_data, is_applicable, False # Data may or may not be modified (if probe was hit), but main pattern failed

    return modified_data, is_applicable, patch_applied

# --- Main Script Logic ---

def main():
    """
    Main function to drive the patching process.
    """
    _utils.print(
        f"""
{_utils.RED}<== {_utils.PURPLE}[{_utils.RESET}Cursor Shadow Patch{_utils.PURPLE}]{_utils.RED} ==>{_utils.RESET}
- Custom machine id, mac address, etc."""
    )

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    appimage_path = None
    appimage_unpacked_dir = None
    app_bundle_path = None 
    app_bundle_tmp_path = None 

    if _utils.SYSTEM == "Linux":
        appimage_path = _utils.appimagepath(
            input(f"\n{_utils.PURPLE}Enter AppImage path: {_utils.RESET}(leave blank = auto detect) ")
        )
    elif _utils.SYSTEM == "Darwin": 
        initial_js_path_input = input(f"\n{_utils.PURPLE}Enter main.js path (inside .app bundle): {_utils.RESET}(leave blank = auto detect) ")
    else: 
        initial_js_path_input = input(f"\n{_utils.PURPLE}Enter main.js path: {_utils.RESET}(leave blank = auto detect) ")

    js_path = None
    if _utils.SYSTEM == "Windows":
        js_path = _utils.jspath(initial_js_path_input)
    
    _utils.print(f"\n{_utils.BLUE}[INFO] Checking for existing patches...{_utils.RESET}")
    all_probes = []
    for p_name in PATCH_DEFINITIONS:
        probe_bytes = PATCH_DEFINITIONS[p_name]["probe_pattern"]
        if isinstance(probe_bytes, str):
            probe_bytes = probe_bytes.encode('utf-8')
        all_probes.append(probe_bytes)

    if _utils.SYSTEM == "Linux":
        assert appimage_path is not None, "AppImage path should be set on Linux"
        appimage_unpacked_dir = _utils.appimage_unpack(appimage_path)
        js_path = _utils.jspath(_utils.appimage_detect_jspath(appimage_unpacked_dir))
    elif _utils.SYSTEM == "Darwin":
        temp_js_path_for_bundle_detection = _utils.jspath(initial_js_path_input)
        app_bundle_path = _utils.appbundle_from_jspath(temp_js_path_for_bundle_detection)
        
        _data_for_patch_check = _utils.load(temp_js_path_for_bundle_detection)
        is_patched_before_modify = _utils.chk(_data_for_patch_check, all_probes)
        del _data_for_patch_check 

        _utils.backup(app_bundle_path, not is_patched_before_modify) 
        
        app_bundle_tmp_path = _utils.appbundle_movetmp(app_bundle_path)
        _utils.appbundle_unsign(app_bundle_tmp_path)
        js_path = _utils.appbundle_to_jspath(app_bundle_tmp_path) 

    if _utils.SYSTEM == "Windows" and not js_path:
         js_path = _utils.jspath(initial_js_path_input)
    
    if not js_path or not js_path.exists():
        _utils.print(f"{_utils.RED}[ERR] main.js path could not be determined or does not exist. Exiting.{_utils.RESET}")
        _utils.pause()
        exit(1)

    _utils.print(f"\n{_utils.BLUE}[INFO] Starting patching process for main.js: {js_path}{_utils.RESET}")
    data = _utils.load(js_path)
    is_patched_initially = _utils.chk(data, all_probes) 

    if _utils.SYSTEM == "Windows": 
        _utils.backup(js_path, not is_patched_initially)

    # --- Apply Patches ---
    modified_data = data
    successful_patches_count = 0
    applicable_patches_count = 0
    skipped_os_patches_count = 0

    for patch_key, patch_definition in PATCH_DEFINITIONS.items():
        original_data_before_patch = modified_data # For checking if data actually changed
        modified_data, was_applicable, was_successful = apply_single_patch(modified_data, patch_key, patch_definition)
        
        if was_applicable:
            applicable_patches_count += 1
            if was_successful: # A patch is successful if _utils.replace made a change
                 successful_patches_count += 1
        else: # Not applicable means it was an OS-specific skip
            skipped_os_patches_count +=1


    # --- Save Modified Data ---
    if _utils.SYSTEM == "Windows": 
        _utils.remove_readonly(js_path.parent) 
        _utils.remove_readonly(js_path)      
    
    _utils.save(js_path, modified_data)

    # --- Summary ---
    _utils.print(f"\n{_utils.GREEN}--- Patching Summary ---{_utils.RESET}")
    _utils.print(f"{_utils.GREEN}[OK]{_utils.RESET} Patching process completed for '{js_path.name}'.")
    if applicable_patches_count > 0:
        _utils.print(f"{_utils.GREEN}[OK]{_utils.RESET} {successful_patches_count} out of {applicable_patches_count} applicable patch(es) were successfully applied.")
    else:
        _utils.print(f"{_utils.BLUE}[INFO]{_utils.RESET} No patches were applicable for the current OS configuration or file content.")
    
    if skipped_os_patches_count > 0:
        _utils.print(f"{_utils.BLUE}[INFO]{_utils.RESET} {skipped_os_patches_count} patch(es) were skipped due to OS incompatibility.")
    
    if successful_patches_count < applicable_patches_count:
        _utils.print(f"{_utils.YELLOW}[WARN]{_utils.RESET} Some applicable patches may not have been applied. Review the log for details (e.g., pattern not found warnings).")


    # --- Platform-Specific Post-Processing ---
    if _utils.SYSTEM == "Darwin":
        assert app_bundle_path is not None, "Original .app path missing for Darwin post-processing"
        assert app_bundle_tmp_path is not None, "Temporary .app path missing for Darwin post-processing"
        _utils.appbundle_sign(app_bundle_tmp_path) 
        _utils.appbundle_moveback(app_bundle_tmp_path, app_bundle_path) 

    elif _utils.SYSTEM == "Linux":
        assert appimage_path is not None, "AppImage path missing for Linux post-processing"
        assert appimage_unpacked_dir is not None, "Unpacked dir missing for Linux post-processing"
        _utils.backup(appimage_path, not is_patched_initially) 
        _utils.appimage_repack(appimage_path, appimage_unpacked_dir)


    # --- Cleanup ---
    _utils.print(f"\n{_utils.BLUE}[INFO] Performing cleanup...{_utils.RESET}")
    
    tmp_dir_to_clean = None
    if _utils.SYSTEM == "Windows":
        appdata = os.getenv("APPDATA", "")
        if appdata:
            tmp_dir_to_clean = _utils.path(appdata) / "Cursor"
    elif _utils.SYSTEM == "Linux":
        home = os.getenv("HOME", "")
        if home:
            tmp_dir_to_clean = _utils.path(home) / ".config" / "Cursor" 
    elif _utils.SYSTEM == "Darwin":
        home = os.getenv("HOME", "")
        if home:
            tmp_dir_to_clean = _utils.path(home) / "Library" / "Application Support" / "Cursor"
    
    if tmp_dir_to_clean and tmp_dir_to_clean.exists():
        _utils.cleantmp(tmp_dir_to_clean) 
        _utils.print(f"{_utils.GREEN}[OK]{_utils.RESET} Cache and config cleanup attempted for {tmp_dir_to_clean}.")
    else:
        _utils.print(f"{_utils.YELLOW}[WARN] Could not determine temp directory for cleanup or directory does not exist.{_utils.RESET}")

    _utils.print(f"\n{_utils.GREEN}*** Overall process completed! ***{_utils.RESET}")
    _utils.pause()

if __name__ == "__main__":
    main()
