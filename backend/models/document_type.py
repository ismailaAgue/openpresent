from enum import Enum


class DocumentType(str, Enum):
    RESUME = "resume"
    ACADEMIC = "academic"
    BUSINESS = "business"
    LECTURE = "lecture"
    GENERAL = "general"
