# ─────────────────────────────────────────────────────────────────────────────
# Naukri UI Selectors — single source of truth for all CSS/XPath locators.
# Add selectors here as new services are built. Never hardcode selectors
# inside service files.
# ─────────────────────────────────────────────────────────────────────────────


class LoginLocators:
    """Selectors for the login nav trigger and login form."""

    NAV_TRIGGER = [
        "a[href*='nlogin']",
        "a.nI-gNb-lg1__login",
        "a[title='Jobseeker Login']",
        "a[title='Login']",
        ".login-register a",
    ]

    EMAIL = [
        "input#usernameField",
        "input[placeholder*='Enter your active Email' i]",
        "input[type='text'][name='username']",
        "input[name='username']",
    ]

    PASSWORD = [
        "input#passwordField",
        "input[type='password'][name='password']",
        "input[placeholder*='password' i]",
        "input[name='password']",
    ]

    SUBMIT = [
        "button.loginButton",
        "button[type='submit']:has-text('Login')",
        "button[type='submit']",
        "input[type='submit']",
    ]


class OTPLocators:
    """Selectors for OTP verification screen."""

    # 6 split input fields (one digit each)
    SPLIT_FIELDS = [
        "input#Input_1",
        "input#Input_2",
        "input#Input_3",
        "input#Input_4",
        "input#Input_5",
        "input#Input_6",
    ]

    # Single combined OTP field (fallback)
    SINGLE_FIELD = [
        "input#otpField",
        "input.otpInput",
        "input[autocomplete='one-time-code']",
        "input[type='tel'][maxlength='6']",
        "input[maxlength='6']",
    ]

    SUBMIT = [
        "button.verify-button",
        "button.loginButton",
        "button[type='submit']:has-text('Verify')",
        "button[type='submit']:has-text('Submit')",
        "button[type='submit']:has-text('Continue')",
        "button[type='submit']",
    ]


class JobLocators:
    """Selectors for job search listing pages, detail pages, and apply flow."""

    # ── Job list page ─────────────────────────────────────────────────────────
    # Outer wrapper — carries data-job-id attribute
    JOB_CARDS = ["div.srp-jobtuple-wrapper"]

    # Within each card (scoped to card element via .locator())
    CARD_TITLE      = "a.title"           # <h2><a class="title ">
    CARD_COMPANY    = "a.comp-name"       # <a class=" comp-name mw-25">
    CARD_SALARY     = ".sal-wrap, .salary, .sal"
    CARD_EXP        = "span.expwdth"      # <span class="expwdth">1-3 Yrs</span>
    CARD_POSTED     = "span.job-post-day" # <span class="job-post-day ">4 days ago</span>
    CARD_APPLICANTS = ".applicants, .applied-count, span[title*='applicant' i]"
    CARD_EASY_APPLY = ".easy-apply, [class*='chat-apply'], .ic-label-container"

    # ── Sort by date (two-step: open dropdown → click Date) ───────────────────
    # Step 1 — open the sort dropdown
    SORT_DROPDOWN_TRIGGER = [
        "button#filter-sort",
        "button[id='filter-sort']",
    ]
    # Step 2 — click the Date option inside the open dropdown
    SORT_DATE_OPTION = [
        "a[data-id='filter-sort-f']",
        "li[title='Date'] a",
    ]
    # Read the active sort label to verify Date is selected
    SORT_ACTIVE_LABEL = "button#filter-sort span"

    # ── Pagination ────────────────────────────────────────────────────────────
    # Pagination lives in <div id="lastCompMark">
    # Next button: <a href="/slug-2" class="styles_btn-secondary__..."><span>Next</span></a>
    # Previous button has disabled="" when on page 1
    NEXT_PAGE = [
        "#lastCompMark a:has-text('Next')",
        "#lastCompMark a[class*='btn-secondary']:not([disabled])",
        "a[class*='btn-secondary']:not([disabled]):has-text('Next')",
        "a[class*='btn-secondary']:has(span):not([disabled])",
    ]

    # ── Job detail page ───────────────────────────────────────────────────────
    DETAIL_DESCRIPTION = [
        ".job-desc",
        "#job-description",
        ".jd-desc",
        ".jobDescContainer .desc",
    ]
    DETAIL_SKILLS = [
        ".key-skill",
        "ul.tags-gt li.tag-li",
        ".chip-list .chip",
        ".skills-list li",
    ]
    # Easy apply detection — stable id="apply-button" confirmed from real DOM
    DETAIL_EASY_APPLY = [
        "button#apply-button",
        "button.apply-button",
    ]

    # ── Easy apply flow ───────────────────────────────────────────────────────
    APPLY_BUTTON = [
        "button#apply-button",
        "button.apply-button",
    ]
    ALREADY_APPLIED = [
        ".already-applied",
        "button:has-text('Applied')",
        "span:has-text('Already Applied')",
    ]

    # Direct-apply success — shown when Naukri applies without a chatbot drawer
    APPLY_SUCCESS = [
        ".apply-success",
        "[class*='apply-success']",
        "[class*='applySuccess']",
        "div:has-text('Application submitted')",
        "div:has-text('Successfully applied')",
        "div:has-text('applied successfully')",
        "button[disabled]:has-text('Applied')",
        "button.applied",
    ]


