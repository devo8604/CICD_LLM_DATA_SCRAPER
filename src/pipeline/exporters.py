import csv
import json
import logging

from src.core.config import AppConfig
from src.data.db_manager import DBManager


class DataExporter:
    def __init__(self, db_manager: DBManager, config: AppConfig):
        if config is None:
            raise ValueError("Config must be provided")
        self.db_manager = db_manager
        self.config = config

    def _get_all_conversations(self):
        return self.db_manager.get_all_training_samples()

    def _format_conversation_to_template(self, conversation, template_name):
        system_content = ""
        user_content_list = []
        assistant_content_list = []

        # Extract roles and content from turns
        for turn in conversation["turns"]:
            if turn["role"] == "system":
                system_content = turn["content"]
            elif turn["role"] == "user":
                user_content_list.append(turn["content"])
            elif turn["role"] == "assistant":
                assistant_content_list.append(turn["content"])

        final_user_content = "\n".join(user_content_list)
        final_assistant_content = "\n".join(assistant_content_list)

        match template_name:
            case "csv":
                return {
                    "user_content": final_user_content,
                    "assistant_content": final_assistant_content,
                }
            case "llama3":
                return self.config.LLAMA3_CHAT_TEMPLATE.format(
                    system_content=(system_content if system_content else "You are a helpful AI assistant."),
                    user_content=final_user_content,
                    assistant_content=final_assistant_content,
                )
            case "mistral":
                system_and_user_content = (f"{system_content}\n\n" if system_content else "") + final_user_content
                return self.config.MISTRAL_CHAT_TEMPLATE.format(
                    system_and_user_content=system_and_user_content,
                    assistant_content=final_assistant_content,
                )
            case "gemma":
                return self.config.GEMMA_CHAT_TEMPLATE.format(
                    user_content=final_user_content,
                    assistant_content=final_assistant_content,
                )
            case "alpaca-jsonl":
                return {
                    "instruction": final_user_content,
                    "input": "",
                    "output": final_assistant_content,
                }
            case "chatml-jsonl":
                messages = []
                if system_content:
                    messages.append({"role": "system", "content": system_content})
                messages.append({"role": "user", "content": final_user_content})
                messages.append({"role": "assistant", "content": final_assistant_content})
                return {"messages": messages}
            case _:
                raise ValueError(f"Unsupported template name: {template_name}")

    def export_data(self, template_name, output_file):  # Renamed format_type to template_name
        all_conversations = self._get_all_conversations()

        if template_name == "csv":
            with open(output_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["user_content", "assistant_content"])
                writer.writeheader()
                for conversation in all_conversations:
                    formatted_entry = self._format_conversation_to_template(conversation, template_name)
                    writer.writerow(formatted_entry)
            logging.info(
                f"Successfully exported {len(all_conversations)} conversations to {output_file} in CSV format."
            )
            return

        exported_lines = []
        for conversation in all_conversations:
            # Check if the template directly produces a JSON object or a string
            if template_name in ["alpaca-jsonl", "chatml-jsonl"]:
                formatted_entry = self._format_conversation_to_template(conversation, template_name)
                # Ensure it's a dictionary/list before dumping
                if isinstance(formatted_entry, (dict, list)):
                    exported_lines.append(json.dumps(formatted_entry))
                else:
                    raise ValueError(
                        f"Template '{template_name}' did not return a JSON-serializable object for conversation "
                        f"{conversation['sample_id']}."
                    )
            else:
                formatted_string = self._format_conversation_to_template(conversation, template_name)
                if formatted_string:  # Only add if formatting was successful
                    exported_lines.append(formatted_string)

        with open(output_file, "w", encoding="utf-8") as f:
            for line in exported_lines:
                f.write(line + "\n")
        logging.info(
            f"Successfully exported {len(exported_lines)} conversations to {output_file} in {template_name} format."
        )
