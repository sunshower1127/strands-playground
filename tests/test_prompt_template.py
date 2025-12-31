"""PromptTemplate 테스트"""

import pytest
from src.rag.prompt_template import (
    PromptTemplate,
    SimplePromptTemplate,
    StrictPromptTemplate,
)


# 테스트용 컨텍스트 fixture
@pytest.fixture
def sample_context() -> str:
    """ContextBuilder 출력 형식의 샘플 컨텍스트"""
    return """[1] (휴가정책.md, p.2)
연차 휴가는 입사 1년차 15일, 2년차부터 16일이 부여됩니다.

[2] (복지제도.md, p.5)
경조사 휴가는 결혼 5일, 출산 10일이 제공됩니다."""


@pytest.fixture
def sample_question() -> str:
    return "연차 휴가는 며칠인가요?"


class TestSimplePromptTemplate:
    """SimplePromptTemplate 테스트 - 베이스라인"""

    def test_returns_tuple(self, sample_context, sample_question):
        template = SimplePromptTemplate()

        result = template.render(sample_context, sample_question)

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_system_prompt_contains_instruction(self, sample_context, sample_question):
        template = SimplePromptTemplate()

        system, _ = template.render(sample_context, sample_question)

        assert "Answer" in system
        assert "documents" in system

    def test_system_prompt_contains_language(self, sample_context, sample_question):
        template = SimplePromptTemplate()

        system, _ = template.render(sample_context, sample_question, "Korean")

        assert "Korean" in system

    def test_user_prompt_contains_context(self, sample_context, sample_question):
        template = SimplePromptTemplate()

        _, user = template.render(sample_context, sample_question)

        assert "휴가정책.md" in user
        assert "연차 휴가" in user

    def test_user_prompt_contains_question(self, sample_context, sample_question):
        template = SimplePromptTemplate()

        _, user = template.render(sample_context, sample_question)

        assert sample_question in user

    def test_different_response_language(self, sample_context, sample_question):
        template = SimplePromptTemplate()

        system, _ = template.render(sample_context, sample_question, "English")

        assert "English" in system
        assert "Korean" not in system

    def test_implements_protocol(self):
        template = SimplePromptTemplate()
        assert isinstance(template, PromptTemplate)


class TestStrictPromptTemplate:
    """StrictPromptTemplate 테스트 - 할루시네이션 방지"""

    def test_returns_tuple(self, sample_context, sample_question):
        template = StrictPromptTemplate()

        result = template.render(sample_context, sample_question)

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_system_prompt_is_english(self, sample_context, sample_question):
        template = StrictPromptTemplate()

        system, _ = template.render(sample_context, sample_question)

        # 영어 키워드 확인
        assert "document-based" in system
        assert "ONLY" in system
        assert "NEVER" in system

    def test_system_prompt_prohibits_prior_knowledge(
        self, sample_context, sample_question
    ):
        template = StrictPromptTemplate()

        system, _ = template.render(sample_context, sample_question)

        assert "prior knowledge" in system
        assert "Prohibited" in system

    def test_system_prompt_requires_citations(self, sample_context, sample_question):
        template = StrictPromptTemplate()

        system, _ = template.render(sample_context, sample_question)

        assert "cite" in system.lower()
        assert "[1]" in system or "document numbers" in system

    def test_system_prompt_contains_language(self, sample_context, sample_question):
        template = StrictPromptTemplate()

        system, _ = template.render(sample_context, sample_question, "Korean")

        assert "Korean" in system
        assert "MUST respond" in system

    def test_user_prompt_is_korean(self, sample_context, sample_question):
        template = StrictPromptTemplate()

        _, user = template.render(sample_context, sample_question)

        # 한국어 키워드 확인
        assert "참고 문서" in user
        assert "질문" in user
        assert "출처" in user

    def test_user_prompt_contains_context(self, sample_context, sample_question):
        template = StrictPromptTemplate()

        _, user = template.render(sample_context, sample_question)

        assert "휴가정책.md" in user
        assert "[1]" in user

    def test_user_prompt_contains_question(self, sample_context, sample_question):
        template = StrictPromptTemplate()

        _, user = template.render(sample_context, sample_question)

        assert sample_question in user

    def test_user_prompt_reinforces_citation(self, sample_context, sample_question):
        """User prompt에서도 출처 명시 요청"""
        template = StrictPromptTemplate()

        _, user = template.render(sample_context, sample_question)

        assert "출처" in user

    def test_different_response_language(self, sample_context, sample_question):
        template = StrictPromptTemplate()

        system, _ = template.render(sample_context, sample_question, "English")

        assert "English" in system
        assert "Korean" not in system

    def test_implements_protocol(self):
        template = StrictPromptTemplate()
        assert isinstance(template, PromptTemplate)


