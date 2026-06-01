"""
Graph Memory - 知识图谱记忆系统

基于图结构存储和检索知识，支持：
- 实体节点和关系边
- 语义搜索
- 路径查询
- 知识推理
"""

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class EntityType(Enum):
    """实体类型"""

    CONCEPT = "concept"
    OBJECT = "object"
    EVENT = "event"
    AGENT = "agent"
    KNOWLEDGE = "knowledge"


class RelationType(Enum):
    """关系类型"""

    IS_A = "is_a"
    PART_OF = "part_of"
    HAS_PROPERTY = "has_property"
    CAUSED_BY = "caused_by"
    LEADS_TO = "leads_to"
    RELATED_TO = "related_to"
    DEPENDS_ON = "depends_on"
    KNOWS = "knows"
    CAN_DO = "can_do"


@dataclass
class Entity:
    """知识图谱实体"""

    id: str
    name: str
    entity_type: EntityType
    properties: Dict[str, Any] = field(default_factory=dict)
    embeddings: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_property(self, key: str, value: Any):
        self.properties[key] = value
        self.updated_at = datetime.now()

    def get_property(self, key: str, default: Any = None) -> Any:
        return self.properties.get(key, default)


@dataclass
class Relation:
    """知识图谱关系"""

    id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def update_weight(self, delta: float):
        self.weight = max(0.0, min(1.0, self.weight + delta))


@dataclass
class GraphQuery:
    """图查询结果"""

    entities: List[Entity]
    relations: List[Relation]
    path: Optional[List[str]] = None
    score: float = 0.0


