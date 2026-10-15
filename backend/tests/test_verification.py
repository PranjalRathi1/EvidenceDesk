from app.verification import normalize_whitespace, quote_exists_in_text, verify_claim

SOURCE = "Four conditions must all hold simultaneously for a deadlock to occur:\nmutual exclusion, hold-and-wait, no preemption, and circular wait."


def test_exact_quote_match():
    assert quote_exists_in_text("mutual exclusion, hold-and-wait", SOURCE)


def test_whitespace_normalized_match():
    messy_quote = "mutual   exclusion,\nhold-and-wait"
    assert quote_exists_in_text(messy_quote, SOURCE)


def test_case_insensitive_match():
    assert quote_exists_in_text("MUTUAL EXCLUSION", SOURCE)


def test_fabricated_quote_is_rejected():
    assert not quote_exists_in_text("mutual exclusion is optional in modern kernels", SOURCE)


def test_empty_quote_is_rejected():
    assert not quote_exists_in_text("", SOURCE)
    assert not quote_exists_in_text("   ", SOURCE)


def test_missing_quote_entirely_unrelated_text():
    assert not quote_exists_in_text("mitochondria produce ATP", SOURCE)


def test_normalize_whitespace_collapses_runs():
    assert normalize_whitespace("a   b\n\nc\t d") == "a b c d"


def test_verify_claim_fails_layer1_without_calling_judge(monkeypatch):
    called = {"n": 0}

    def fake_judge(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("semantic judge should not be called when the quote itself is fabricated")

    monkeypatch.setattr("app.verification.semantic_support_check", fake_judge)
    verdict = verify_claim("deadlocks require four conditions", "completely made up text", SOURCE)
    assert verdict.status == "not_found"
    assert verdict.method == "exact_quote_failed"
    assert called["n"] == 0


def test_verify_claim_calls_judge_when_quote_exists(monkeypatch):
    from app.verification import SupportVerdict

    monkeypatch.setattr(
        "app.verification.semantic_support_check",
        lambda claim, evidence: SupportVerdict(status="supported", explanation="matches", method="llm_judge"),
    )
    verdict = verify_claim("there are four deadlock conditions", "mutual exclusion, hold-and-wait", SOURCE)
    assert verdict.status == "supported"
    assert verdict.method == "llm_judge"


def test_semantic_check_fails_safe_on_judge_error(monkeypatch):
    from app import llm_client
    from app.verification import semantic_support_check

    def broken_chat(*args, **kwargs):
        raise llm_client.LLMError("ollama unreachable")

    monkeypatch.setattr(llm_client.provider, "chat", broken_chat)
    verdict = semantic_support_check("claim", "evidence")
    assert verdict.status == "not_found"
    assert verdict.method == "judge_unavailable"


def test_semantic_check_fails_safe_on_malformed_judge_json(monkeypatch):
    from app import llm_client
    from app.verification import semantic_support_check

    monkeypatch.setattr(llm_client.provider, "chat", lambda *a, **k: "not valid json")
    verdict = semantic_support_check("claim", "evidence")
    assert verdict.status == "not_found"
    assert verdict.method == "judge_unavailable"


def test_semantic_check_fails_safe_on_invalid_status_value(monkeypatch):
    from app import llm_client
    from app.verification import semantic_support_check

    monkeypatch.setattr(llm_client.provider, "chat", lambda *a, **k: '{"status": "definitely_true", "explanation": "x"}')
    verdict = semantic_support_check("claim", "evidence")
    assert verdict.status == "not_found"
    assert verdict.method == "judge_unavailable"
