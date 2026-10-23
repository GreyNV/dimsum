"""Architecture fitness tests: the AGENTS.md invariants, checked on the source itself.

Each test reads code (Python AST, or JS import and call text) rather than running it, so a rule
breaks the build the moment someone breaks it, not when a run happens to hit the bad path.
Where old code predates a rule, the exceptions are listed by name with the reason; the lists
are ratchets: a new violation fails, and so does an exception that no longer exists, so the
list only ever shrinks.
"""
import ast
import pathlib
import re
import unittest

from dimensional_sim.world import catalog

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src" / "dimensional_sim"
WORLD = ROOT / "world"
BROWSER = WORLD / "browser"
IDLE_SIM = {"dimensional_sim.core", "dimensional_sim.content", "dimensional_sim.balance",
            "dimensional_sim.persistence", "dimensional_sim.summoning", "dimensional_sim.equipment",
            "dimensional_sim.cli"}
# Adapters own real time (frame pacing, HTTP polling); the simulation never reads a clock.
CLOCK_ADAPTERS = {"terminal.py", "browser_server.py"}
# Pure layers: no providers (pipeline), no I/O.
PURE_LAYERS = {"runtime", "renderer", "animation"}
NETWORK_MODULES = {"socket", "http", "urllib", "requests", "subprocess", "asyncio"}
# Client art: these modules draw catalog art keys, and naming the key is how art is looked up.
CLIENT_ART = {"art.js", "ascii_art.js", "actors.js", "combat_art.js", "nature_art.js", "natural_ground.js",
              "painted.js", "painted_props.js", "place_art.js", "player_art.js", "sprites.js"}
# Location art never draws the player (AGENTS.md: player graphics never belong in locations).
LOCATION_ART = {"art.js", "nature_art.js", "natural_ground.js", "painted_props.js", "place_art.js", "minimap.js"}

# Catalog ids named in engine code before the rule was enforced, with why each stays.
# (file relative to world/, id) -> reason
NAMED_ID_EXCEPTIONS = {
    ("actions.py", "dark_forest"): "Context default biome for callers that predate biomes",
    ("encounters.py", "dark_forest"): "frozen v1 spot pool, pinned by ENCOUNTER_VERSION",
    ("generation.py", "dark_forest"): "frozen blocker cell colors of pinned generator versions",
    ("models.py", "dark_forest"): "DimensionSpec default biome, pinned in world saves",
    ("open_terrain.py", "dark_forest"): "frozen open-terrain composition (generator v3-v8 pinned)",
    ("open_terrain.py", "ash_plain"): "frozen open-terrain composition (generator v3-v8 pinned)",
    ("autopilot/saves.py", "walking_staff"): "schema migration of a historic save",
    ("autopilot/saves.py", "snares"): "schema migration of a historic save",
    ("autopilot/saves.py", "hide_wrap"): "schema migration of a historic save",
    ("web.py", "dark_forest"): "the hosted build's world spec (an adapter choosing content)",
}


def python_files(base=WORLD):
    return sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)


def module_name(path):
    parts = path.relative_to(ROOT.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imports_of(path, known):
    """Modules (from `known`) imported anywhere in `path`, resolving relative imports."""
    name = module_name(path)
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[:len(package.split(".")) - (node.level - 1)]
                target = ".".join(base + ([node.module] if node.module else []))
            else:
                target = node.module or ""
            candidates = [target] + [f"{target}.{alias.name}" for alias in node.names]
        elif isinstance(node, ast.Import):
            candidates = [alias.name for alias in node.names]
        else:
            continue
        for candidate in candidates:
            while candidate and candidate not in known:
                candidate = candidate.rpartition(".")[0]
            if candidate and candidate != name:
                found.add(candidate)
    return found


def raw_imports(path):
    """Top-level names of every module imported in `path` (absolute imports only)."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names.add(node.module.split(".")[0])
    return names


def import_graph(base):
    files = {module_name(p): p for p in python_files(base)}
    everything = {module_name(p) for p in python_files(ROOT)}
    return {name: imports_of(path, everything) for name, path in files.items()}


def cycles(graph):
    """Strongly connected components with more than one module (Tarjan, iterative)."""
    index, low, stack, on_stack, result, counter = {}, {}, [], set(), [], [0]
    for root in sorted(graph):
        if root in index:
            continue
        work = [(root, iter(sorted(graph[root] & graph.keys())))]
        index[root] = low[root] = counter[0]; counter[0] += 1
        stack.append(root); on_stack.add(root)
        while work:
            node, edges = work[-1]
            for nxt in edges:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]; counter[0] += 1
                    stack.append(nxt); on_stack.add(nxt)
                    work.append((nxt, iter(sorted(graph[nxt] & graph.keys()))))
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[node])
                if low[node] == index[node]:
                    component = []
                    while True:
                        member = stack.pop(); on_stack.discard(member); component.append(member)
                        if member == node:
                            break
                    if len(component) > 1:
                        result.append(sorted(component))
    return result


def js_imports(path):
    return set(re.findall(r"""from\s+['"]\./([\w.]+)['"]""", path.read_text(encoding="utf-8")))


