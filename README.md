# app-runner

`app-runner` is a lightweight CLI that runs a Java/Spring Boot project the same
way a developer usually would from an IDE run configuration: detect the build
tool, prefer the project wrapper, start the app, watch logs, and report a clear
success or failure.

It does not use an LLM.

## Install for development

```powershell
python -m pip install -e .
```

## Usage

Run Spring Boot app:

```powershell
app-runner C:\path\to\spring-project --timeout 120
```

Run OpenRewrite dry run by injecting plugin XML from a local `.txt` file:

```powershell
app-runner C:\path\to\legacy-app --rewrite-plugin-txt C:\path\to\rewrite-plugin.txt --timeout 300
```

For multi-module Maven, target a module pom:

```powershell
app-runner C:\path\to\legacy-app --module shoppoc-app --rewrite-plugin-txt C:\path\to\rewrite-plugin.txt --timeout 300
```

For Maven multi-module projects, target the runnable module:

```powershell
app-runner C:\path\to\project --module app-service --timeout 120
```

`--module` targets `app-service/pom.xml` directly to avoid running `spring-boot:run`
on the parent aggregator POM.

If Maven cannot infer the Spring Boot main class, set it explicitly:

```powershell
app-runner C:\path\to\project --module app-service --main-class com.example.Application
```

By default, `app-runner` keeps the application attached after startup is
detected, so you continue to see logs until the app exits or you press Ctrl+C.
For CI-style startup checks, stop the app after the success signal:

```powershell
app-runner C:\path\to\spring-project --timeout 120 --stop-after-start
```

Equivalent module invocation:

```powershell
python -m app_runner C:\path\to\spring-project --timeout 120
```

## First-version behavior

- Detects Maven by `pom.xml`.
- Detects Gradle by `build.gradle`, `build.gradle.kts`, or `settings.gradle`.
- Prefers `mvnw` / `gradlew` wrappers when present.
- Runs Maven apps with `spring-boot:run`.
- Runs Gradle apps with `bootRun`.
- Captures stdout and stderr.
- Streams output while scanning for startup success and common failures.
- Stops waiting after a configurable timeout.
- Does not use IntelliJ APIs or control IntelliJ directly.
- Supports Maven module targeting via `--module`.
- Supports Maven main class override via `--main-class`.
- Supports OpenRewrite plugin injection from `--rewrite-plugin-txt` and runs `rewrite:dryRun`.

## Exit codes

- `0`: application started successfully.
- `1`: startup failed or timed out.
- `2`: CLI usage or project detection error.
