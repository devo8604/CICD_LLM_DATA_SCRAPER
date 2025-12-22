import logging
from pathlib import Path

DEFAULT_PROMPTS = {
    "question_system": (
        "You are a Senior DevOps Architect and Automation Engineer. Your goal is to analyze the provided "
        "code/text and generate at most 5 high-quality, specific questions to test deep understanding of this content. "
        "Questions must be answerable solely and directly from the provided text. Focus on conceptual or "
        "functional aspects rather than trivial details. Target quantity: at most 5 questions per code/config file. "
        "Focus on reverse engineering (instruction tuning) - treat the provided code as the solution and "
        "generate prompts that would ask for this specific implementation. Design questions that are 100-300 characters long "
        "and would require detailed answers with code examples or practical implementations. Each question should "
        "be comprehensive and specific enough to require detailed answers. Output ONLY the questions, "
        "one per line, with no preamble or explanations. Ensure each question is detailed enough to require "
        "substantial answers with examples and practical implementations."
    ),
    "question_user": (
        "Code/Text to analyze:\n\n"
        "[The actual code/text content will be inserted here by the system]\n\n"
        "INSTRUCTIONS:\n"
        "1. Analyze the provided code/text content above\n"
        "2. Generate at most 5 high-quality, specific questions to test deep understanding of this content\n"
        "3. Each question should be 100-300 characters long and comprehensive\n"
        "4. Focus on reverse engineering (instruction tuning) - treat the provided code as the solution and "
        "generate prompts that would ask for this specific implementation\n"
        "5. Design questions that would require detailed answers with code examples or practical implementations\n"
        "6. Each question should be specific enough to require substantial answers\n"
        "OUTPUT REQUIREMENTS:\n"
        "- Output ONLY the questions, one per line\n"
        "- Each question must be 100-300 characters long\n"
        "- Each question must end with a question mark '?'\n"
        "- Each question should require detailed answers with examples\n"
        "- Do not include any other text, explanations, or formatting"
    ),
    "answer_system": (
        "Answer the following question, leveraging both the provided context and your broader knowledge base. "
        "Prioritize information from the context, but use your general knowledge to provide a comprehensive "
        "answer if the context is insufficient. If the context directly contradicts your broader knowledge, "
        "use the context's information. Focus on providing concise, relevant answers that directly address "
        "the question without unnecessary verbosity. Include relevant code examples, sample implementations, "
        "or practical examples when appropriate to make your answer comprehensive and actionable. Keep your "
        "answer focused and avoid repetitive information. Target answer context length of 1025-4096 characters."
    ),
    "answer_user": (
        "Answer ONLY and EXACTLY the question above based on the content shown. Your response must directly "
        "address what was asked in the question. If the question asks 'HOW', focus on processes/procedures and "
        "include code examples or step-by-step instructions when possible. If it asks 'WHAT', focus on "
        "descriptions and include relevant examples. If it asks 'WHY', focus on reasons/purposes and provide "
        "practical examples to illustrate the concepts. If it asks 'WHERE', focus on locations/URLs and "
        "include example usage. Make sure your answer is specific to what was asked, not a general summary "
        "of the content. Include code snippets, sample implementations, or practical examples to make your "
        "answer more comprehensive and actionable. Keep your answer focused and avoid unnecessary repetition. "
        "Target answer length of 1025-4096 characters to provide sufficient detail without excessive verbosity."
    ),
}


class PromptManager:
    """Manages loading and retrieval of customizable prompts with themes."""

    def __init__(self, theme: str = "devops", base_dir: str = "prompts"):
        self.base_dir = Path(base_dir)
        self.theme = theme
        self.prompts = {}
        self.load_prompts()

    def load_prompts(self):
        """Load prompts from the current theme directory, falling back to defaults."""
        theme_dir = self.base_dir / self.theme
        if not theme_dir.exists():
            logging.warning(f"Prompt theme directory {theme_dir} not found. Creating it with defaults.")
            theme_dir.mkdir(parents=True, exist_ok=True)

        for key, default_val in DEFAULT_PROMPTS.items():
            file_path = theme_dir / f"{key}.txt"
            if file_path.exists():
                try:
                    self.prompts[key] = file_path.read_text(encoding="utf-8").strip()
                except Exception as e:
                    logging.warning(f"Error reading prompt file {file_path}: {e}. Using default.")
                    self.prompts[key] = default_val
            else:
                # If file doesn't exist in theme dir, create it with default value
                try:
                    file_path.write_text(default_val, encoding="utf-8")
                except Exception as e:
                    logging.warning(f"Could not write default prompt to {file_path}: {e}")
                self.prompts[key] = default_val

    def set_theme(self, theme: str):
        """Switch the current theme and reload prompts."""
        self.theme = theme
        self.load_prompts()

    def get_prompt(self, key: str) -> str:
        """Get a prompt by key, falling back to default if not loaded."""
        return self.prompts.get(key, DEFAULT_PROMPTS.get(key, ""))


# Singleton instance
_instance = None


def get_prompt_manager(theme: str = "devops", base_dir: str = "prompts") -> PromptManager:
    """Get the global PromptManager instance."""
    global _instance
    if _instance is None:
        _instance = PromptManager(theme, base_dir)
    elif theme != _instance.theme:
        _instance.set_theme(theme)
    return _instance
