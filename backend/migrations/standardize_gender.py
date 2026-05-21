"""
Migration: Standardize gender field values to consistent capitalization.
Converts all gender values to: Male, Female, Non-Binary, Prefer not to say
"""

from sqlalchemy import text
from app.core.database import SessionLocal

def migrate_gender_values():
    """Standardize gender field capitalization in the database."""
    db = SessionLocal()
    try:
        # Map of old values to new standardized values
        gender_map = {
            'male': 'Male',
            'Male': 'Male',
            'MALE': 'Male',
            'female': 'Female',
            'Female': 'Female',
            'FEMALE': 'Female',
            'non-binary': 'Non-Binary',
            'non_binary': 'Non-Binary',
            'Non-Binary': 'Non-Binary',
            'non binary': 'Non-Binary',
            'prefer not to say': 'Prefer not to say',
            'Prefer not to say': 'Prefer not to say',
            'PREFER NOT TO SAY': 'Prefer not to say',
        }

        # Update each variation to the standard value
        for old_value, new_value in gender_map.items():
            if old_value != new_value:
                db.execute(
                    text(f"UPDATE employees SET gender = :new_val WHERE LOWER(gender) = LOWER(:old_val)"),
                    {"new_val": new_value, "old_val": old_value}
                )

        db.commit()
        print("✓ Gender values standardized successfully")
    except Exception as e:
        print(f"✗ Error standardizing gender values: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_gender_values()
