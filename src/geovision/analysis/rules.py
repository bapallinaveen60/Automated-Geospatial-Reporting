"""Config-driven exceedance rules evaluated against the flattened metrics payload."""

import operator
from collections.abc import Callable, Iterable, Mapping
from typing import Literal

from pydantic import BaseModel

from geovision.contracts.metrics import ExceedanceFlag, Severity

Op = Literal["<", "<=", ">", ">=", "==", "!="]

_OPS: dict[str, Callable[[float, float], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


class Rule(BaseModel):
    id: str
    metric: str
    op: Op
    threshold: float
    severity: Severity
    # Python format string; available fields: {value}, {threshold}, plus any extra context.
    message: str
    regulation: str | None = None
    # A missing metric usually means "nothing found" (e.g. no protected area in range).
    when_missing: Literal["skip", "info"] = "skip"


class _SafeDict(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def evaluate(
    rules: Iterable[Rule],
    metrics: Mapping[str, float | None],
    context: Mapping[str, object] | None = None,
) -> list[ExceedanceFlag]:
    flags: list[ExceedanceFlag] = []
    for rule in rules:
        value = metrics.get(rule.metric)
        if value is None:
            if rule.when_missing == "info":
                flags.append(
                    ExceedanceFlag(
                        rule_id=rule.id,
                        severity="info",
                        message=f"Data unavailable for '{rule.metric}'; manual check required.",
                        metric=rule.metric,
                        value=None,
                        threshold=rule.threshold,
                        regulation=rule.regulation,
                    )
                )
            continue
        if _OPS[rule.op](value, rule.threshold):
            fields = _SafeDict(context or {})
            fields.update(value=value, threshold=rule.threshold)
            flags.append(
                ExceedanceFlag(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=rule.message.format_map(fields),
                    metric=rule.metric,
                    value=value,
                    threshold=rule.threshold,
                    regulation=rule.regulation,
                )
            )
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(flags, key=lambda f: order[f.severity])
