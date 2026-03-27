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


class ProfileLocators:
    """Selectors for the profile update widgets."""

    # ── Resume Headline ───────────────────────────────────────────────────────
    HEADLINE_EDIT = [
        ".widgetHead:has(.widgetTitle:text('Resume headline')) span.edit.icon",
        ".widgetHead:has(.widgetTitle:text('Resume Headline')) span.edit.icon",
    ]
    HEADLINE_FORM = "form[name='resumeHeadlineForm']"
    HEADLINE_INPUT = ["textarea#resumeHeadlineTxt"]
    HEADLINE_SAVE = ["form[name='resumeHeadlineForm'] button.btn-dark-ot"]

    # ── Profile Summary ───────────────────────────────────────────────────────
    SUMMARY_EDIT = [
        ".widgetHead:has(.widgetTitle:text('Profile summary')) span.edit.icon",
        ".widgetHead:has(.widgetTitle:text('Profile Summary')) span.edit.icon",
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
