from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


class RewriteError(Exception):
    pass


@dataclass(frozen=True)
class RewritePreparation:
    pom_path: Path
    plugin_coordinates: tuple[str, str]


def prepare_rewrite_plugin(
    project_path: Path,
    plugin_txt_path: Path,
    module: str | None,
    backup: bool = True,
) -> RewritePreparation:
    pom_path = _resolve_pom_path(project_path, module)
    plugin_xml = _read_plugin_xml(plugin_txt_path)
    plugin_element = _parse_plugin_xml(plugin_xml)
    coordinates = _plugin_coordinates(plugin_element)

    tree = ET.parse(pom_path)
    root = tree.getroot()
    namespace = _namespace_uri(root.tag)
    if namespace:
        ET.register_namespace("", namespace)

    build = _find_or_create_child(root, "build", namespace)
    plugins = _find_or_create_child(build, "plugins", namespace)
    _upsert_plugin(plugins, plugin_element, coordinates, namespace)

    if backup:
        backup_path = pom_path.with_suffix(".xml.bak")
        shutil.copyfile(pom_path, backup_path)

    tree.write(pom_path, encoding="utf-8", xml_declaration=True)
    return RewritePreparation(pom_path=pom_path, plugin_coordinates=coordinates)


def build_rewrite_command(maven_executable: str, module: str | None) -> list[str]:
    command = [maven_executable]
    if module:
        command.extend(["-f", str(Path(module) / "pom.xml")])
    command.append("rewrite:dryRun")
    return command


def _resolve_pom_path(project_path: Path, module: str | None) -> Path:
    if module:
        pom_path = project_path / module / "pom.xml"
    else:
        pom_path = project_path / "pom.xml"

    if not pom_path.is_file():
        raise RewriteError(f"Could not find pom.xml at: {pom_path}")
    return pom_path


def _read_plugin_xml(plugin_txt_path: Path) -> str:
    if not plugin_txt_path.is_file():
        raise RewriteError(f"Plugin txt file does not exist: {plugin_txt_path}")

    content = plugin_txt_path.read_text(encoding="utf-8").strip()
    if not content:
        raise RewriteError("Plugin txt file is empty")
    return content


def _parse_plugin_xml(plugin_xml: str) -> ET.Element:
    try:
        element = ET.fromstring(plugin_xml)
    except ET.ParseError as exc:
        raise RewriteError(f"Plugin txt is not valid XML: {exc}") from exc

    if _local_name(element.tag) != "plugin":
        raise RewriteError("Plugin txt must contain a single <plugin>...</plugin> element")
    return element


def _plugin_coordinates(plugin_element: ET.Element) -> tuple[str, str]:
    group_id = _child_text(plugin_element, "groupId")
    artifact_id = _child_text(plugin_element, "artifactId")
    if not artifact_id:
        raise RewriteError("Plugin XML must include <artifactId>")
    if not group_id:
        group_id = "org.openrewrite.maven"
    return group_id.strip(), artifact_id.strip()


def _upsert_plugin(
    plugins_node: ET.Element,
    plugin_element: ET.Element,
    coordinates: tuple[str, str],
    namespace: str | None,
) -> None:
    expected_group, expected_artifact = coordinates
    for existing in list(plugins_node):
        if _local_name(existing.tag) != "plugin":
            continue
        existing_group = (_child_text(existing, "groupId") or "org.apache.maven.plugins").strip()
        existing_artifact = (_child_text(existing, "artifactId") or "").strip()
        if existing_group == expected_group and existing_artifact == expected_artifact:
            plugins_node.remove(existing)
            break

    plugins_node.append(_with_namespace(plugin_element, namespace))


def _with_namespace(element: ET.Element, namespace: str | None) -> ET.Element:
    copied = ET.fromstring(ET.tostring(element, encoding="unicode"))
    if not namespace:
        return copied

    for node in copied.iter():
        node.tag = f"{{{namespace}}}{_local_name(node.tag)}"
    return copied


def _find_or_create_child(parent: ET.Element, name: str, namespace: str | None) -> ET.Element:
    child = _find_child(parent, name)
    if child is not None:
        return child
    tag = f"{{{namespace}}}{name}" if namespace else name
    child = ET.Element(tag)
    parent.append(child)
    return child


def _find_child(parent: ET.Element, local_name: str) -> ET.Element | None:
    for child in parent:
        if _local_name(child.tag) == local_name:
            return child
    return None


def _child_text(parent: ET.Element, local_name: str) -> str | None:
    child = _find_child(parent, local_name)
    if child is None or child.text is None:
        return None
    return child.text


def _namespace_uri(tag: str) -> str | None:
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return None


def _local_name(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag
