"""
Prompt templates and system instructions for all post-processing tasks in BriefAI.
Includes few-shot examples for structured tasks (lecture notes, decisions log).
"""

from __future__ import annotations

# Task-specific system instructions to control formatting, tone, and guardrails
SYSTEM_PROMPTS: dict[str, str] = {
    "summarize": (
        "You are an expert meeting assistant. Your task is to provide clear, concise, "
        "and structured summaries of meeting transcripts in clean Markdown. Focus on "
        "the main topics discussed, key points made, and the overall outcome. Do not "
        "include conversational filler."
    ),
    "translate": (
        "You are an expert translator. Your task is to translate the provided text "
        "accurately to the target language, preserving the original tone, style, and meaning. "
        "Output ONLY the translated text, with no introductory or concluding remarks."
    ),
    "action_items": (
        "You are a project manager assistant. Your task is to extract all action items, "
        "tasks, and follow-ups from the transcript. Format them in a clean Markdown list "
        "detailing the task, the assignee (if specified, otherwise 'Unassigned'), and "
        "any context/deadline."
    ),
    "lecture_notes": (
        "You are an academic study assistant. Your task is to compile the provided transcript "
        "into highly structured, detailed study/lecture notes in Markdown. Use clear headings, "
        "bullet points, bold key terms, and summaries of educational concepts."
    ),
    "decisions": (
        "You are a business analyst assistant. Your task is to extract all key decisions "
        "made during the meeting. Format each decision in a clean Markdown log explaining "
        "the context, the decision taken, and the rationale or consequences."
    ),
    "terminology": (
        "You are a technical editor. Your task is to identify and extract key terms, "
        "acronyms, abbreviations, and technical jargon from the transcript. Define each "
        "term clearly based on the context of the discussion."
    ),
}

# User prompt templates containing instructions and few-shot examples
TEMPLATES: dict[str, str] = {
    "summarize": (
        "Meeting Transcript:\n"
        "\"\"\"\n"
        "{transcript}\n"
        "\"\"\"\n\n"
        "Please provide the summary of the meeting transcript above in clean Markdown using the following structure:\n\n"
        "### 1. Executive Summary\n"
        "[A concise 2-3 sentence paragraph summarizing the high-level purpose and outcome of the meeting]\n\n"
        "### 2. Key Themes\n"
        "- **[Theme Name]**: [Description of discussion around this theme]\n"
        "- **[Theme Name]**: [Description of discussion around this theme]\n\n"
        "### 3. Important Details\n"
        "- [Bullet point of key information]\n"
        "- [Bullet point of key information]"
    ),
    
    "translate": (
        "Transcript to translate:\n"
        "\"\"\"\n"
        "{transcript}\n"
        "\"\"\"\n\n"
        "Translate the transcript above into {target_language}. Output only the translated text."
    ),
    
    "action_items": (
        "Meeting Transcript:\n"
        "\"\"\"\n"
        "{transcript}\n"
        "\"\"\"\n\n"
        "Please extract all action items and tasks identified in the transcript above. Format as follows:\n\n"
        "### Action Items\n\n"
        "- **Action Item**: [Description of the task]\n"
        "  - **Assignee**: [Name of person, or 'Unassigned' if not specified]\n"
        "  - **Next Steps**: [Any steps, details, or deadlines mentioned in the text]"
    ),
    
    "lecture_notes": (
        "Transcript:\n"
        "\"\"\"\n"
        "{transcript}\n"
        "\"\"\"\n\n"
        "Please compile this transcript into structured study notes. Follow this format:\n\n"
        "# Study Notes: [Topic]\n\n"
        "## 1. Key Concepts\n"
        "- **[Concept Name]**: [Explanation]\n\n"
        "## 2. Detailed Summary\n"
        "- [Bulleted details of the discussion]\n\n"
        "## 3. Key Takeaways\n"
        "- [Summary of main learnings]\n\n"
        "---\n"
        "Example:\n"
        "Input Transcript: \"Okay class, today we are learning about Photosynthesis. This is the process where green plants use sunlight to synthesize nutrients from carbon dioxide and water. The key pigment involved is chlorophyll, which absorbs light energy. Remember, oxygen is produced as a byproduct.\"\n\n"
        "Structured Study Notes:\n"
        "# Study Notes: Photosynthesis\n\n"
        "## 1. Key Concepts\n"
        "- **Photosynthesis**: The process by which green plants synthesize nutrients from carbon dioxide and water using sunlight.\n"
        "- **Chlorophyll**: The primary green pigment in plants responsible for absorbing light energy.\n\n"
        "## 2. Detailed Summary\n"
        "- Discussion of how plants utilize sunlight as an energy source.\n"
        "- Input requirements: carbon dioxide and water.\n"
        "- Output/byproduct: oxygen.\n\n"
        "## 3. Key Takeaways\n"
        "- Photosynthesis is the fundamental energy conversion process for plant life.\n"
        "- Chlorophyll is essential for capturing solar energy.\n"
        "---\n\n"
        "Now compile the new transcript:\n"
        "Transcript:\n"
        "\"\"\"\n"
        "{transcript}\n"
        "\"\"\"\n"
    ),
    
    "decisions": (
        "Transcript:\n"
        "\"\"\"\n"
        "{transcript}\n"
        "\"\"\"\n\n"
        "Please extract all decisions made from this transcript. Format each decision as:\n\n"
        "### Decision: [Brief description of decision]\n"
        "- **Context**: [Why this decision was discussed]\n"
        "- **Decision Taken**: [What was decided]\n"
        "- **Rationale/Consequences**: [Reasoning or next steps resulting from the decision]\n\n"
        "---\n"
        "Example:\n"
        "Input Transcript: \"We need to figure out where to host the database. AWS is powerful but expensive. Since we are a startup, let's go with Supabase for now. It will save us database admin overhead and cost. If we scale, we can migrate to AWS later. Let's get that set up by Friday.\"\n\n"
        "Decisions Log:\n"
        "### Decision: Database Hosting Platform\n"
        "- **Context**: Need to choose a hosting provider for the database while balancing cost and administrative overhead.\n"
        "- **Decision Taken**: Host the database on Supabase for the initial startup phase, with a plan to migrate to AWS if scaling demands it.\n"
        "- **Rationale/Consequences**: Supabase reduces setup cost and DB administration work. Task assignee must set this up by Friday.\n"
        "---\n\n"
        "Now extract decisions from the new transcript:\n"
        "Transcript:\n"
        "\"\"\"\n"
        "{transcript}\n"
        "\"\"\"\n"
    ),
    
    "terminology": (
        "Transcript:\n"
        "\"\"\"\n"
        "{transcript}\n"
        "\"\"\"\n\n"
        "Identify and list key technical terms, acronyms, or jargon from the transcript, and provide definitions based on the context. Format as:\n\n"
        "### Key Terminology\n\n"
        "- **[Term/Acronym]**: [Definition]"
    ),
}
