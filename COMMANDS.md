# COMMANDS.md — working reference

Windows 11 / PowerShell / VS Code terminal. Run everything from the repo root.

---

## Daily rhythm

```powershell
git checkout main                 # switch to main
git pull                          # bring down anything merged on GitHub
git checkout -b feature/thing     # new branch, switch to it in one step
# ...work...
git status                        # what changed, what's staged
git add path/to/file.py           # stage specific files (deliberate > git add .)
git commit -m "message"           # record the staged snapshot
git push -u origin feature/thing  # send branch to GitHub; -u links it (first push only)
git push                          # every push after that
# PR on GitHub -> Merge -> Confirm
git checkout main && git pull     # sync local main with the merge
```

## Git — inspection

```powershell
git --version                            # is git installed at all
git branch                               # list branches, * marks current
git status                               # tracked/untracked/staged
git ls-files                             # every file git TRACKS (ignores .venv etc.)
git ls-files --others --exclude-standard # on disk, not ignored, not yet added
git log --oneline -5                     # last 5 commits, one line each
git check-ignore -v model.joblib         # WHY is this file being ignored (file + line)
```

## Git — one-time setup

```powershell
git clone https://github.com/Daniel8B/clinical-trial-matcher.git
git config --global user.name "Daniel"
git config --global user.email "..."     # public + permanent on public repos
git config --global --list               # verify
```

## Environment

```powershell
python -m venv .venv                     # create the venv (once, per project)
.venv\Scripts\Activate.ps1               # activate — prompt must show (.venv)
python --version
where.exe python                         # which python wins on PATH, in order
pip install fastapi "uvicorn[standard]"  # quotes needed: [] is PowerShell syntax
pip freeze > requirements.txt            # re-run after EVERY install
python -c "import fastapi; print(fastapi.__version__)"   # run Python from the shell
```

## Running things

```powershell
python train_model.py                              # run a script top-to-bottom
uvicorn clinical_trial_matcher.main:app --reload    # dev server; pkg.module:variable
# Ctrl+C to stop — graceful shutdown, runs lifespan shutdown code
```

Then in the browser: `http://127.0.0.1:8000/docs` → Try it out → Execute.
Reloading `/docs` does **not** call an endpoint.

## Hitting the API from the terminal

```powershell
curl.exe --% -X POST http://127.0.0.1:8000/search -H "Content-Type: application/json" -d "{\"query\":\"diabetes\",\"top_k\":3}"
```

- `curl.exe` not `curl` — bare `curl` is a PowerShell alias for something else
- `--%` — stop-parsing token; without it PS 5.1 mangles the quotes
- `-X` method · `-H` header · `-d` body

## PowerShell — files and paths

```powershell
Get-Location                                  # where am I
Get-ChildItem                                 # what's here
Get-ChildItem -Recurse -Filter train_model.py # find a file anywhere below
Get-Content .gitignore                        # print a file
Get-Content .gitignore | Select-String model  # grep a file
mkdir tests                                   # new folder
New-Item tests\.gitkeep -ItemType File        # new empty file
Move-Item clinical_trial_matcher\train_model.py .   # move; . = here
Test-Path .venv\Scripts\python.exe            # does this exist -> True/False
Remove-Item .venv -Recurse -Force             # delete a folder and contents
```

## VS Code

| Shortcut | Does |
|---|---|
| `` Ctrl+` `` | new terminal |
| `` Ctrl+Shift+` `` or `+` in panel | *second* terminal (server in one, git in the other) |
| `Ctrl+Shift+P` | Command Palette |
| `Ctrl+S` | save — `--reload` only picks up saved files |

Palette commands used: `Python: Select Interpreter` (after moving the repo), `Developer: Reload Window` (stale interpreter error), `Git: Clone`.

## Docker — day 4

```powershell
docker --version
docker run hello-world     # end-to-end check of the install
```