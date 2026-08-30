from app.models import ChineseCharacter, SpeechReviewDecision
from app.schemas.learning import SpeechAttemptCreate
from app.services.character_speech import evaluate_character_speech, normalize_pinyin


def character(value: str, pinyin: str, accepted: list[str] | None = None) -> ChineseCharacter:
    return ChineseCharacter(
        character=value,
        pinyin=pinyin,
        accepted_readings=accepted or [],
    )


def test_pinyin_normalization_accepts_marks_numbers_case_and_u_variants() -> None:
    assert normalize_pinyin("DŌNG") == "dong1"
    assert normalize_pinyin("dong1") == "dong1"
    assert normalize_pinyin("nǚ") == "nv3"


def test_homophone_and_explicit_character_phrases_match() -> None:
    assert (
        evaluate_character_speech(character("东", "dōng"), "冬").decision
        == SpeechReviewDecision.MATCH
    )
    assert (
        evaluate_character_speech(character("东", "dōng"), "东方的东").decision
        == SpeechReviewDecision.MATCH
    )


def test_curated_polyphone_is_accepted_without_accepting_every_reading() -> None:
    assert (
        evaluate_character_speech(character("行", "xíng", ["hang2"]), "hang2").decision
        == SpeechReviewDecision.MATCH
    )
    assert (
        evaluate_character_speech(character("行", "xíng", ["hang2"]), "xing2").decision
        == SpeechReviewDecision.MATCH
    )
    assert (
        evaluate_character_speech(character("行", "xíng", ["hang2"]), "hang3").decision
        == SpeechReviewDecision.UNCERTAIN
    )


def test_tone_difference_is_uncertain_and_no_tone_is_partial() -> None:
    tone = evaluate_character_speech(character("东", "dōng"), "懂")
    assert tone.decision in {SpeechReviewDecision.UNCERTAIN, SpeechReviewDecision.NO_MATCH}
    assert tone.syllable_match is True
    assert tone.tone_match is False
    assert (
        evaluate_character_speech(character("东", "dōng"), "dong").decision
        == SpeechReviewDecision.PARTIAL_MATCH
    )


def test_silence_and_asr_noise_never_become_incorrect() -> None:
    assert (
        evaluate_character_speech(character("日", "rì"), None).decision
        == SpeechReviewDecision.NO_SPEECH
    )
    long_text = "我在东方的东边看到很多很多漂亮的东西"
    assert (
        evaluate_character_speech(character("东", "dōng"), long_text).decision
        == SpeechReviewDecision.UNCERTAIN
    )


def test_unknown_phrases_are_explicit_only() -> None:
    result = evaluate_character_speech(character("日", "rì"), "我不会读")
    assert result.decision == SpeechReviewDecision.NO_MATCH
    assert result.explicit_unknown is True


def test_speech_payload_rejects_raw_audio() -> None:
    payload = {
        "knowledge_point_id": "00000000-0000-0000-0000-000000000001",
        "attempt_index": 1,
        "provider": "browser_speech_recognition",
        "decision": "no_speech",
        "raw_audio": "base64-must-never-be-accepted",
    }
    try:
        SpeechAttemptCreate.model_validate(payload)
    except ValueError:
        return
    raise AssertionError("raw audio must not be accepted by the speech evidence schema")
