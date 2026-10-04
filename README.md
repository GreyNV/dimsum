# Dimensional Summoner
A deterministic Python idle-game simulator, with an opt-in character-grid exploration
foundation. Python 3.10+; no runtime dependencies.

From the repository in PowerShell:
```powershell
$env:PYTHONPATH = "src"
python -B -m dimensional_sim.world.cli play --seed 482910
```
WASD moves, Space attacks, Q exits. Use --plain if your terminal lacks color support.

Browser world with the auto-pilot (the character explores and resolves forest
encounters by itself; manual control is a locked skill):
```powershell
python -B -m dimensional_sim.world.cli browser --seed 482910
```
Then open http://127.0.0.1:8765/. Development only: add --unlock-control for WASD.
Each life ends at zero health; dimensional experience persists to the next life.
Save/resume with --save run.json / --load run.json.

Hosted build (runs the same Python in the browser via Pyodide; deploys to Vercel
from GitHub, cloud saves in Supabase): see [hosting](docs/technical/hosting.md).
For a scripted example (no interactive terminal required):
```powershell
python -B -m dimensional_sim.world.cli demo --seed 482910
python -B -m dimensional_sim.cli --seconds 600 --seed 1
python -B -m unittest discover -s tests -v
```

- [World quickstart and extension guide](docs/technical/world-quickstart.md)
- [World scope, contracts and Definition of Done](docs/technical/world-foundation.md)
- [Final implementation report and acceptance evidence](docs/technical/world-final-report.md)
- [Existing idle simulator](docs/technical/simulator.md)
- [Agent instructions](AGENTS.md)

The world uses local validated assets and needs no AI API. The optional offline
provider pipeline creates reusable assets; it never drives live gameplay.
The equipment-review directory remains a separate unfinished UI experiment.