class ChatbotLocators:
    """Selectors for Naukri's chatbot-based easy apply drawer."""

    # Drawer container — appears after clicking Apply
    DRAWER          = "div.chatbot_DrawerContentWrapper"

    # Last bot question text (read before answering)
    LAST_BOT_MSG    = "li.botItem:last-of-type div.botMsg span"

    # All bot messages (used to detect when a new one arrives)
    ALL_BOT_MSGS    = "li.botItem"

    # Clickable chip options (Yes / No / other single-click answers)
    CHIP_OPTIONS    = [
        "li.botItem:last-of-type .chip",
        "li.botItem:last-of-type [class*='chip']",
        "li.botItem:last-of-type button",
        ".botItem:last-of-type .option",
    ]

    # Free-text input field
    TEXT_INPUT      = "div.textArea[contenteditable='true']"

    # Send / Save button (enabled once text is entered)
    SEND_BTN        = "div.sendMsg"

    # Success detection — "Thank you" message from bot
    SUCCESS_TEXT    = "Thank you"

    # Close button (X) on the drawer
    CLOSE_BTN       = "div.crossIcon.chatBot"


class ProfileLocators:
    """Selectors for the profile update widgets."""

    # ── Resume Headline ───────────────────────────────────────────────────────
    HEADLINE_READ = [
        "#resumeHeadlineSection .headline",
        ".resumeHeadlinePara .para",
        "[class*='headlineSection'] .para",
        "[data-section='headline'] .para",
    ]
    HEADLINE_EDIT = [
        "#lazyResumeHead .widgetHead span.edit.icon",
        ".resumeHeadline .widgetHead span.edit.icon",
        ".widgetHead:has(.widgetTitle:text('Resume headline')) span.edit.icon",
        ".widgetHead:has(.widgetTitle:text('Resume Headline')) span.edit.icon",
    ]
    HEADLINE_FORM = "form[name='resumeHeadlineForm']"
    HEADLINE_INPUT = ["textarea#resumeHeadlineTxt"]
    HEADLINE_SAVE = ["form[name='resumeHeadlineForm'] button.btn-dark-ot"]

    # ── Profile Summary ───────────────────────────────────────────────────────
    SUMMARY_READ = [
        "#profileSummarySection .summary",
        ".profileSummarySection .para",
        "[class*='summarySection'] .para",
        "[data-section='summary'] .para",
    ]
    SUMMARY_EDIT = [
        "#lazyProfileSummary .widgetHead span.edit.icon",
        ".profileSummary .widgetHead span.edit.icon",
        ".widgetHead:has(.widgetTitle:text('Profile summary')) span.edit.icon",
        ".widgetHead:has(.widgetTitle:text('Profile Summary')) span.edit.icon",
        ".widgetHead:has-text('Profile summary') span.edit.icon",
        ".widgetHead:has-text('Profile Summary') span.edit.icon",
    ]
    SUMMARY_FORM = "form[name='profileSummaryForm']"
    SUMMARY_INPUT = ["textarea#profileSummaryTxt"]
    SUMMARY_SAVE = ["form[name='profileSummaryForm'] button.btn-dark-ot"]

    # ── Resume Upload ─────────────────────────────────────────────────────────
    RESUME_UPLOAD = ["input#attachCV", "input.fileUpload"]

    # ── Resume Replace Confirmation ───────────────────────────────────────────
    RESUME_CONFIRM = [
        ".res360editconfirmationBox a.btn-dark-ot",
        ".res360editconfirmationBox button.btn-dark-ot",
    ]
