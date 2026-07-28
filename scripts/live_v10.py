"""Live validation for v1.0 shelf import and refresh workflows."""

from __future__ import annotations

import argparse
import json
import time

from substance_painter_mcp.client import PainterRemote
from substance_painter_mcp.operations import PainterOperations


def emit(label: str, value) -> None:
    print(label, json.dumps(value, ensure_ascii=False, indent=2))


def run(remote: PainterRemote, code: str, params=None):
    envelope = remote.execute_python_json(code, params)
    if not envelope.get("success"):
        raise RuntimeError(envelope)
    return envelope["data"]


def wait_until_idle(operations: PainterOperations, shelf_name: str, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        shelf = next(
            item for item in operations.list_shelves()["shelves"]
            if item["name"] == shelf_name
        )
        if not shelf["crawling"]:
            return
        time.sleep(0.25)
    raise TimeoutError(f"Shelf did not become idle within {timeout} seconds")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--shelf-path", required=True)
    parser.add_argument("--shelf-name", required=True)
    args = parser.parse_args()

    remote = PainterRemote()
    operations = PainterOperations(remote)
    original = operations.project_info()
    if not original["open"] or not original["path"]:
        raise RuntimeError("A saved disposable project must be open")
    operations.save_project(confirm=True)

    created = False
    try:
        shelf = run(
            remote,
            """
import substance_painter.resource as resource
if resource.Shelves.exists(params["name"]):
    raise RuntimeError(f'Shelf already exists: {params["name"]}')
resource.Shelves.add(params["name"], params["path"])
item = resource.Shelf(params["name"])
result = {
    "name": item.name(),
    "path": item.path(),
    "can_import": item.can_import_resources(),
}
""",
            {"name": args.shelf_name, "path": args.shelf_path},
        )
        created = True
        emit("temporary_shelf", shelf)
        if not shelf["can_import"]:
            raise AssertionError("Temporary shelf is not writable")

        wait_until_idle(operations, args.shelf_name)
        shelves = operations.list_shelves()
        emit("shelves", shelves)
        if args.shelf_name not in {item["name"] for item in shelves["shelves"]}:
            raise AssertionError("Temporary shelf was not listed")

        resource_name = f"mcp_v10_{int(time.time())}"
        imported = operations.import_shelf_resource(
            args.source,
            "TEXTURE",
            shelf_name=args.shelf_name,
            name=resource_name,
            group="MCP Validation",
            confirm=True,
        )
        emit("imported", imported)
        if imported["context"] != args.shelf_name or not imported["verified"]:
            raise AssertionError("Imported shelf resource identity was not verified")

        wait_until_idle(operations, args.shelf_name)
        started = operations.start_shelf_refresh(args.shelf_name, confirm=True)
        emit("refresh_started", started)
        deadline = time.time() + 120
        while time.time() < deadline:
            job = operations.get_shelf_refresh_job(started["job_id"])
            if job["found"] and job["job"]["status"] in {"success", "failed"}:
                break
            time.sleep(0.25)
        else:
            raise TimeoutError("Shelf refresh did not finish within 120 seconds")
        emit("refresh_terminal", job)
        if job["job"]["status"] != "success" or job["crawling"]:
            raise AssertionError(f"Shelf refresh failed: {job['job']['error']}")

        retrieved = run(
            remote,
            """
import substance_painter.resource as resource
identifier = resource.ResourceID.from_url(params["url"])
result = [
    {
        "url": item.identifier().url(),
        "location": item.location().name,
        "type": item.type().name,
    }
    for item in resource.Resource.retrieve(identifier)
]
""",
            {"url": imported["url"]},
        )
        emit("retrieved", retrieved)
        if not any(item["url"] == imported["url"] for item in retrieved):
            raise AssertionError("Imported resource disappeared after refresh")
    finally:
        cleanup = run(
            remote,
            """
import substance_painter.project as project
import substance_painter.resource as resource
if project.is_open():
    project.close()
removed = False
if params["remove"] and resource.Shelves.exists(params["name"]):
    resource.Shelves.remove(params["name"])
    removed = True
project.open(params["project_path"])
result = {
    "removed": removed,
    "restored_path": str(project.file_path()) if project.file_path() else None,
    "open": project.is_open(),
}
""",
            {
                "name": args.shelf_name,
                "project_path": original["path"],
                "remove": created,
            },
        )
        emit("cleanup", cleanup)
        if created and not cleanup["removed"]:
            raise AssertionError("Temporary shelf was not removed")
        if cleanup["restored_path"].casefold() != original["path"].casefold():
            raise AssertionError("Original project was not restored")

    restored = operations.project_info()
    emit("restored", restored)
    if restored["path"].casefold() != original["path"].casefold():
        raise AssertionError("Original project verification failed")


if __name__ == "__main__":
    main()
