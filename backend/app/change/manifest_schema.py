"""Deliberately bounded apps/v1 Deployment schema, validated without cluster access.

Unsupported Kubernetes fields fail closed; expanding this subset is operator code review.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.change.models import SHA256_IMAGE


class Object(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Metadata(Object):
    name: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9.-]{0,252}$")
    namespace: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    labels: dict[str, str] = Field(default_factory=dict)


class Port(Object):
    containerPort: int = Field(ge=1, le=65535)
    name: str | None = None
    protocol: Literal["TCP", "UDP", "SCTP"] = "TCP"


class HTTPGet(Object):
    path: str
    port: int = Field(ge=1, le=65535)
    scheme: Literal["HTTP", "HTTPS"] = "HTTP"


class Probe(Object):
    httpGet: HTTPGet
    initialDelaySeconds: int = Field(default=0, ge=0)
    periodSeconds: int = Field(default=10, ge=1)
    timeoutSeconds: int = Field(default=1, ge=1)
    failureThreshold: int = Field(default=3, ge=1)


class Resources(Object):
    requests: dict[str, str] = Field(default_factory=dict)
    limits: dict[str, str] = Field(default_factory=dict)


class Container(Object):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    image: str = Field(pattern=SHA256_IMAGE.pattern)
    imagePullPolicy: Literal["Always", "IfNotPresent", "Never"] = "IfNotPresent"
    ports: list[Port] = Field(default_factory=list)
    readinessProbe: Probe | None = None
    livenessProbe: Probe | None = None
    resources: Resources | None = None


class PodSpec(Object):
    containers: list[Container] = Field(min_length=1)
    restartPolicy: Literal["Always"] = "Always"
    terminationGracePeriodSeconds: int = Field(default=30, ge=0)


class Template(Object):
    metadata: Metadata
    spec: PodSpec


class Selector(Object):
    matchLabels: dict[str, str] = Field(min_length=1)


class DeploymentSpec(Object):
    replicas: int = Field(default=1, ge=0)
    selector: Selector
    template: Template

    @model_validator(mode="after")
    def matches(self) -> "DeploymentSpec":
        if any(
            self.template.metadata.labels.get(k) != v for k, v in self.selector.matchLabels.items()
        ):
            raise ValueError("Selector must match pod template labels")
        names = [item.name for item in self.template.spec.containers]
        if len(set(names)) != len(names):
            raise ValueError("Container names must be unique")
        return self


class Deployment(Object):
    apiVersion: Literal["apps/v1"]
    kind: Literal["Deployment"]
    metadata: Metadata
    spec: DeploymentSpec

    @model_validator(mode="after")
    def named(self) -> "Deployment":
        if not self.metadata.name:
            raise ValueError("Deployment name is required")
        return self
