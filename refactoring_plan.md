# Refactoring and Enhancement Plan

This document tracks the progress of implementing various fixes, changes, and features identified in the codebase.

## Planned Items:

1.  **[x] Logger Refinements (`utils/logger.py`)**
    *   [x] Consolidate the two `setup_logger` methods.
    *   [x] Modify `log_message` to use `self.logger.info()` for `app.log` and remove direct `app_file.write()`.
    *   [x] Correct `error(self, message)` method to use `self.logger.error()`.
    *   [x] Remove redundant `FileNotFoundError` `except` block in `load_bad_patterns`.

2.  **[ ] Text-to-Speech (TTS) Enhancements (`utils/tts.py`)**
    *   [ ] Enhance `async def process_text` for dynamic channel-specific `voice_preset` and `bark_model`.
    *   [ ] Ensure `async def process_text` consistently logs to `tts_logs` and calls `notify_new_audio_available`.
    *   [ ] Clarify/consolidate primary TTS generation path (`async def process_text` vs. `process_text_thread`).

3.  **[ ] JavaScript Audio Toggle Conflict Resolution (`static/scripts/notification.js`, `static/scripts/event_listener.js`)**
    *   [ ] Remove `initAudioToggle` from `static/scripts/notification.js`.
    *   [ ] Ensure `setupAutoplayToggle` in `static/scripts/event_listener.js` is the sole controller.

4.  **[ ] Standardize Cache Build Time Storage Format (`utils/bot.py`, `utils/markov_handler.py`)**
    *   [ ] Migrate `cache_build_times.json` fully to a dictionary format.
    *   [ ] Remove backward compatibility logic for list format in `utils/bot.py`.
    *   [ ] Update `utils/markov_handler.py`'s `record_build_time` to save in dictionary format.

5.  **[ ] Streamline Bot Channel Joining and Status (`utils/bot.py`)**
    *   [ ] Refactor channel joining logic in `event_ready` and `check_and_join_channels`.
    *   [ ] Centralize management of `currently_connected` status in `channel_configs` table.

6.  **[ ] Improve Inter-Process Communication (IPC) for Bot Commands (`utils/bot.py`, `webapp.py`)**
    *   *This is a larger feature and might be broken down further.*
    *   [ ] Plan and implement a replacement for the file-based request system (e.g., message queue, local socket).

7.  **[ ] Refactor `webapp.py` Bot Status Determination**
    *   [ ] Simplify `is_bot_actually_running` function.
    *   [ ] Streamline bot status verification in `/send_markov_message/<channel_name>` endpoint.

8.  **[ ] Centralize Bot Status UI Updates in JavaScript (`static/scripts/bot_status.js`)**
    *   [ ] Ensure `window.BotStatus.init()` is the definitive source for UI status.
    *   [ ] Reduce direct `checkBotStatus()` calls in other JS files, relying on events/state from `BotStatus`.

9.  **[ ] Database Schema and Usage for `tts_logs.message_id` (`utils/db_setup.py`, `utils/tts.py`)**
    *   [ ] Clarify if `tts_logs.message_id` is PK or FK.
    *   [ ] If PK, ensure `AUTOINCREMENT` in `utils/db_setup.py`.
    *   [ ] Adjust `log_tts_to_db` in `utils/tts.py` accordingly.

10. **[ ] Markov Model Loading Consistency (`utils/markov_handler.py`)**
    *   [ ] Ensure models loaded from cache (initially or on-demand) are consistently stored as `markovify.Text` objects in `self.models`.

## Progress Legend:
- `[ ]` - Not started
- `[/]` - In progress
- `[x]` - Completed
