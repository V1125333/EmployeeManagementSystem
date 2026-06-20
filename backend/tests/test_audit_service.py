import unittest
from datetime import date

from app.services.audit_service import changed_fields, mask_audit_value, sanitize_values


class AuditServiceTests(unittest.TestCase):
    def test_sensitive_values_are_masked(self):
        self.assertEqual(mask_audit_value("phone", "+1 5722082825"), "*******2825")
        self.assertEqual(mask_audit_value("personal_email", "trilok@reknew.com"), "tr****@reknew.com")
        self.assertEqual(mask_audit_value("date_of_birth", date(2001, 6, 30)), "****-**-30")
        self.assertEqual(mask_audit_value("current_address", "123 Main St"), "[ADDRESS_CHANGED]")
        self.assertEqual(mask_audit_value("salary", "100000"), "[SENSITIVE_VALUE_CHANGED]")

    def test_never_log_fields_are_removed(self):
        values = sanitize_values({
            "first_name": "Trilok",
            "password_hash": "secret",
            "totp_secret": "secret",
            "setup_code": "123456",
        })
        self.assertEqual(values, {"first_name": "Trilok"})

    def test_changed_fields_masks_before_returning_diff(self):
        diff = changed_fields(
            {"phone": "1234567890", "department": "Engineering"},
            {"phone": "1234560000", "department": "Product"},
        )
        self.assertEqual(diff["phone"]["old"], "******7890")
        self.assertEqual(diff["phone"]["new"], "******0000")
        self.assertEqual(diff["department"]["old"], "Engineering")
        self.assertEqual(diff["department"]["new"], "Product")


if __name__ == "__main__":
    unittest.main()
