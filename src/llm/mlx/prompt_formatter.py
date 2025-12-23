"MLX Prompt formatting and parsing utilities."


class MLXPromptFormatter:
    """Handles formatting prompts and parsing responses for MLX models."""

    def __init__(self, tokenizer, prompt_manager, context_window: int):
        self.tokenizer = tokenizer
        self.prompt_manager = prompt_manager
        self.context_window = context_window

    def format_question_prompt(self, content: str, instruction: str) -> str:
        """Format the prompt for question generation."""
        safe_limit = self.context_window - 1000
        if safe_limit < 500:
            safe_limit = 500

        truncated_content = self._truncate_to_tokens(content, safe_limit)

        system_msg = (
            "You are an expert researcher and analyst. Generate only the specific questions requested by the "
            "user. Do not include any template instructions or system messages in your response."
        )

        instructional_part = self.prompt_manager.get_prompt("question_user")

        user_msg = (
            f"Based on the following content, analyze its meaning and generate multiple relevant questions:\n\n"
            f"CONTENT:\n```\n{truncated_content}\n```\n\n"
            f"INSTRUCTION: {instruction}\n\n"
            f"{instructional_part}\n\n"
            "IMPORTANT: Return only clear, specific questions. Each question should be on its own line, formatted as "
            '"Q1: What does this content do?", "Q2: How is this organized?", etc. '
            "Do NOT include ANSWER: sections or empty code blocks like ``` in your response."
        )

        return self._apply_chat_template(system_msg, user_msg)

    def format_answer_prompt(self, question: str, context: str, max_tokens: int) -> str:
        """Format the prompt for answer generation."""
        safe_limit = self.context_window - max_tokens - 500
        if safe_limit < 500:
            safe_limit = 500

        truncated_content = self._truncate_to_tokens(context, safe_limit)

        system_msg = (
            "You are a precise question-answering expert. You will be given content and a specific "
            "question about that content. ANSWER ONLY THE QUESTION ASKED using information from the "
            "content. Never give generic answers about the content unrelated to the specific question."
        )

        instructional_part = self.prompt_manager.get_prompt("answer_user")

        user_msg = f"CONTENT FOR REFERENCE:\n```\n{truncated_content}\n```\n\nSPECIFIC QUESTION (ANSWER THIS EXACTLY): {question}\n\nRESPONSE: {instructional_part}"

        return self._apply_chat_template(system_msg, user_msg)

    def _apply_chat_template(self, system_msg: str, user_msg: str) -> str:
        """Apply chat template using tokenizer if available."""
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        if hasattr(self.tokenizer, "apply_chat_template"):
            return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        # Fallback
        prompt_parts = []
        for message in messages:
            role = message["role"]
            content = message["content"]
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
        return "\n\n".join(prompt_parts)

    def parse_questions(self, text: str) -> list[str]:
        """Parse generated text into a list of questions."""
        if not text or not text.strip():
            return []

        lines = text.split("\n")
        questions = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if ":" in line and line.startswith(("Q", "q")):
                import re

                q_pattern = r"^[Qq]\d+:\s*(.+?\?)$"
                match = re.match(q_pattern, line)
                if match:
                    question = match.group(1).strip()
                    if question and len(question) > 3:
                        questions.append(question)
                elif "?" in line:
                    content = line.split(":", 1)[1].strip()
                    if "?" not in content and len(content) > 3:
                        questions.append(f"{content}?")

            elif "?" in line:
                parts = line.split("?")
                for part in parts[:-1]:
                    question = (part + "?").strip()
                    question = (
                        question.replace("Q:", "")
                        .replace("Question:", "")
                        .replace("1.", "")
                        .replace("2.", "")
                        .replace("3.", "")
                        .replace("4.", "")
                        .replace("5.", "")
                        .replace("6.", "")
                        .replace("7.", "")
                        .replace("8.", "")
                        .replace("9.", "")
                        .replace("10.", "")
                        .strip()
                    )
                    if question and len(question) > 3:
                        questions.append(question)

            import re

            numbered_pattern = r"\d+\.\s*(.+?\?)"
            matches = re.findall(numbered_pattern, line)
            for match in matches:
                cleaned_match = match.strip()
                if cleaned_match and len(cleaned_match) > 3:
                    questions.append(cleaned_match)

        seen = set()
        unique_questions = []
        for q in questions:
            if q not in seen and q.strip():
                seen.add(q)
                unique_questions.append(q.strip())

        if not unique_questions and text.strip():
            if "?" not in text:
                return [f"{text.strip()}?"]
            return [text.strip()]

        return unique_questions

    def _truncate_to_tokens(self, content: str, max_prompt_tokens: int) -> str:
        """Truncate content to a specific number of tokens."""
        if not content:
            return ""

        # Pre-truncate by characters to avoid tokenizing massive strings
        estimated_char_limit = max_prompt_tokens * 4
        if len(content) > estimated_char_limit:
            content = content[:estimated_char_limit]

        try:
            tokens = self.tokenizer.encode(content)
            if len(tokens) > max_prompt_tokens:
                truncated_tokens = tokens[:max_prompt_tokens]
                return self.tokenizer.decode(truncated_tokens)
            return content
        except Exception:
            char_limit = max_prompt_tokens * 3
            return content[:char_limit]
