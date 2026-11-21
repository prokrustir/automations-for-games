"""Every template the script uses: file name (without .png) -> what to capture.

Optional templates are marked; everything else is required for the flow that uses it.
"""

TEMPLATES: dict[str, str] = {
    # --- FM: session start ---
    "fm_start_most_recent": "FM start screen: the title 'Load Most Recent Career' of the top-left tile",
    "fm_start_load_game": "FM start screen: the 'Load Game' tile title (fallback, picks the newest Wieczysta save) (optional)",
    # --- FM: holiday ---
    "fm_calendar": "Portal submenu: the word 'Calendar'",
    "fm_go_on_holiday": "Calendar page: 'Go On Holiday' button",
    "fm_return_date_label": "Holiday dialog: the text 'Return from holiday on date:' (dropdown is clicked at an offset from it)",
    "fm_next_match_option": "Holiday dropdown (open): the words 'Next match' (without the date)",
    "fm_confirm_holiday": "Holiday dialog: 'Confirm Holiday' button",
    # --- FM: match day ---
    "fm_review_team_selection": "Top-right purple button: 'Review Team Selection'",
    "fm_go_to_match": "Top-right purple button: 'Go To Match'",
    "fm_instant_result": "Team Selection screen: 'Instant Result' button",
    "fm_dialog_confirm": "Instant Result dialog: 'Confirm' button",
    "fm_dialog_yes": "'Proceed with simulate match?' dialog: 'Yes' button",
    "fm_dialog_ok": "'<player> is injured, and is unavailable' dialog: 'Ok' button",
    "fm_continue": "Top-right purple button: 'Continue'",
    "fm_bn_header": "Result screen title: 'Breaking News'",
    "fm_our_crest": "Wieczysta crest as shown on the big Breaking News result card",
    "fm_latest_results": "Breaking News: 'Latest Results' button (top right)",
    # --- FM: reload ---
    "fm_settings": "Top bar: gear (Settings) icon",
    "fm_load_game": "FM Menu: 'Load Game' button",
    "fm_dialog_no": "'Save before you load another game?' dialog: 'No' button",
    "fm_save_row": "Load game list: the text 'Kolo Kolo - Wieczysta Krak' (name only, no date)",
    "fm_load_btn": "Load game list: left part of the purple 'Load' button (Steam toast can cover the right part)",
    # --- FM: inbox ---
    "fm_messages_tab": "Portal submenu: the word 'Messages'",
    "fm_unread_filter": "Messages list: the purple 'Unread (N)' pill (capture only 'Unread', not the number)",
    "fm_mark_all_read": "Messages list: green double tick 'Mark all as read' icon",
    # --- FMRTE (fallbacks if UI Automation can't find the buttons) ---
    "fmrte_heal": "FMRTE right menu: 'Heal'",
    "fmrte_ok": "FMRTE 'Please reload your save' dialog: 'Ok' button",
    "fmrte_load_game": "FMRTE top right: purple 'Load Game' button",
    "fmrte_reload_prompt": "FMRTE dialog title 'Please reload your save'",
    "fmrte_favorites": "FMRTE top bar: 'Favorites' (normal state, menu closed, mouse elsewhere)",
    "fmrte_game_loaded": "FMRTE status bar bottom-left: 'Game was loaded' (optional, speeds up loading)",
    "fmrte_fav_manager": "FMRTE Favorites menu: 'Kolo Kolo'",
    "fmrte_fav_club": "FMRTE Favorites > Kolo Kolo submenu: 'Wieczysta Kraków'",
    "fmrte_club_tab": "FMRTE purple tab header 'Wieczysta Kraków' next to 'FM - Real Time Editor' (optional)",
    "fmrte_squads_menu": "FMRTE club page, left menu: 'Squads'",
    "fmrte_first_team_tab": "FMRTE squad sub-tab 'Wieczysta Kraków' (first one, left) (optional)",
    "fmrte_first_team_marker": "Something only in the first-team list, e.g. 'Mario Balotelli' (optional)",
}

OPTIONAL = {k for k, v in TEMPLATES.items() if "(optional)" in v}
