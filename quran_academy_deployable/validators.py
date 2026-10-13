"""Server-side validation and sanitization of all user-submitted data."""
import re

from db import CLASS_FORMATS, READING_LEVELS, SCHEDULES

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-()]{6,19}$")


def clean_text(value, max_len: int = 300, required: bool = False,
               field: str = "", label: str = ""):
    """Normalize a text input. Returns (error, cleaned)."""
    name = label or field.replace("_", " ").title()
    if value is None:
        value = ""
    if not isinstance(value, str):
        return (f"{name} is invalid.", "") if required else ("", "")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value).strip()
    if required and not cleaned:
        return f"{name} is required.", ""
    if len(cleaned) > max_len:
        return f"{name} is too long (maximum {max_len} characters).", ""
    return "", cleaned


def clean_phone(value, field: str, label: str, required: bool):
    name = label or field.replace("_", " ").title()
    if value is None:
        value = ""
    value = str(value).strip()
    if not value:
        if required:
            return f"{name} is required.", ""
        return "", ""
    digits = re.sub(r"\D", "", value)
    if not PHONE_RE.match(value) or len(digits) < 7 or len(digits) > 15:
        return (f"{name} must be a valid phone number including country code "
                f"(for example +251912345678)."), ""
    return "", re.sub(r"\s+", " ", value)


def clean_email(value, required: bool):
    if value is None:
        value = ""
    value = str(value).strip()
    if not value:
        return ("Email address is required.", "") if required else ("", "")
    if len(value) > 120 or not EMAIL_RE.match(value):
        return "Please enter a valid email address (for example name@example.com).", ""
    return "", value.lower()


def clean_age(value):
    if value is None or value == "":
        return "Student's age is required.", None
    try:
        age = int(str(value).strip())
    except (TypeError, ValueError):
        return "Student's age must be a number.", None
    if not 3 <= age <= 110:
        return "Student's age must be between 3 and 110.", None
    return "", age


def _in_enum(value, allowed, label):
    if not value:
        return "", ""
    if value not in allowed:
        return f"{label} is invalid.", ""
    return "", value


def validate_registration(data: dict) -> tuple[dict, dict]:
    """Returns (errors_by_field, cleaned_values)."""
    errors: dict[str, str] = {}
    out: dict = {}

    def put(field, err, val):
        if err:
            errors[field] = err
        else:
            out[field] = val

    put("full_name", *clean_text(data.get("full_name"), 120, True, "full_name",
                                 "Student's full name"))
    put("age", *clean_age(data.get("age")))
    put("country", *clean_text(data.get("country"), 60, True, "country"))
    put("city", *clean_text(data.get("city"), 60, True, "city", "City or location"))
    put("phone", *clean_phone(data.get("phone"), "phone", "Phone number", True))
    put("whatsapp", *clean_phone(data.get("whatsapp"), "whatsapp",
                                 "WhatsApp number", False))
    put("email", *clean_email(data.get("email"), False))
    put("gender", *clean_text(data.get("gender"), 20, False))
    put("previous_experience", *clean_text(data.get("previous_experience"), 500))
    put("learning_goals", *clean_text(data.get("learning_goals"), 1000,
                                      False, "learning_goals", "Learning goals or notes"))
    put("referral_source", *clean_text(data.get("referral_source"), 120))
    put("parent_name", *clean_text(data.get("parent_name"), 120))
    put("parent_phone", *clean_phone(data.get("parent_phone"), "parent_phone",
                                     "Parent or guardian contact number", False))

    put("reading_level", *_in_enum(data.get("reading_level"), READING_LEVELS,
                                   "Current Quran reading level"))
    if not out.get("reading_level"):
        errors["reading_level"] = "Please select the student's current Quran reading level."

    put("preferred_schedule", *_in_enum(data.get("preferred_schedule"), SCHEDULES,
                                        "Preferred learning schedule"))
    if not out.get("preferred_schedule"):
        errors["preferred_schedule"] = "Please select a preferred learning schedule."

    put("class_format", *_in_enum(data.get("class_format"), CLASS_FORMATS,
                                  "Preferred class format"))

    age = out.get("age")
    if age is not None and age < 18:
        if not out.get("parent_name"):
            errors["parent_name"] = ("A parent or guardian's full name is required "
                                     "for students under 18.")
        if not out.get("parent_phone"):
            errors["parent_phone"] = ("A parent or guardian's contact number is required "
                                      "for students under 18.")

    if errors:
        return errors, {}
    return {}, out


def validate_contact(data: dict) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    out: dict = {}

    err, val = clean_text(data.get("name"), 120, True, "name", "Your name")
    if err:
        errors["name"] = err
    else:
        out["name"] = val

    err, val = clean_email(data.get("email"), False)
    if err:
        errors["email"] = err
    else:
        out["email"] = val

    err, val = clean_phone(data.get("phone"), "phone", "Phone number", False)
    if err:
        errors["phone"] = err
    else:
        out["phone"] = val

    err, val = clean_text(data.get("message"), 2000, True, "message", "Message")
    if err:
        errors["message"] = err
    else:
        out["message"] = val

    if not out.get("email") and not out.get("phone"):
        errors["email"] = "Please provide an email address or a phone number so the academy can reply."

    if errors:
        return errors, {}
    return {}, out
