---
name: pyqmh-init
description: 'Initialize a pyqmh project from scratch with no virtual environment, install pyqmh and pyqmh-tools, and run pyqmh_project_init. Use when setting up a new pyqmh workspace or guiding command prompts interactively.'
argument-hint: 'Project path/name'
user-invocable: true
disable-model-invocation: false
---

# Initialize pyqmh Project

Set up a new pyqmh project end-to-end starting with no virtual environment, then initialize project structure.

## When to Use

- Creating a brand-new pyqmh project.
- Repeating the same environment setup process across projects.
- Walking a user through interactive prompts from pyqmh commands.

## Inputs to Collect First

Collect these before running commands:

1. Existing project folder path (where setup commands will run).
2. Shell and OS (PowerShell, cmd, bash/zsh).
3. Whether to initialize Git.
4. Whether to freeze dependencies to `requirements.txt`.
5. Project description — this is passed directly to `pyqmh_project_init` when it prompts `App/project description:`.

## Procedure

1. Validate Python is available.

```powershell
python --version
```

If needed on Windows:

```powershell
py --version
```

2. Create virtual environment.

```powershell
python -m venv .venv
```

Fallback:

```powershell
py -m venv .venv
```

3. Activate virtual environment.

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

cmd:

```cmd
.venv\Scripts\activate.bat
```

bash/zsh:

```bash
source .venv/bin/activate
```

4. Upgrade packaging tools.

```powershell
python -m pip install --upgrade pip setuptools wheel
```

5. Install pyqmh packages.

```powershell
python -m pip install pyqmh pyqmh-tools
```

6. Verify install.

```powershell
python -m pip show pyqmh pyqmh-tools
python -m pip list
```

7. Optional dependency freeze.

```powershell
python -m pip freeze > requirements.txt
```

8. Initialize project structure.

Ask the user for the project description before running this step, then inject it via stdin so the interactive prompt is answered non-interactively:

PowerShell:

```powershell
echo "<project-description>" | pyqmh_project_init
```

cmd:

```cmd
echo <project-description> | pyqmh_project_init
```

bash/zsh:

```bash
echo "<project-description>" | pyqmh_project_init
```

The command will emit `App/project description:` and the piped value will be consumed automatically.

## Interactive Prompt Handling

When a command is interactive, do this every time:

1. Echo the exact prompt text to the user.
2. Present concise options if obvious from the prompt.
3. Ask the user for a single answer.
4. Send exactly one answer back to the terminal prompt.
5. Continue prompt-by-prompt until command completion.
6. Summarize what was configured after the command exits.

Use this response format during interaction:

- Prompt: `<exact prompt from command>`
- Suggested input: `<best default or common value>`
- Your choice: `<ask user to confirm or provide alternative>`

## Completion Checks

Consider setup complete only when all are true:

- Virtual environment exists and is active.
- `pyqmh` and `pyqmh-tools` are installed.
- `pyqmh_project_init` completed without errors.
- Final project state summary is provided to the user.

## Troubleshooting

- `python` not found: try `py` or fix PATH/Python install.
- PowerShell activation blocked: use process-scoped execution policy command.
- Package import issues: confirm active venv and rerun `python -m pip list`.
- Command not found (`pyqmh_project_init` or module commands): verify venv activation and reinstall `pyqmh-tools`.
