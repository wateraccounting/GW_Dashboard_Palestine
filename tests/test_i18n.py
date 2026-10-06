"""English and Arabic text must stay in sync."""
import string

from gw_dashboard.i18n import TEXT, tr


def fields(s):
    return {f for _, f, _, _ in string.Formatter().parse(s) if f}


def test_same_keys_in_every_language():
    assert set(TEXT["ar"]) == set(TEXT["en"])


def test_same_placeholders_in_every_language():
    for key, en in TEXT["en"].items():
        assert fields(TEXT["ar"][key]) == fields(en), key


def test_fallbacks():
    assert tr("xx", "month") == "Month"
    assert tr("en", "no-such-key") == "no-such-key"
