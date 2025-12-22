# Customizable Prompts

This directory contains themes for the LLM Data Pipeline prompts.

## Directory Structure

- `devops/`: The default theme focused on CI/CD, Kubernetes, and DevOps.
- `template/`: A boilerplate theme you can copy to create your own custom prompts.

## How to Create a Custom Theme

1. Copy the `template/` directory to a new name (e.g., `prompts/my-theme/`).
2. Edit the `.txt` files in your new directory.
3. Update your `cicdllm.yaml` configuration to use your new theme:

```yaml
pipeline:
  prompt_theme: "my-theme"
```

4. Restart the application or use the "Reload Prompts" command in the TUI (Press `C` to open the Command Palette).
