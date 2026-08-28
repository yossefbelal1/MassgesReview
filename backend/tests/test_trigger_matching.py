import pytest
from backend.app.services.job_engine import matches_trigger

def test_url_does_not_trigger_short_keywords():
    # https:// has 'tp' inside 'http' but should NEVER trigger 'TP'
    msg_url = "سهرانين نراقب السيولة الآسيوية 🥷 في فرصة ممتازة بتتكون دلوقتي، هننزلها حصري هنا 👇 https://t.me/+RW0Hx9vCk1UyNmFk"
    assert matches_trigger(msg_url, "TP", "contains") is False
    assert matches_trigger(msg_url, "tp", "contains") is False
    assert matches_trigger(msg_url, "me", "contains") is False
    assert matches_trigger(msg_url, "http", "contains") is False

def test_legitimate_keywords_match():
    assert matches_trigger("ضربنا TP اليوم بالكامل يا شباب 🔥", "TP", "contains") is True
    assert matches_trigger("الهدف الأول TP1 تم بنجاح", "TP1", "contains") is True
    assert matches_trigger("الهدف الثاني TP2", "TP2", "contains") is True
    assert matches_trigger("شاركونا رأيكم في صفقات اليوم", "شاركونا", "contains") is True
    assert matches_trigger("رايكم في الصفقة؟", "رايكم", "contains") is True

def test_partial_word_substrings_do_not_match():
    # 'output' has 'tp' inside it, shouldn't match 'tp'
    assert matches_trigger("This is an output message", "TP", "contains") is False
    # 'laptop' has 'tp' inside it
    assert matches_trigger("Working on my laptop", "TP", "contains") is False
