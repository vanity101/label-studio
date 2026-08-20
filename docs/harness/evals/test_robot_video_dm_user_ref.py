"""Eval for Data Manager missing User reference crash. Contract: robot-video-dm-user-ref.md"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "docs" / "harness" / "overlays" / "zhiyuan-robot-video"
DM = ROOT / "web" / "libs" / "datamanager" / "src"
if str(OVERLAY) not in sys.path:
    sys.path.insert(0, str(OVERLAY))

import check_overlay as overlay  # noqa: E402


def test_ensure_user_stubs_exists_on_app_store():
    text = (DM / "stores" / "AppStore.js").read_text(encoding="utf-8")
    assert "ensureUserStubs" in text
    assert "self.users.push" in text


def test_set_list_stubs_users_before_assigning_tasks():
    data_store = (DM / "mixins" / "DataStore" / "DataStore.js").read_text(encoding="utf-8")
    assignee = (DM / "stores" / "Assignee.js").read_text(encoding="utf-8")
    tasks = (DM / "stores" / "DataStores" / "tasks.js").read_text(encoding="utf-8")
    assert "collectReferencedUserIds" in assignee
    assert "collectReferencedUserIds" in data_store
    assert "ensureUserStubs" in data_store
    set_list_index = data_store.index("setList({ list")
    stub_index = data_store.index("ensureUserStubs")
    assign_index = data_store.index("self.list = [...newEntity]")
    assert set_list_index < stub_index < assign_index
    assert "ensureUserStubs" in tasks
    assert "collectReferencedUserIds" in tasks


def test_bun_coverage_mentions_numeric_annotators():
    text = (DM / "stores" / "Assignee.test.js").read_text(encoding="utf-8")
    assert "annotators: [1]" in text
    assert "users is empty" in text


def test_multi_view_xml_was_not_rewritten():
    root = overlay.parse_config(overlay.MULTI_VIEW)
    overlay.check_multi_view(root)
    values = overlay._all_choice_values(root)
    assert "异常" in values
    assert "abnormal" in values


def _run_standalone() -> int:
    tests = [
        test_ensure_user_stubs_exists_on_app_store,
        test_set_list_stubs_users_before_assigning_tasks,
        test_bun_coverage_mentions_numeric_annotators,
        test_multi_view_xml_was_not_rewritten,
    ]
    failed = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001 — eval runner must surface any failure
            failed.append(test.__name__)
            print(f"FAIL {test.__name__}: {exc}")
            traceback.print_exc()
    total = len(tests)
    passed = total - len(failed)
    print(f"{passed}/{total} passed, pass_rate={passed / total:.2f}")
    if failed:
        print("Critical failures:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
