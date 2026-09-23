from app.core.property_actions import PropertyAction


def test_property_actions_define_supported_actions():
    assert {
        action.value
        for action in PropertyAction
    } == {
        "property_management",
        "plate_operations",
        "property_verification",
        "installation_verification",
    }


def test_property_action_values_match_existing_access_types():
    assert PropertyAction.PROPERTY_MANAGEMENT.value == "property_management"
    assert PropertyAction.PLATE_OPERATIONS.value == "plate_operations"
    assert (
        PropertyAction.PROPERTY_VERIFICATION.value
        == "property_verification"
    )
    assert (
        PropertyAction.INSTALLATION_VERIFICATION.value
        == "installation_verification"
    )