class TestLanguageControl:
    """응답 언어 제어 테스트"""

    @pytest.mark.parametrize(
        "language",
        ["Korean", "English", "Japanese", "Chinese", "Spanish"],
    )
    def test_simple_template_supports_languages(
        self, sample_context, sample_question, language
    ):
        template = SimplePromptTemplate()

        system, _ = template.render(sample_context, sample_question, language)

        assert language in system

    @pytest.mark.parametrize(
        "language",
        ["Korean", "English", "Japanese", "Chinese", "Spanish"],
    )
    def test_strict_template_supports_languages(
        self, sample_context, sample_question, language
    ):
        template = StrictPromptTemplate()

        system, _ = template.render(sample_context, sample_question, language)

        assert language in system

    def test_default_language_is_korean(self, sample_context, sample_question):
        """기본 언어는 Korean"""
        simple = SimplePromptTemplate()
        strict = StrictPromptTemplate()

        simple_system, _ = simple.render(sample_context, sample_question)
        strict_system, _ = strict.render(sample_context, sample_question)

        assert "Korean" in simple_system
        assert "Korean" in strict_system


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_context(self, sample_question):
        template = StrictPromptTemplate()

        system, user = template.render("", sample_question)

        assert system  # system은 항상 존재
        assert sample_question in user

    def test_empty_question(self, sample_context):
        template = StrictPromptTemplate()

        system, user = template.render(sample_context, "")

        assert system
        assert sample_context in user

    def test_multiline_question(self, sample_context):
        template = StrictPromptTemplate()
        question = "연차 휴가는 며칠인가요?\n그리고 경조사 휴가는요?"

        _, user = template.render(sample_context, question)

        assert question in user

    def test_special_characters_in_context(self, sample_question):
        template = StrictPromptTemplate()
        context = "특수문자: []{}<>()\"'`~!@#$%^&*"

        _, user = template.render(context, sample_question)

        assert "특수문자" in user

    def test_very_long_context(self, sample_question):
        template = StrictPromptTemplate()
        context = "긴 문서 내용. " * 1000

        _, user = template.render(context, sample_question)

        assert len(user) > 5000

    def test_unicode_in_language(self, sample_context, sample_question):
        template = StrictPromptTemplate()

        # 한국어로 언어 지정해도 동작
        system, _ = template.render(sample_context, sample_question, "한국어")

        assert "한국어" in system


class TestPromptComparison:
    """템플릿 비교 테스트"""

    def test_strict_has_more_instructions(self, sample_context, sample_question):
        """StrictPromptTemplate이 더 많은 지시 포함"""
        simple = SimplePromptTemplate()
        strict = StrictPromptTemplate()

        simple_system, _ = simple.render(sample_context, sample_question)
        strict_system, _ = strict.render(sample_context, sample_question)

        assert len(strict_system) > len(simple_system)

    def test_strict_has_hallucination_prevention(self, sample_context, sample_question):
        """StrictPromptTemplate만 할루시네이션 방지 지시 포함"""
        simple = SimplePromptTemplate()
        strict = StrictPromptTemplate()

        simple_system, _ = simple.render(sample_context, sample_question)
        strict_system, _ = strict.render(sample_context, sample_question)

        assert "NEVER" not in simple_system
        assert "NEVER" in strict_system
        assert "prior knowledge" not in simple_system
        assert "prior knowledge" in strict_system

    def test_both_templates_return_strings(self, sample_context, sample_question):
        """모든 템플릿이 문자열 반환"""
        templates = [SimplePromptTemplate(), StrictPromptTemplate()]

        for template in templates:
            system, user = template.render(sample_context, sample_question)
            assert isinstance(system, str)
            assert isinstance(user, str)
