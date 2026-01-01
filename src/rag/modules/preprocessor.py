"""쿼리 전처리기 (Preprocessor)

사용자 질문을 검색에 최적화된 형태로 변환합니다.

결론:
- BM25: Nori가 조사/어미 자동 처리
- 벡터 검색: 임베딩 모델이 문맥 이해, 전처리 효과 미미
- 권장: NoopPreprocessor로 시작, 검색 품질 문제 발생 시 추가
"""

import re
import unicodedata
from typing import Protocol, runtime_checkable


@runtime_checkable
class Preprocessor(Protocol):
    """쿼리 전처리기 프로토콜"""

    def process(self, query: str) -> str:
        """쿼리를 전처리하여 반환"""
        ...


class NoopPreprocessor:
    """아무것도 안 함 (권장)

    Nori + 임베딩 모델이 충분히 처리하므로 전처리 불필요.
    """

    def process(self, query: str) -> str:
        return query


class MinimalPreprocessor:
    """최소 정규화만 (선택적)

    유니코드 정규화(NFKC)만 수행.
    한글 자모 정규화에 유용할 수 있음.
    """

    def process(self, query: str) -> str:
        if not query:
            return query
        return unicodedata.normalize("NFKC", query).strip()


class KoreanPreprocessor:
    """기존 프로젝트의 한국어 전처리 로직

    비교 테스트용으로 구현. Nori가 처리하지 못하는 영역 담당:
    - 유니코드 정규화 (NFKC)
    - 양끝 문장부호/공백 정리
    - 문장 종결어미 제거 (알려줘, 해주세요 등)
    - 숫자 단위 정규화 (2024년 → 2024)

    Note: 기본 조사(이/가/을/를)는 Nori POS 필터가 처리하므로 제외
    """

    # 양끝 문장부호 패턴
    _punct_pattern = re.compile(
        r"^[\s\"\"\"\'\'\'()\[\]{},.\-?!:;~·…<>「」『』]+|[\s\"\"\"\'\'\'()\[\]{},.\-?!:;~·…<>「」『』]+$"
    )

    # 문장 종결어미 패턴 (Nori가 처리하지 못하는 복합 어미)
    # "알려줘", "찾아줘" 등 "아/어줘" 패턴 포함
    _ending_pattern = re.compile(
        r"(?:"
        r"(?:알려|보여|찾아|설명해|검색해|가르쳐|말해|정리해|요약해|조회해|제출해|추천해|비교해|분석해)줘(?:요)?"
        r"|해\s?주세요|해주세요|주세요"
        r"|해줘|해라|해$"
        r"|인가요\??|인가\??|이야\??|야\??"
        r")$"
    )

    # 숫자 단위 패턴 (년도)
    _year_pattern = re.compile(r"(\d{2,4})\s*년\b")

    def process(self, query: str) -> str:
        if not query:
            return query

        # 1) 유니코드 정규화 + 양끝 문장부호/공백 정리
        s = unicodedata.normalize("NFKC", query).strip()
        s = self._punct_pattern.sub("", s)

        # 2) 문장 종결어미 제거 (반복 제거로 중첩된 어미 처리)
        for _ in range(2):
            ns = self._ending_pattern.sub("", s).strip()
            if ns == s:
                break
            s = ns

        # 3) 숫자 단위 정규화 (검색 최적화)
        s = self._year_pattern.sub(r"\1", s)

        return s
