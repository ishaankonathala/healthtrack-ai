from enum import Enum


class SymptomCategory(str, Enum):
    HEADACHE_NEUROLOGICAL = "Headache / Neurological"
    FEVER = "Fever"
    RESPIRATORY = "Respiratory"
    DIGESTIVE = "Digestive"
    MUSCULOSKELETAL = "Musculoskeletal"
    SKIN = "Skin"
    CARDIOVASCULAR = "Cardiovascular"
    GENERAL_OTHER = "General / Other"


SYMPTOM_CATEGORY_VALUES = tuple(category.value for category in SymptomCategory)
SYMPTOM_CATEGORY_SQL_VALUES = ", ".join(f"'{value}'" for value in SYMPTOM_CATEGORY_VALUES)
