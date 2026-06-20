# pyqmh Project Setup Guide

This guide shows how to initialize a new project using `pyqmh` and `pyqmh-tools`, starting from **no virtual environment**.

If you prefer an automated workflow, you can also run the `pyqmh-init` skill to guide and automate project setup.

## Prerequisites

- Python 3.10+ installed
- Git installed (optional, but recommended)
- PowerShell (Windows) or a shell on macOS/Linux

To confirm Python is available:

```powershell
python --version
```

If that fails, try:

```powershell
py --version
```

## 1. Create a Virtual Environment

From your project root:

```powershell
python -m venv .venv
```

If your machine uses the Python launcher:

```powershell
py -m venv .venv
```

## 2. Activate the Virtual Environment

### Windows (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
```

If you get an execution policy error, run this once in the current shell and then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### Windows (cmd)

```cmd
.venv\Scripts\activate.bat
```

### macOS/Linux (bash/zsh)

```bash
source .venv/bin/activate
```

You should now see `(.venv)` in your shell prompt.

## 3. Upgrade Packaging Tools

```powershell
python -m pip install --upgrade pip setuptools wheel
```

## 4. Install pyqmh and pyqmh-tools

```powershell
python -m pip install pyqmh pyqmh-tools
```

## 5. Verify Installation

Check that the packages are installed:

```powershell
python -m pip show pyqmh pyqmh-tools
```

List installed packages (optional):

```powershell
python -m pip list
```

## 6. Freeze Dependencies (Recommended)

```powershell
python -m pip freeze > requirements.txt
```

This helps make your environment reproducible.

## 7. Initialize the Project Structure

Use the `pyqmh_project_init` command to generate the project skeleton and starter files:

```powershell
pyqmh_project_init
```

After initialization, follow the command prompts (if any) and then continue development in the generated structure.

## 8. Add or Remove Modules

After project initialization, use the module management commands to update your project structure.

Add a module:

```powershell
pyqhm_module_add
```

Remove a module:

```powershell
pyqmh_module_remove
```

Run each command from the project root and follow any interactive prompts.

## 9. Daily Workflow

From project root each time you start work:

1. Activate the virtual environment.
2. Install any new dependencies.
3. Run your app/tests.
4. Update `requirements.txt` when dependencies change.

## 10. Troubleshooting

- `python` not found:
  - Use `py` on Windows, or reinstall Python and ensure "Add Python to PATH" is enabled.
- Activation script blocked in PowerShell:
  - Use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` in that shell session.
- Installed package but import fails:
  - Confirm `(.venv)` is active and run `python -m pip list` to verify package installation.

## 11. Optional: Deactivate the Environment

When done:

```powershell
deactivate
```

---
