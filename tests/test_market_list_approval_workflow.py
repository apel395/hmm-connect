from types import SimpleNamespace

from app.services.approval import (
    MARKET_LIST_APPROVAL_CHAIN,
    WORKFLOW_CHAINS,
    _workflow_matches_chain,
)


def _workflow(*roles):
    steps = [
        SimpleNamespace(
            step_order=index,
            name=name,
            approver_role=SimpleNamespace(name=role),
        )
        for index, (name, role) in enumerate(roles, start=1)
    ]
    return SimpleNamespace(steps=steps)


def test_market_list_uses_direct_use_approval_chain():
    assert MARKET_LIST_APPROVAL_CHAIN == (
        (1, "Chef Approval", "CHEF"),
        (2, "PM / Camp Boss Approval", "PM/CAMP BOSS"),
    )
    assert WORKFLOW_CHAINS["ML_APPROVAL"] == MARKET_LIST_APPROVAL_CHAIN


def test_market_list_chain_rejects_legacy_store_first_workflow():
    legacy = _workflow(
        ("Store Approval", "STORE"),
        ("Chef Approval", "CHEF"),
        ("PM / Camp Boss Approval", "PM/CAMP BOSS"),
    )

    assert not _workflow_matches_chain(legacy, MARKET_LIST_APPROVAL_CHAIN)


def test_market_list_chain_accepts_exact_direct_use_workflow():
    direct_use = _workflow(
        ("Chef Approval", "CHEF"),
        ("PM / Camp Boss Approval", "PM/CAMP BOSS"),
    )

    assert _workflow_matches_chain(direct_use, MARKET_LIST_APPROVAL_CHAIN)
