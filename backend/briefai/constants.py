from enum import Enum

class TaskType(str, Enum):
    SUMMARIZE = "summarize"
    TRANSLATE = "translate"
    ACTION_ITEMS = "action_items"
    LECTURE_NOTES = "lecture_notes"
    DECISIONS = "decisions"
    TERMINOLOGY = "terminology"

class ModelName(str, Enum):
    QWEN3 = "qwen3:1.7b"
    LLAMA32 = "llama3.2:1b"
