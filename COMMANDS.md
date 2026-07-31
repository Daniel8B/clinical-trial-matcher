# COMMANDS.md — working reference

Windows 11 / PowerShell 5.1 / VS Code terminal. Run everything from the repo root.

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

**Committing is what fixes work to a branch.** Uncommitted changes belong to the
working directory and will follow you across a `git checkout`.

## Git — inspection

```powershell
git --version                            # is git installed at all
git branch                               # list branches, * marks current
git branch -d name1 name2                # delete merged branches (refuses if unmerged)
git status                               # tracked/untracked/staged
git ls-files                             # every file git TRACKS (ignores .venv etc.)
git ls-files .env                        # empty = never tracked, ever
git ls-files --others --exclude-standard # on disk, not ignored, not yet added
git log --oneline -5                     # last 5 commits, one line each
git diff --stat                          # which files changed, how much
git check-ignore -v .env                 # WHY is this ignored (file + line number)
```

`Bin 718 -> 928 bytes` in `git diff --stat` = git sees the file as binary.
For a text file that means wrong encoding — see requirements.txt below.

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
pip install -r requirements.txt          # install from the pinned file
python -c "import fastapi; print(fastapi.__version__)"   # run Python from the shell
```

### requirements.txt — encoding matters

```powershell
pip freeze | Out-File -Encoding ascii requirements.txt   # ALWAYS this
# NOT: pip freeze > requirements.txt   -- PS 5.1 writes UTF-16, pip in Linux may choke
Get-Content requirements.txt -Encoding Byte -TotalCount 4   # 255 254 = UTF-16 (bad)
```

Re-run the freeze after **every** install.

## Running things

```powershell
python train_model.py                               # run a script top-to-bottom
uvicorn clinical_trial_matcher.main:app --reload     # dev server; pkg.module:variable
# Ctrl+C to stop — graceful shutdown, runs lifespan shutdown code
```

Browser: `http://127.0.0.1:8000/docs` → Try it out → Execute.
Reloading `/docs` does **not** call an endpoint.

## Tests

```powershell
pytest                          # discovers tests/test_*.py, functions test_*
pytest -v                       # one line per test
pytest tests/test_main.py       # single file
pytest -k health                # only tests whose name contains "health"
```

- Empty `conftest.py` at the repo root puts the root on `sys.path`.
  Without it: `ModuleNotFoundError: No module named 'clinical_trial_matcher'`.
- `TestClient(app)` skips `lifespan`. Use `with TestClient(app) as client:`
  for any test touching startup-loaded state, or you get `KeyError`.

## Docker

```powershell
docker --version                          # asks the CLI only — no daemon needed
docker run hello-world                    # end-to-end check (needs the daemon)
docker build -t trial-matcher .           # -t tag, . = build context
docker run -p 8000:8000 trial-matcher     # -p host:container
docker ps                                 # running containers
docker images                             # images on disk
docker stop <id>                          # stop an orphaned container
docker rmi <image>                        # delete an image
```

- Docker Desktop must be **running**, not just installed — CLI ≠ daemon.
- `transferring dockerfile: NNNB` — if the byte count didn't change, the build
  didn't read your edits. **Save the file first (Ctrl+S).**
- Tag names are exact strings: `trial-matcher` ≠ `trial_matcher`.
- `ENV` / `EXPOSE` / `CMD` create no layer, so they don't appear in the step count.
- Docker reads `.dockerignore`, **not** `.gitignore`.

## PowerShell — files and paths

```powershell
Get-Location                                  # where am I
Get-ChildItem                                 # what's here
Get-ChildItem -Recurse -Filter train_model.py # find a file anywhere below
Get-Content .gitignore                        # print a file
Get-Content .gitignore | Select-String model  # grep a file
mkdir tests                                   # new folder
New-Item tests\.gitkeep -ItemType File        # new empty file
New-Item .env -ItemType File                  # leading dot, no extension
Move-Item clinical_trial_matcher\file.md .    # move; . = here
Test-Path .venv\Scripts\python.exe            # does this exist -> True/False
Remove-Item .venv -Recurse -Force             # delete a folder and contents
```

## Hitting the API from the terminal

```powershell
curl.exe --% -X POST http://127.0.0.1:8000/search -H "Content-Type: application/json" -d "{\"query\":\"diabetes\",\"top_k\":3}"
```

- `curl.exe` not `curl` — bare `curl` is a PowerShell alias for `Invoke-WebRequest`
- `--%` — stop-parsing token; without it PS 5.1 mangles the quotes
- `-X` method · `-H` header · `-d` body
- Easier alternative: write a pytest test instead. No shell quoting at all.

## VS Code

| Shortcut | Does |
|---|---|
| `` Ctrl+` `` | new terminal |
| `` Ctrl+Shift+` `` or `+` in panel | *second* terminal (server in one, git in the other) |
| `Ctrl+Shift+P` | Command Palette |
| `Ctrl+S` | save — `--reload` and `docker build` only see saved files |

Palette commands used: `Python: Select Interpreter` (after moving the repo),
`Developer: Reload Window` (stale interpreter error), `Git: Clone`.

---

## Two checks worth making a habit

**Before any `pip install`** — glance at the prompt: `(.venv)` present, path is the project.
**Before any `git commit`** — run `git status` and read the list.