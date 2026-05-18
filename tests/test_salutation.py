"""Tests for the gender-aware salutation helper."""

from therapist_finder.utils.gender import guess_gender
from therapist_finder.utils.salutation import make_salutation


class TestGuessGender:
    """Tests for the gender_guesser wrapper."""

    def test_female_german_first_name(self):
        assert guess_gender("Katrin") == "female"
        assert guess_gender("Heike") == "female"
        assert guess_gender("Lena") == "female"

    def test_male_german_first_name(self):
        assert guess_gender("Andreas") == "male"
        assert guess_gender("Thomas") == "male"

    def test_case_insensitive(self):
        assert guess_gender("katrin") == "female"
        assert guess_gender("ANDREAS") == "male"

    def test_unknown_or_androgynous(self):
        assert guess_gender("Xyzqwerty") == "unknown"

    def test_empty_string(self):
        assert guess_gender("") == "unknown"


class TestMakeSalutation:
    """Tests for make_salutation."""

    def test_female_first_name(self):
        # Common German female first name → "Frau" greeting even without
        # an explicit "Frau" token in the name.
        assert make_salutation("Katrin Nicolaus") == "Sehr geehrte Frau Nicolaus"

    def test_male_first_name(self):
        assert make_salutation("Andreas Müller") == "Sehr geehrter Herr Müller"

    def test_explicit_frau_marker_wins(self):
        # Explicit marker overrides gender guess.
        assert (
            make_salutation("Dr. Frau Mustermann") == "Sehr geehrte Frau Dr. Mustermann"
        )

    def test_explicit_herr_marker_wins(self):
        assert (
            make_salutation("Dr. Herr Mustermann")
            == "Sehr geehrter Herr Dr. Mustermann"
        )

    def test_title_preserved(self):
        assert make_salutation("Dr. Andreas Müller") == "Sehr geehrter Herr Dr. Müller"

    def test_dipl_psych_title_preserved(self):
        assert (
            make_salutation("Dipl.-Psych. Heike Schmidt")
            == "Sehr geehrte Frau Dipl.-Psych. Schmidt"
        )

    def test_unknown_name_neutral_greeting(self):
        # Name the dataset doesn't know → neutral "Guten Tag" greeting,
        # never "Sehr geehrte Frau"/"Sehr geehrter Herr".
        result = make_salutation("Xyzqwerty Lastname")
        assert result == "Guten Tag Lastname"

    def test_empty_name(self):
        assert make_salutation("") == "Sehr geehrte Damen und Herren"

    def test_initial_first_name_falls_back_to_neutral(self):
        # "H. Paschotta" — initial isn't usable for gender guessing.
        result = make_salutation("H. Paschotta")
        assert result == "Guten Tag Paschotta"
