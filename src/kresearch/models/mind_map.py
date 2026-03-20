"""Mind map — the agent's persistent epistemic state."""

from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


class Source(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""


class Contradiction(BaseModel):
    topic: str
    claim_a: str
    claim_b: str
    source_a: Source
    source_b: Source


class MindMapNode(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    topic: str
    content: str = ""
    sources: list[Source] = Field(default_factory=list)
    confidence: float = 0.0
    children: list[MindMapNode] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)


class MindMap(BaseModel):
    root: MindMapNode
    query: str

    @classmethod
    def create(cls, query: str) -> MindMap:
        return cls(root=MindMapNode(topic=query), query=query)

    def find_or_create_node(self, topic: str) -> MindMapNode:
        found = self._find_node(self.root, topic)
        if found:
            return found
        node = MindMapNode(topic=topic)
        self.root.children.append(node)
        return node

    def _find_node(self, node: MindMapNode, topic: str) -> MindMapNode | None:
        if node.topic.lower() == topic.lower():
            return node
        for child in node.children:
            found = self._find_node(child, topic)
            if found:
                return found
        return None

    def add_finding(self, topic: str, content: str, sources: list[Source],
                    confidence: float) -> MindMapNode:
        node = self.find_or_create_node(topic)
        node.content = f"{node.content}\n\n{content}".strip()
        node.sources.extend(sources)
        node.confidence = max(node.confidence, confidence)
        return node

    def log_contradiction(self, topic: str, claim_a: str, claim_b: str,
                          source_a: Source, source_b: Source) -> None:
        node = self.find_or_create_node(topic)
        node.contradictions.append(Contradiction(
            topic=topic, claim_a=claim_a, claim_b=claim_b,
            source_a=source_a, source_b=source_b,
        ))

    def get_summary(self) -> str:
        lines: list[str] = []
        self._walk(self.root, lines, 0)
        return "\n".join(lines)

    def _walk(self, node: MindMapNode, lines: list[str], depth: int) -> None:
        pre = "  " * depth
        conf = f"{node.confidence:.0%}" if node.confidence else "none"
        lines.append(f"{pre}- {node.topic}  ({len(node.sources)} sources, confidence: {conf})")
        for c in node.contradictions:
            lines.append(f"{pre}  ⚠ Contradiction: {c.claim_a} vs {c.claim_b}")
        for child in node.children:
            self._walk(child, lines, depth + 1)

    def get_gaps(self) -> list[str]:
        return [n.topic for n in self._all_nodes() if n.confidence < 0.3 and n.topic != self.query]

    def get_contradictions(self) -> list[Contradiction]:
        result: list[Contradiction] = []
        for n in self._all_nodes():
            result.extend(n.contradictions)
        return result

    def source_count(self) -> int:
        return sum(len(n.sources) for n in self._all_nodes())

    def _all_nodes(self) -> list[MindMapNode]:
        nodes: list[MindMapNode] = []
        stack = [self.root]
        while stack:
            n = stack.pop()
            nodes.append(n)
            stack.extend(n.children)
        return nodes

    def to_structured_data(self) -> dict:
        return self.model_dump()

    def to_markdown(self) -> str:
        return self.get_summary()
