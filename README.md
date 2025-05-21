> [!NOTE]  
> This tool has been recently updated to improve its robustness and maintainability for newer versions of Cursor. However, Cursor's internal structure can change frequently, and future updates to the application might still require adjustments to this script's patching logic.

# Cursor Shadow Patch

This script patches Cursor's `main.js` file to allow customization of identifiers such as machine ID, MAC address, and others. This can be useful for users experiencing issues with Cursor's default ID generation mechanisms preventing access to their accounts.

**Disclaimer: This tool is intended solely to help users fix issues preventing them from using their own legitimate Cursor account due to internal machine ID retrieval problems. It must not be used for automated account registration, trial abuse, or any other activities that violate Cursor's terms of service. Please respect the developers and use Cursor responsibly.**

## Key Features

*   Modifies `main.js` to use custom or randomly generated values for:
    *   Machine ID
    *   MAC Address
    *   SQM ID (Windows-specific)
    *   Developer Device ID (devDeviceId)
*   Platform-specific handling for:
    *   Windows (direct `main.js` patching)
    *   Linux (AppImage unpacking, patching, and repacking)
    *   macOS (App Bundle copying, unsigning, patching, and re-signing)
*   Robust detection of Cursor installation paths and the target `main.js` file across platforms.
*   Automated backup of critical files (`main.js`, AppImage, or App Bundle) before patching.
*   Cleaning of certain temporary/cache files that might store old identifiers to complement the patching.

## Supported Versions

*   **Cursor:** Designed to be adaptable to various Cursor versions due to more flexible path detection and regex patterns. However, compatibility with the absolute latest version of Cursor is not guaranteed, as breaking changes in `main.js` can occur.
*   **Python:** Python 3.10 or newer is required.

## Usage Instructions

1.  **Get the Patcher:**
    *   Clone this project: `git clone https://github.com/zetaloop/cursor-shadow-patch.git`
    *   Alternatively, [download the ZIP archive](https://github.com/zetaloop/cursor-shadow-patch/archive/refs/heads/main.zip) and extract it.
    *   Navigate into the `cursor-shadow-patch` directory in your terminal.

2.  **Ensure Python Version:**
    *   Make sure you have Python 3.10 or a newer version installed and accessible from your terminal. You can check with `python --version` or `python3 --version`.

3.  **Run the Patcher:**
    *   Execute the script from your terminal: `python patcher.py` (or `python3 patcher.py` depending on your system's Python setup).

4.  **Follow Prompts:**
    *   The script will attempt to automatically detect your Cursor installation. If it cannot, it will prompt you for the path to `main.js` (Windows/macOS) or the Cursor AppImage (Linux).
    *   It will then ask for values for each identifier it can patch (some are OS-specific). You can generally press <kbd>Enter</kbd> at each prompt to accept a randomly generated value or a sensible default (e.g., an empty string for Windows SQM ID).

5.  **Check Output:**
    *   Observe the script's output. Green `[OK]` messages indicate success for specific steps.
    *   Pay attention to any yellow `[WARN]` or red `[ERR]` messages, especially regarding pattern matching.
    *   A summary at the end will indicate how many patches were successfully applied out of the applicable ones for your OS. If most applicable patches are successful, you should be good to go.

6.  **Re-run When Needed:**
    *   Run the patcher again if you update Cursor (as the `main.js` will be overwritten), or if you need to change the patched identifiers.

## Troubleshooting & Adapting to New Cursor Versions

Cursor is updated frequently. If the application's internal JavaScript code (especially in `main.js`) changes significantly, this patcher might fail to find the necessary code patterns to modify.

**Symptoms of Failure:**

*   During script execution, you might see `[WARN]` or `[INFO]` messages indicating that a "pattern was not found" for one or more patches.
*   The final summary may show that fewer patches were applied than expected for your OS, or that some applicable patches failed.

**How to Potentially Fix It (For Technical Users):**

The core patching logic relies on Regular Expressions (regex) defined in a dictionary named `PATCH_DEFINITIONS` at the beginning of the `patcher.py` file. Each entry in this dictionary contains patterns (`find_pattern`, `probe_pattern`) used to locate and verify the code to be modified.

If the script fails after a Cursor update, these regex patterns likely need adjustment:

1.  **Locate `main.js`:** You'll need to find the `main.js` file for your Cursor installation.
    *   **Windows/macOS:** The patcher attempts to print this path when it loads the file. You can also manually locate it within the Cursor application's resources.
    *   **Linux (AppImage):** You'll need to unpack the AppImage first. The patcher does this into a `squashfs-root` directory in the same folder where you run `patcher.py`. The `main.js` is usually found in a path like `squashfs-root/resources/app/out/main.js`.
2.  **Inspect `main.js`:** Open `main.js` in a text editor (it will likely be minified and hard to read; using a JavaScript beautifier can help). Search for code snippets related to the functionality you expect to be patched (e.g., parts of functions that retrieve `machineId`, `getMacAddress`, `sqmId`, or `getDeviceId`).
3.  **Update `PATCH_DEFINITIONS`:** Carefully compare the JavaScript code you find with the regex patterns in `patcher.py` for the failing patch(es). You may need to adjust the `find_pattern` (the search pattern) and `probe_pattern` (to detect already patched code) to match the new code structure in `main.js`. The existing patterns provide a good starting point.
4.  **Test:** After saving your modifications to `patcher.py`, re-run it to see if your updated patterns work.

This process requires some understanding of JavaScript and Regular Expressions. While efforts are made to keep the patcher's patterns robust, community contributions or self-updates might be necessary if Cursor's code changes significantly.

## Important Notes

*   **IP Address and Email:** Changing the machine ID and other script-modified identifiers may not be sufficient if Cursor employs other methods for tracking, such as IP address or email account blocks.
*   **Backup:** The script automatically creates backups of `main.js` (or the entire AppImage/AppBundle on Linux/macOS) before making modifications. These backups will typically have a `.bak` extension (e.g., `main.js.bak` or `Cursor.AppImage.bak`).
*   **Idempotency:** The script is designed to be idempotent. If a patch is already applied (based on "probe" patterns in the regex), it will attempt to overwrite it with the new value you provide. If a pattern isn't found, it will be skipped.

Please use this tool responsibly and ethically. Contributions to improve its robustness are welcome.
