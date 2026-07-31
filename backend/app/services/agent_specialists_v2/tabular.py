from __future__ import annotations

from app.schemas.agent_specialist_results import (
    ObjectiveSpecialistInputV1,
    StructuredFactSetV1,
    specialist_payload_sha256,
)
from app.schemas.authorized_query_plan import StructuredQueryArtifactV1
from app.schemas.retrieval_v2 import EvidenceBundleV2
from app.services.agent_specialists_v2.base import (
    SpecialistExecutionContextV2,
    SpecialistHandlerResultV2,
)


class TabularSpecialistV2:
    capability_id = "platform.tabular.analyse"
    input_schema_version = "objective-specialist-input.v1"
    output_schema_version = "structured-fact-set.v1"
    allowed_ports = frozenset(
        {"artifact_reader", "authorized_query_gateway", "clock", "metrics"}
    )

    def execute(
        self,
        command: ObjectiveSpecialistInputV1,
        context: SpecialistExecutionContextV2,
    ) -> SpecialistHandlerResultV2:
        if command.capability_id != self.capability_id:
            raise ValueError("tabular_specialist_capability_mismatch")
        query_artifacts: list[StructuredQueryArtifactV1] = []
        evidence_bundles: list[EvidenceBundleV2] = []
        for artifact_ref in command.input_artifact_refs:
            artifact = context.artifact_reader(artifact_ref)
            if isinstance(artifact, StructuredQueryArtifactV1):
                query_artifacts.append(artifact)
            elif isinstance(artifact, EvidenceBundleV2):
                evidence_bundles.append(artifact)
            else:
                raise TypeError("tabular_specialist_input_artifact_invalid")
        if len(query_artifacts) != 1 or len(evidence_bundles) > 1:
            raise ValueError("tabular_specialist_input_shape_invalid")
        query_artifact = query_artifacts[0]
        result = query_artifact.result
        if (
            query_artifact.plan.scope_hash != command.scope_hash
            or result.scope_hash != command.scope_hash
        ):
            raise ValueError("tabular_specialist_scope_mismatch")
        if (
            query_artifact.plan.schema_hash != command.schema_hash
            or result.schema_hash != command.schema_hash
        ):
            raise ValueError("tabular_specialist_schema_mismatch")
        evidence_refs: tuple[str, ...] = (f"query-result:sha256:{result.result_hash}",)
        if evidence_bundles:
            bundle = evidence_bundles[0]
            if (
                bundle.objective_id != command.objective_id
                or bundle.scope_hash != command.scope_hash
            ):
                raise ValueError("tabular_specialist_evidence_mismatch")
            evidence_refs = (
                *evidence_refs,
                *(item.evidence_id for item in bundle.nodes),
            )
        values: dict[str, object] = {
            "version": "structured-fact-set.v1",
            "objective_id": command.objective_id,
            "records": tuple(item.model_dump(mode="python") for item in result.records),
            "groups": tuple(item.model_dump(mode="python") for item in result.groups),
            "aggregates": tuple(
                item.model_dump(mode="python") for item in result.aggregates
            ),
            "relation_paths": tuple(
                item.model_dump(mode="python") for item in result.relation_paths
            ),
            "source_versions": tuple(
                item.model_dump(mode="python") for item in result.source_versions
            ),
            "evidence_refs": evidence_refs,
            "scope_hash": result.scope_hash,
            "schema_hash": result.schema_hash,
            "complete": not result.truncated,
            "truncated": result.truncated,
        }
        values["content_hash"] = specialist_payload_sha256(values)
        facts = StructuredFactSetV1.model_validate(values)
        metrics = {
            "records": len(facts.records),
            "aggregates": len(facts.aggregates),
            "provider_calls": 0,
        }
        for key, value in metrics.items():
            context.metrics(key, value)
        return SpecialistHandlerResultV2(
            payload=facts,
            safe_summary="结构化事实已生成",
            metrics=metrics,
        )


__all__ = ["TabularSpecialistV2"]