class LayeringTests(unittest.TestCase):
    def test_the_world_package_has_no_import_cycles(self):
        self.assertEqual(cycles(import_graph(WORLD)), [])

    def test_the_world_never_imports_the_phase_one_idle_sim(self):
        for name, targets in import_graph(WORLD).items():
            self.assertFalse(targets & IDLE_SIM, f"{name} imports the idle sim: {targets & IDLE_SIM}")

    def test_pure_layers_never_reach_providers_or_the_network(self):
        graph = import_graph(WORLD)
        for layer in PURE_LAYERS:
            name = f"dimensional_sim.world.{layer}"
            self.assertNotIn("dimensional_sim.world.pipeline", graph[name], name)
            self.assertFalse(raw_imports(WORLD / f"{layer}.py") & NETWORK_MODULES, name)

    def test_autopilot_mixins_never_import_the_expedition_that_composes_them(self):
        for path in python_files(WORLD / "autopilot"):
            if path.name in ("expedition.py", "__init__.py"):
                continue
            self.assertNotIn("dimensional_sim.world.autopilot.expedition",
                             imports_of(path, {module_name(p) for p in python_files(ROOT)}), path.name)

    def test_only_the_transport_module_talks_to_the_network_in_the_client(self):
        for path in sorted(BROWSER.glob("*.js")):
            if path.name == "transport.js":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\bfetch\(|XMLHttpRequest|WebSocket|EventSource", text), path.name)

    def test_location_art_never_draws_the_player(self):
        for name in LOCATION_ART:
            self.assertNotIn("player_art.js", js_imports(BROWSER / name), name)


class DeterminismTests(unittest.TestCase):
    def test_the_simulation_reads_no_clock_no_hash_and_no_shared_rng(self):
        for path in python_files():
            if path.name in CLOCK_ADAPTERS:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            rel = path.relative_to(WORLD)
            self.assertFalse(raw_imports(path) & {"time", "datetime", "secrets", "uuid"}, f"{rel} reads a clock")
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "hash":
                    self.fail(f"{rel}:{node.lineno} calls hash(), which is salted per process")
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                        and node.value.id == "random" and node.attr != "Random":
                    self.fail(f"{rel}:{node.lineno} uses the shared random.{node.attr}; seed a random.Random")
                if isinstance(node, ast.ImportFrom) and node.module == "random" \
                        and any(alias.name != "Random" for alias in node.names):
                    self.fail(f"{rel}:{node.lineno} imports shared RNG functions")


def catalog_ids():
    ids = {}
    for kind, table in (("enemy", catalog.ENEMIES), ("item", catalog.ITEMS), ("unlock", catalog.UNLOCKS),
                        ("biome", catalog.BIOMES)):
        for key in table:
            ids.setdefault(key, kind)
    return ids


def named_ids_in_python(ids):
    """(file, id) for every string literal equal to a catalog id outside catalog data and docstrings."""
    found = set()
    for path in python_files():
        if path.name in ("catalog.py", "tuning.py", "pipeline.py", "assets.py", "cli.py", "simulate.py"):
            continue   # content, balance numbers, the offline provider and the developer CLIs
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                      and ast.get_docstring(node, clean=False) is not None}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in ids \
                    and id(node) not in docstrings:
                found.add((path.relative_to(WORLD).as_posix(), node.value))
    return found


class ContentRuleTests(unittest.TestCase):
    def test_engine_code_names_no_enemy_item_unlock_or_biome(self):
        found = named_ids_in_python(catalog_ids())
        new = sorted(found - set(NAMED_ID_EXCEPTIONS))
        self.assertEqual(new, [], "name content through a catalog field or Effect stat instead")
        gone = sorted(set(NAMED_ID_EXCEPTIONS) - found)
        self.assertEqual(gone, [], "fixed: remove these from NAMED_ID_EXCEPTIONS")

    def test_client_logic_names_no_enemy_item_unlock_or_biome(self):
        ids = catalog_ids()
        for path in sorted(BROWSER.glob("*.js")):
            if path.name in CLIENT_ART:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
                if line.strip().startswith("//"):
                    continue
                for match in re.finditer(r"""(['"])([a-z_][a-z0-9_]*)\1""", line):
                    self.assertNotIn(match.group(2), ids, f"{path.name}:{number} names {match.group(2)!r}")


if __name__ == "__main__":
    unittest.main()
