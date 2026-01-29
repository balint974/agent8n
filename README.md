# Unified Agent Config

A cross-platform desktop application to unify configurations for coding agents: **Claude**, **Gemini**, and **Codex**.

## Features

*   **Unified Configuration**: Manage common and agent-specific settings in one place.
*   **Skill Management**: Create and edit Agent Skills (Markdown format) and deploy them to all supported agents.
*   **Project Management**: Deploy configurations to global user paths (`~/.claude`, etc.) and specific project directories.
*   **Cross-Platform**: Runs on Linux, Windows, macOS.

## Prerequisites

*   Python 3.8+
*   Pip

## Installation

1.  Clone the repository.
2.  Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1.  Start the application:

```bash
uvicorn src.main:app --reload
```

2.  Open your browser and navigate to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

3.  **Configure Settings**:
    *   **Common Settings**: JSON configuration applied to *all* agents.
    *   **Specific Settings**: JSON configuration merged into the specific agent's config, overriding common settings if keys collide.

4.  **Manage Skills**:
    *   Add new skills with Name, Description, and Markdown content.
    *   These will be deployed as `<skill-name>.md` files in the `skills/` subdirectory of each agent.

5.  **Manage Projects**:
    *   Add paths to your local projects (e.g., `/Users/me/projects/my-app`).
    *   The app will deploy settings and skills to `.claude/`, `.gemini/`, and `.codex/` folders inside these project directories.

6.  **Deploy**:
    *   Click "Save Config" to save changes to `~/.unified-agent-config.json`.
    *   Click "Deploy to Agents" to write the configuration files to the actual agent directories on disk.

## supported Agents & Paths

The application deploys to the following locations (both Global and in Project folders):

| Agent | Directory | Config File |
| :--- | :--- | :--- |
| **Claude** | `.claude/` | `settings.json` |
| **Gemini** | `.gemini/` | `settings.json` |
| **Codex** | `.codex/` | `settings.json` |

## Data Storage

Your unified configuration is stored in `~/.unified-agent-config.json`.
