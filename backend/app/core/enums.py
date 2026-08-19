from enum import StrEnum


class EnvironmentLevel(StrEnum):
    DEVELOPMENT = "DEVELOPMENT"
    TEST = "TEST"
    PRODUCTION = "PRODUCTION"


class OperationAction(StrEnum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    DEPLOY = "deploy"
    STATUS = "status"
    INSPECT = "inspect"
    DISCOVER_TOPOLOGY = "discover_topology"
    STATUS_ALL = "status_all"
    STATUS_SERVICE = "status_service"
    STATUS_SERVICE_HOSTS = "status_service_hosts"
    INSPECT_PROCESSES = "inspect_processes"


class OperationScope(StrEnum):
    ALL = "all"
    SERVICE = "service"
    SERVICE_HOSTS = "service_hosts"
    HOST = "host"
    HOSTS = "hosts"


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIALLY_SUCCEEDED = "PARTIALLY_SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class TargetStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"
    CANCELLED = "CANCELLED"


class PartialFailurePolicy(StrEnum):
    NONE = "NONE"
    BEST_EFFORT = "BEST_EFFORT"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    TASK_CREATED = "TASK_CREATED"


class IntegrationConfigStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    READY = "READY"
    DISABLED = "DISABLED"
