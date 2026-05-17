# Building LightBurn Bridge for Windows

PyInstaller produces **native** binaries — you cannot cross-compile from
macOS or Linux to a Windows `.exe`. Three options below. Pick whichever
matches your situation.

## Option A — Build on your Windows laptop directly (fastest)

**Prerequisites:** Windows 10 or 11.

### 1. Install Python 3.12

Download the installer from <https://www.python.org/downloads/windows/>.
**During install, check "Add python.exe to PATH"** so `python` and `pip`
work from any terminal.

Verify in **PowerShell**:

```powershell
python --version
# Python 3.12.x
```

### 2. Install `uv`

Open PowerShell and run:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart PowerShell so `uv` is on PATH. Verify:

```powershell
uv --version
# uv 0.10.x or later
```

### 3. Get the source onto the Windows laptop

Easiest paths (pick one):

- **Push to GitHub from your Mac, clone on Windows**

  ```powershell
  git clone https://github.com/<you>/lightburn-tool.git
  cd lightburn-tool
  ```

- **Copy via USB / OneDrive / Dropbox** — copy the entire `lightburn-tool/`
  folder. Make sure the `templates/` and `tests/fixtures/` directories
  come along.

### 4. Install deps and build

In the project directory, in PowerShell:

```powershell
uv sync --extra ui --dev
uv run pyinstaller packaging/lbb.spec --clean --noconfirm
```

First run takes 3–5 minutes (downloads PySide6, pypdfium2, etc.). Subsequent
builds are ~30 seconds.

### 5. Run the app

```powershell
.\dist\"LightBurn Bridge"\"LightBurn Bridge.exe"
```

You should see the same dark-themed window you saw on Mac. Drop a PDF
named with a registered SKU, click Send, watch LightBurn open the file.

### 6. (Optional) Seed a demo SKU on this machine

```powershell
uv run python scripts/seed_demo.py
```

This populates `%USERPROFILE%\.lightburn-bridge\profiles.sqlite` with the
LB-WALLET-LEATHER-S profile, so dropping `LB-WALLET-LEATHER-S__showcase.pdf`
on the app works immediately.

---

## Option B — GitHub Actions builds for you (cleanest for repeat builds)

The CI workflow already builds Win/Mac/Linux on every push. After Task #42
(this commit), it also **uploads the built artifact** for each OS.

### 1. Push to GitHub (private repo is fine)

```bash
# On your Mac, from the repo root:
gh repo create lightburn-tool --private --source=. --remote=origin --push
# or with plain git:
git remote add origin git@github.com:<you>/lightburn-tool.git
git push -u origin main
```

### 2. Watch the build

Go to GitHub → your repo → **Actions** tab. The `CI` workflow runs three
jobs (test + build per OS). Wait ~10 minutes.

### 3. Download the Windows build

From the workflow run page, scroll to **Artifacts**. Download:

```
lightburn-bridge-windows-latest.zip
```

Unzip it. Inside: `LightBurn Bridge/LightBurn Bridge.exe`. Copy the folder
to your Windows laptop and run the `.exe`.

### 4. Rebuild on demand

Push a commit (any change) and the build re-runs. Or use the **Run workflow**
button on the Actions tab for a manual trigger without a commit.

---

## Option C — Windows VM on your Mac (most flexibility)

Useful if you want to keep development on the Mac but iterate on Windows
builds without pushing. Apple Silicon Macs: Parallels Desktop or UTM run
Windows 11 ARM. Intel Macs: VMware Fusion or VirtualBox.

Once Windows is installed in the VM, follow **Option A** inside the VM.

This is the slowest setup but gives the tightest local iteration loop —
useful if you hit Windows-specific bugs that need quick repro.

---

## Troubleshooting

### "uv: command not found" after installing

Restart PowerShell. The installer adds uv to `$env:Path` but existing
terminals don't pick it up until restart.

### PyInstaller can't find Qt plugins on Windows

This usually means `--extra ui` was missed. Re-run:

```powershell
uv sync --extra ui --dev
```

### Antivirus flags `LightBurn Bridge.exe`

Unsigned PyInstaller `.exe` files trip Windows Defender / SmartScreen on
first run. The fix is code-signing with an Authenticode certificate
(~$50–$400/year). For internal demos, click "More info → Run anyway."

For production distribution, see the open Task on code-signing.

### "LightBurn — Not connected" stays red on Windows

The status pill checks the running LightBurn process via `tasklist`. Make
sure LightBurn is actually open. The lookup is case-sensitive; if your
LightBurn executable is named differently (e.g. `LightBurnPro.exe`), pass
a custom `app_name` to `LightBurnShellAdapter` in your code or open an
issue.

### LightBurn doesn't open when I click Send

`cmd /c start "" file.lbrn2` relies on `.lbrn2` being associated with
LightBurn. In Windows: right-click any `.lbrn2` → Open With → Choose
another app → check "Always use this app" → pick LightBurn.

After that, our app's Send will work.
