"""컨텍스트 빌더 (ContextBuilder)

검색 결과 → LLM에 주입할 컨텍스트 문자열 생성.

권장 사용:
    RankedContextBuilder(reorder=True)  # Lost in the Middle 문제 완화

참고:
    - Lost in the Middle (Stanford): LLM은 컨텍스트 처음과 끝은 잘 활용하지만 중간은 무시
    - 권장 k: 5-7개 (10개 이상시 성능 저하)
    - 컨텍스트 총량: 윈도우의 30-40% 이하 권장
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ContextBuilder(Protocol):
    """컨텍스트 빌더 프로토콜"""

    def build(self, results: list[dict]) -> str:
        """검색 결과를 컨텍스트 문자열로 변환

        Args:
            results: OpenSearch 검색 결과 리스트 [{"_score": float, "_source": {...}}, ...]

        Returns:
            LLM에 주입할 컨텍스트 문자열
        """
        ...


class SimpleContextBuilder:
    """단순 연결 (베이스라인)

    검색 결과를 번호를 붙여 단순 연결합니다.
    비교 기준용.

    출력 예시:
        [1]
        연차 휴가는 입사 1년차 15일...

        [2]
        경조사 휴가는 결혼 5일...
    """

    def __init__(self, text_field: str = "text"):
        """
        Args:
            text_field: 텍스트를 가져올 필드명 (text, chunk_text, content 등)
        """
        self.text_field = text_field

    def build(self, results: list[dict]) -> str:
        if not results:
            return ""

        parts = []
        for i, doc in enumerate(results, 1):
            source = doc.get("_source", {})
            text = source.get(self.text_field, "")
            if not text:
                # fallback 시도
                text = source.get("content", "") or source.get("text", "")
            parts.append(f"[{i}]\n{text}")

        return "\n\n".join(parts)


class RankedContextBuilder:
    """메타데이터 + LongContextReorder 적용 (권장)

    특징:
    1. 파일명, 페이지 번호 등 메타데이터 포함
    2. LongContextReorder: 관련도 높은 문서를 처음과 끝에 배치
       (U-shaped attention 패턴 활용)
    3. 선택적 점수 표시 (디버깅용)

    출력 예시:
        [1] (휴가정책.md, p.2)
        연차 휴가는 입사 1년차 15일...

        [2] (복지제도.md, p.5)
        경조사 휴가는 결혼 5일...

    디버그 모드:
        [1] (휴가정책.md, p.2) [score: 0.85]
        ...
    """

    def __init__(
        self,
        reorder: bool = True,
        include_score: bool = False,
        text_field: str = "text",
    ):
        """
        Args:
            reorder: LongContextReorder 적용 여부
            include_score: 점수 표시 여부 (디버깅용)
            text_field: 텍스트를 가져올 필드명
        """
        self.reorder = reorder
        self.include_score = include_score
        self.text_field = text_field

    def _reorder_for_attention(self, results: list[dict]) -> list[dict]:
        """U-shaped attention 패턴 활용

        관련도 높은 문서(짝수 인덱스): 중앙에서 시작하여 양쪽으로 배치
        관련도 낮은 문서(홀수 인덱스): 끝에 추가

        입력: [1, 2, 3, 4, 5] (1이 가장 관련도 높음)
        출력: [3, 1, 5, 2, 4] (1, 5가 시작/끝 근처)

        이렇게 하면 LLM이 가장 잘 활용하는 처음과 끝에
        관련도 높은 문서가 배치됩니다.
        """
        if not self.reorder or len(results) <= 2:
            return results

        reordered = []
        for i, doc in enumerate(results):
            if i % 2 == 0:
                # 짝수 인덱스: 중앙에 삽입
                reordered.insert(len(reordered) // 2, doc)
            else:
                # 홀수 인덱스: 끝에 추가
                reordered.append(doc)

        return reordered

    def build(self, results: list[dict]) -> str:
        if not results:
            return ""

        reordered = self._reorder_for_attention(results)

        parts = []
        for i, doc in enumerate(reordered, 1):
            source = doc.get("_source", {})

            # 텍스트 추출
            text = source.get(self.text_field, "")
            if not text:
                text = source.get("content", "") or source.get("text", "")

            # 메타데이터 추출
            filename = source.get("file_name", "") or source.get("original_filename", "")
            page = source.get("page_number", "")

            # 헤더 구성
            if filename and page:
                header = f"[{i}] ({filename}, p.{page})"
            elif filename:
                header = f"[{i}] ({filename})"
            else:
                header = f"[{i}]"

            # 점수 추가 (디버깅용)
            if self.include_score and "_score" in doc:
                header += f" [score: {doc['_score']:.3f}]"

            parts.append(f"{header}\n{text}")

        return "\n\n".join(parts)


# 편의 alias
DebugContextBuilder = lambda: RankedContextBuilder(include_score=True)
