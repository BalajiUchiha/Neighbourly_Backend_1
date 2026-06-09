SUPPORTED_UI_LANGUAGES = ["tamil", "english"]

TRANSLATIONS = {
    "tamil": {
        "welcome": "வணக்கம்",
        "work_near_you": "உங்களுக்கு அருகில் வேலை",
        "help_around_you": "உங்கள் சமூகத்திற்கு உதவுங்கள்",
        "around_me": "என் அருகில்",
        "for_me": "என்னிற்காக",
        "part_time": "பகுதி நேரம்",
        "volunteer": "தொண்டு செய்க",
        "no_experience": "அனுபவம் தேவையில்லை",
        "my_posts": "என் பதிவுகள்",
        "post_a_task": "பணி பதிவிடு",
        "apply": "விண்ணப்பிக்க",
        "login": "உள்நுழை",
        "signup": "பதிவு செய்",
        "logout": "வெளியேறு"
    },
    "english": {
        "welcome": "Welcome",
        "work_near_you": "Work near you",
        "help_around_you": "Help around you",
        "around_me": "Around Me",
        "for_me": "For Me",
        "part_time": "Part Time",
        "volunteer": "Volunteer",
        "no_experience": "No Experience",
        "my_posts": "My Posts",
        "post_a_task": "Post a Task",
        "apply": "Apply",
        "login": "Login",
        "signup": "Sign Up",
        "logout": "Logout"
    }
}

def get_translation(language: str, key: str) -> str:
    if language not in SUPPORTED_UI_LANGUAGES:
        language = "english"
    return TRANSLATIONS[language].get(key, TRANSLATIONS["english"].get(key, key))