class GraphMemory:
    """
    知识图谱记忆系统

    实现三层记忆架构中的 Semantic Memory 层，
    提供基于图结构的专业知识存储和检索。
    """

    def __init__(self, max_entities: int = 10000, max_relations: int = 50000):
        self.max_entities = max_entities
        self.max_relations = max_relations

        self._entities: Dict[str, Entity] = {}
        self._relations: Dict[str, Relation] = {}

        self._entity_index: Dict[str, Set[str]] = {}
        self._type_index: Dict[EntityType, Set[str]] = {}

        self._outgoing_edges: Dict[str, Set[str]] = {}
        self._incoming_edges: Dict[str, Set[str]] = {}

    def add_entity(
        self,
        name: str,
        entity_type: EntityType,
        properties: Optional[Dict[str, Any]] = None,
        entity_id: Optional[str] = None,
    ) -> Entity:
        """添加实体"""
        if len(self._entities) >= self.max_entities:
            self._evict_oldest_entities(100)

        entity_id = entity_id or str(uuid.uuid4())[:8]

        entity = Entity(
            id=entity_id, name=name, entity_type=entity_type, properties=properties or {}
        )

        self._entities[entity_id] = entity

        self._entity_index.setdefault(name.lower(), set()).add(entity_id)
        self._type_index.setdefault(entity_type, set()).add(entity_id)

        self._outgoing_edges.setdefault(entity_id, set())
        self._incoming_edges.setdefault(entity_id, set())

        print(f"   📔 知识图谱添加实体: {name} ({entity_type.value})")
        return entity

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
        relation_id: Optional[str] = None,
    ) -> Optional[Relation]:
        """添加关系"""
        if source_id not in self._entities or target_id not in self._entities:
            print("   ⚠️ 关系添加失败: 实体不存在")
            return None

        if len(self._relations) >= self.max_relations:
            self._evict_oldest_relations(100)

        relation_id = relation_id or str(uuid.uuid4())[:8]

        relation = Relation(
            id=relation_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            weight=weight,
            properties=properties or {},
        )

        self._relations[relation_id] = relation

        self._outgoing_edges.setdefault(source_id, set()).add(relation_id)
        self._incoming_edges.setdefault(target_id, set()).add(relation_id)

        print(f"   🔗 知识图谱添加关系: {source_id} --[{relation_type.value}]--> {target_id}")
        return relation

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        return self._entities.get(entity_id)

    def find_entities(
        self, name: Optional[str] = None, entity_type: Optional[EntityType] = None
    ) -> List[Entity]:
        """查找实体"""
        results = set(self._entities.keys())

        if name:
            name_lower = name.lower()
            if name_lower in self._entity_index:
                results &= self._entity_index[name_lower]
            else:
                return []

        if entity_type and entity_type in self._type_index:
            results &= self._type_index[entity_type]

        return [self._entities[eid] for eid in results]

    def find_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        relation_type: Optional[RelationType] = None,
    ) -> List[Relation]:
        """查找关系"""
        results = set(self._relations.keys())

        if source_id:
            outgoing = self._outgoing_edges.get(source_id, set())
            results &= outgoing

        if target_id:
            incoming = self._incoming_edges.get(target_id, set())
            results &= incoming

        if relation_type:
            results = {
                rid for rid in results if self._relations[rid].relation_type == relation_type
            }

        return [self._relations[rid] for rid in results]

    def get_neighbors(
        self, entity_id: str, relation_type: Optional[RelationType] = None, direction: str = "out"
    ) -> List[Tuple[Entity, Relation]]:
        """获取邻居节点"""
        neighbors = []

        if direction in ("out", "both"):
            for relation_id in self._outgoing_edges.get(entity_id, set()):
                relation = self._relations[relation_id]
                if relation_type and relation.relation_type != relation_type:
                    continue
                target = self._entities.get(relation.target_id)
                if target:
                    neighbors.append((target, relation))

        if direction in ("in", "both"):
            for relation_id in self._incoming_edges.get(entity_id, set()):
                relation = self._relations[relation_id]
                if relation_type and relation.relation_type != relation_type:
                    continue
                source = self._entities.get(relation.source_id)
                if source:
                    neighbors.append((source, relation))

        return neighbors

    def find_path(self, source_id: str, target_id: str, max_depth: int = 5) -> Optional[List[str]]:
        """路径查找（BFS）"""
        if source_id not in self._entities or target_id not in self._entities:
            return None

        if source_id == target_id:
            return [source_id]

        visited = {source_id}
        queue = [(source_id, [source_id])]

        while queue:
            current, path = queue.pop(0)

            if len(path) > max_depth:
                continue

            for relation_id in self._outgoing_edges.get(current, set()):
                relation = self._relations[relation_id]
                neighbor = relation.target_id

                if neighbor == target_id:
                    return path + [neighbor]

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def find_paths(
        self, source_id: str, target_id: str, max_depth: int = 5, max_paths: int = 3
    ) -> List[List[str]]:
        """查找多条路径"""
        if source_id not in self._entities or target_id not in self._entities:
            return []

        all_paths = []

        def dfs(current: str, path: List[str], visited: Set[str]):
            if len(all_paths) >= max_paths:
                return

            if len(path) > max_depth:
                return

            if current == target_id:
                all_paths.append(path.copy())
                return

            for relation_id in self._outgoing_edges.get(current, set()):
                relation = self._relations[relation_id]
                neighbor = relation.target_id

                if neighbor not in visited:
                    visited.add(neighbor)
                    path.append(neighbor)
                    dfs(neighbor, path, visited)
                    path.pop()
                    visited.remove(neighbor)

        dfs(source_id, [source_id], {source_id})
        return all_paths

    def query(self, query_text: str, top_k: int = 5) -> List[Entity]:
        """语义查询（基于关键词匹配）"""
        query_lower = query_text.lower()
        query_terms = set(query_lower.split())

        scored_entities = []

        for entity in self._entities.values():
            score = 0.0

            name_terms = set(entity.name.lower().split())
            score += len(query_terms & name_terms) * 2.0

            for prop_value in entity.properties.values():
                if isinstance(prop_value, str):
                    prop_terms = set(prop_value.lower().split())
                    score += len(query_terms & prop_terms) * 0.5

            if entity.entity_type.value in query_lower:
                score += 1.0

            if score > 0:
                scored_entities.append((entity, score))

        scored_entities.sort(key=lambda x: x[1], reverse=True)
        return [entity for entity, score in scored_entities[:top_k]]

    def reason(self, entity_id: str, depth: int = 2) -> Dict[str, Any]:
        """知识推理"""
        entity = self._entities.get(entity_id)
        if not entity:
            return {}

        results = {
            "entity": entity,
            "direct_relations": [],
            "inferred_relations": [],
            "similar_entities": [],
            "paths_to_concepts": [],
        }

        for neighbor, relation in self.get_neighbors(entity_id):
            results["direct_relations"].append(
                {
                    "entity": neighbor.name,
                    "relation": relation.relation_type.value,
                    "weight": relation.weight,
                }
            )

        if depth > 1:
            for neighbor, relation in self.get_neighbors(entity_id):
                for second_neighbor, second_relation in self.get_neighbors(neighbor.id):
                    if second_neighbor.id != entity_id:
                        results["inferred_relations"].append(
                            {
                                "via": neighbor.name,
                                "to": second_neighbor.name,
                                "relation": second_relation.relation_type.value,
                            }
                        )

        if entity.entity_type == EntityType.CONCEPT:
            for neighbor, relation in self.get_neighbors(entity_id, RelationType.IS_A):
                if relation.source_id == entity_id:
                    results["paths_to_concepts"].append(neighbor.name)

        return results

    def update_embedding(self, entity_id: str, embeddings: List[float]):
        """更新实体嵌入向量"""
        entity = self._entities.get(entity_id)
        if entity:
            entity.embeddings = embeddings

    def find_similar(
        self, embeddings: List[float], top_k: int = 5, threshold: float = 0.7
    ) -> List[Tuple[Entity, float]]:
        """基于嵌入向量的相似度搜索"""
        scored_entities = []

        for entity in self._entities.values():
            if entity.embeddings:
                similarity = self._cosine_similarity(embeddings, entity.embeddings)
                if similarity >= threshold:
                    scored_entities.append((entity, similarity))

        scored_entities.sort(key=lambda x: x[1], reverse=True)
        return scored_entities[:top_k]

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _evict_oldest_entities(self, count: int):
        """驱逐最老的实体"""
        entities = sorted(self._entities.items(), key=lambda x: x[1].created_at)
        for entity_id, entity in entities[:count]:
            self._remove_entity(entity_id)

    def _evict_oldest_relations(self, count: int):
        """驱逐最老的关系"""
        relations = sorted(self._relations.items(), key=lambda x: x[1].created_at)
        for relation_id, relation in relations[:count]:
            self._remove_relation(relation_id)

    def _remove_entity(self, entity_id: str):
        """移除实体及其关联"""
        for relation_id in list(self._outgoing_edges.get(entity_id, set())):
            self._remove_relation(relation_id)
        for relation_id in list(self._incoming_edges.get(entity_id, set())):
            self._remove_relation(relation_id)

        if entity_id in self._entities:
            entity = self._entities[entity_id]
            name_key = entity.name.lower()
            if name_key in self._entity_index:
                self._entity_index[name_key].discard(entity_id)
            if entity.entity_type in self._type_index:
                self._type_index[entity.entity_type].discard(entity_id)

        self._entities.pop(entity_id, None)
        self._outgoing_edges.pop(entity_id, None)
        self._incoming_edges.pop(entity_id, None)

    def _remove_relation(self, relation_id: str):
        """移除关系"""
        relation = self._relations.get(relation_id)
        if relation:
            self._outgoing_edges.get(relation.source_id, set()).discard(relation_id)
            self._incoming_edges.get(relation.target_id, set()).discard(relation_id)
        self._relations.pop(relation_id, None)

    def merge_from(self, other: "GraphMemory"):
        """从另一个 GraphMemory 合并"""
        for entity_id, entity in other._entities.items():
            if entity_id not in self._entities:
                self.add_entity(
                    name=entity.name,
                    entity_type=entity.entity_type,
                    properties=entity.properties.copy(),
                    entity_id=entity_id,
                )

        for relation_id, relation in other._relations.items():
            if relation_id not in self._relations:
                self.add_relation(
                    source_id=relation.source_id,
                    target_id=relation.target_id,
                    relation_type=relation.relation_type,
                    weight=relation.weight,
                    properties=relation.properties.copy(),
                    relation_id=relation_id,
                )

    def export(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "entities": {
                eid: {"name": e.name, "type": e.entity_type.value, "properties": e.properties}
                for eid, e in self._entities.items()
            },
            "relations": [
                {
                    "source": r.source_id,
                    "target": r.target_id,
                    "type": r.relation_type.value,
                    "weight": r.weight,
                }
                for r in self._relations.values()
            ],
        }

    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "entity_count": len(self._entities),
            "relation_count": len(self._relations),
            "max_entities": self.max_entities,
            "max_relations": self.max_relations,
            "entity_types": {etype.value: len(eids) for etype, eids in self._type_index.items()},
        }
