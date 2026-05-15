from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResultKind(str, Enum):
    SUCCESS = "success"
    PORT_IN_USE = "port_already_in_use"
    MAIN_CLASS_NOT_FOUND = "main_class_not_found"
    COMPILATION_ERROR = "compilation_error"
    MISSING_CONFIG = "missing_config"
    DEPENDENCY_ERROR = "dependency_error"
    JAVA_VERSION_MISMATCH = "java_version_mismatch"
    PROCESS_EXITED = "process_exited"
    TIMEOUT = "timeout"
    UNKNOWN_FAILURE = "unknown_failure"


@dataclass(frozen=True)
class Classification:
    kind: ResultKind
    message: str
    line: str | None = None


SUCCESS_PATTERNS = (
    "Started ",
    "Tomcat started on port",
    "Netty started on port",
    "Started Application in ",
)

FAILURE_PATTERNS: tuple[tuple[ResultKind, tuple[str, ...], str], ...] = (
    (
        ResultKind.PORT_IN_USE,
        (
            "Web server failed to start. Port",
            "Address already in use",
            "BindException",
            "port is already in use",
            "port already in use",
        ),
        "Port already in use",
    ),
    (
        ResultKind.MAIN_CLASS_NOT_FOUND,
        (
            "Unable to find a suitable main class",
            "please add a 'mainClass' property",
            "no main manifest attribute",
        ),
        "Main class not found for Spring Boot run",
    ),
    (
        ResultKind.COMPILATION_ERROR,
        (
            "COMPILATION ERROR",
            "Compilation failure",
            "Compilation failed",
            "Execution failed for task ':compile",
            "cannot find symbol",
            "package does not exist",
        ),
        "Compilation error",
    ),
    (
        ResultKind.MISSING_CONFIG,
        (
            "Could not resolve placeholder",
            "Failed to bind properties",
            "No qualifying bean of type",
            "UnsatisfiedDependencyException",
            "BeanCreationException",
            "PropertyReferenceException",
        ),
        "Missing or invalid application configuration",
    ),
    (
        ResultKind.DEPENDENCY_ERROR,
        (
            "Could not resolve dependencies",
            "Could not find artifact",
            "Could not transfer artifact",
            "Could not resolve all files",
            "Could not resolve all dependencies",
            "PKIX path building failed",
        ),
        "Dependency resolution error",
    ),
    (
        ResultKind.JAVA_VERSION_MISMATCH,
        (
            "UnsupportedClassVersionError",
            "has been compiled by a more recent version of the Java Runtime",
            "invalid source release",
            "invalid target release",
            "release version",
            "Unsupported class file major version",
        ),
        "Java version mismatch",
    ),
)


def classify_line(line: str) -> Classification | None:
    normalized = line.strip()
    if not normalized:
        return None

    for pattern in SUCCESS_PATTERNS:
        if pattern in normalized:
            return Classification(ResultKind.SUCCESS, "Application started successfully", normalized)

    for kind, patterns, message in FAILURE_PATTERNS:
        if _matches_failure(normalized, patterns):
            return Classification(kind, message, normalized)

    return None


def process_exit_classification(exit_code: int) -> Classification:
    return Classification(
        ResultKind.PROCESS_EXITED,
        f"Process exited before startup was detected with exit code {exit_code}",
    )


def timeout_classification(seconds: int) -> Classification:
    return Classification(
        ResultKind.TIMEOUT,
        f"Timed out after {seconds} seconds before startup was detected",
    )


def unknown_failure_classification(exit_code: int | None) -> Classification:
    if exit_code is None:
        return Classification(ResultKind.UNKNOWN_FAILURE, "Application failed before startup was detected")
    return Classification(ResultKind.UNKNOWN_FAILURE, f"Application failed with exit code {exit_code}")


def _matches_failure(line: str, patterns: tuple[str, ...]) -> bool:
    lower_line = line.lower()
    return any(pattern.lower() in lower_line for pattern in patterns)
