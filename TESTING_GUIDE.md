# GhostPush Beta Testing Guide

Welcome to the GhostPush External Beta! This document provides a complete step-by-step testing plan for evaluating GhostPush on a Windows environment.

---

## 1. System Requirements & Setup

### Prerequisites
- **Operating System**: Windows 10 or Windows 11 (64-bit).
- **Browser**: Google Chrome or Brave (Manifest V3 extension support).
- **AI Provider Key**: An API key from Google Gemini, OpenAI, Anthropic, Groq, or OpenRouter.

### Installation Steps
1. Unzip the `GhostPush-Beta-Release.zip` archive into any directory (e.g. `C:\GhostPush`).
2. Run `GhostPush.exe`. The application will start silently in your Windows System Tray (system notification area at bottom-right).
3. Right-click the **GhostPush** icon in the system tray (indigo icon with a 'G') and select **Configuration**.

---

## 2. Step-by-Step Testing Walkthrough

### Test Case 1: First-Time Initialization & Unconfigured Status
- **Action**: Open **Configuration**.
- **Expected Outcome**:
  - The status label displays: `⚠ Gemini API key not configured` (in orange/warning text).
  - The **Save API Key** button is enabled.
  - The **Remove API Key** and **Test AI Connection** buttons are disabled.
  - No secret keys exist in `config.json` or `.env`.

### Test Case 2: Entering and Saving an AI API Key
- **Action**:
  1. Select your preferred AI Provider (e.g., `gemini`).
  2. Enter your API key into the **AI API Key** field.
  3. Click **Show** / **Hide** to verify masking works.
  4. Click **Save API Key**.
- **Expected Outcome**:
  - The key field clears immediately.
  - The window **never freezes** or displays "Not Responding".
  - Status immediately displays `✓ API key saved. Testing connection...`.
  - Within 1–3 seconds, status updates to `✓ Gemini connection successful` (in green text).
  - System Tray icon status displays: `Backend: Running | AI: Gemini Connected`.

### Test Case 3: Test AI Connection
- **Action**: Click **Test AI Connection**.
- **Expected Outcome**:
  - Status updates asynchronously to `● Testing Gemini connection...` without freezing.
  - Final status returns to `✓ Gemini connection successful`.

### Test Case 4: Invalid API Key Test
- **Action**:
  1. Enter an invalid string (e.g., `AIzaSyInvalidTestKey123`).
  2. Click **Save API Key**.
- **Expected Outcome**:
  - Status updates asynchronously to `✗ Gemini API key is invalid` (in red text).
  - The application remains completely responsive and does not crash.

### Test Case 5: Remove API Key
- **Action**: Click **Remove API Key**.
- **Expected Outcome**:
  - Confirmation prompt appears.
  - Key is removed from `%APPDATA%\GhostPush\.env`.
  - Status immediately returns to `⚠ Gemini API key not configured`.
  - **Test AI Connection** and **Remove API Key** buttons return to disabled state.

### Test Case 6: Provider Switching
- **Action**:
  1. Select `gemini` and configure a key.
  2. Switch the **AI Provider** dropdown to `openai`.
- **Expected Outcome**:
  - Status immediately recalculates for `openai` (`⚠ Openai API key not configured`).
  - Gemini's key is not shared with OpenAI.

### Test Case 7: Chrome Extension Installation & Metadata Extraction
- **Action**:
  1. Open Chrome → `chrome://extensions`.
  2. Enable **Developer Mode** (top-right toggle).
  3. Click **Load unpacked** and select the `_internal/extension` folder inside the GhostPush distribution folder.
  4. Navigate to a competitive programming problem on LeetCode (e.g. `https://leetcode.com/problems/two-sum/`).
  5. Click the GhostPush Chrome Extension icon in your browser toolbar.
  6. Click **⚡ Extract Page Metadata**.
- **Expected Outcome**:
  - Platform auto-fills: `LeetCode`.
  - Problem Title auto-fills: `Two Sum` (or title without leading numbers).
  - Difficulty auto-fills: `Easy` / `Medium` / `Hard`.
  - Tags auto-fill: `Array, Hash Table` (non-empty).
  - Language auto-detects based on editor state/code (e.g., `Java` for Java solutions, `Python` for Python).

### Test Case 8: Solution Push & Repository Generation (Golden Path)
- **Action**:
  1. Write or paste a Java solution into the editor on LeetCode:
     ```java
     class Solution {
         public int[] twoSum(int[] nums, int target) {
             for (int i = 0; i < nums.length; i++) {
                 for (int j = i + 1; j < nums.length; j++) {
                     if (nums[i] + nums[j] == target) {
                         return new int[]{i, j};
                     }
                 }
             }
             return new int[]{};
         }
     }
     ```
  2. Ensure Local Repository path points to a valid folder on your computer.
  3. Click **🚀 Push Solution**.
- **Expected Outcome**:
  - Notification toast/status in popup displays job progress (`QUEUED` → `PROCESSING` → `GENERATING_README` → `WRITING_FILES` → `COMPLETED`).
  - In your target local repository folder, a folder `LeetCode/Two Sum/` is created containing:
    - `Solution.java` (containing the exact Java code submitted).
    - `metadata.json` containing:
      ```json
      {
        "platform": "leetcode",
        "title": "Two Sum",
        "difficulty": "Easy",
        "url": "https://leetcode.com/problems/two-sum/",
        "tags": ["Array", "Hash Table"],
        "language": "java"
      }
      ```
    - `README.md` containing formatted problem description, complexity analysis, language badge (`Java`), platform badge (`LeetCode`), problem URL, and Java solution block.

---

## 3. Reporting Issues

If you encounter any unexpected behavior, freeze, error, or data mismatch, please fill out `BUG_REPORT_TEMPLATE.md` and send it to the development team.
