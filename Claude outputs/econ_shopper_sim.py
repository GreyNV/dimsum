import sys, json, time
sys.path.insert(0, "/tmp/dimsum/src")
from dimensional_sim.world.autopilot import Expedition
from dimensional_sim.world.runtime import Exploration
from dimensional_sim.world.web import new_world
from dimensional_sim.world import economy

def run(seed, minutes):
    e = Expedition(Exploration(new_world(seed), "forest"))
    lives=[]; buys=[]; recorded=0; total=minutes*60000
    while e.total_ms < total:
        e.advance(1000)
        if e.anchor_ms is not None and recorded != e.life:
            recorded = e.life
            ash_before = e.ash; bl_before=e.blessing
            offers = e.anchor_offers()
            bought=[]
            while True:
                rows=[r for r in e.anchor_offers() if r["available"]]
                u=sorted((r for r in rows if r["kind"] in ("unlock","bind","keep")), key=lambda r:(r["cost"],r["id"]))
                b=[r for r in rows if r["kind"]=="boon"]
                c=(u or b or [None])[0]
                if c is None: break
                e.anchor_action({"type":c["kind"],"id":c["id"]}); bought.append((c["kind"],c["id"],c["cost"],c["currency"]))
            lives.append({"life":e.life,"min":round(e.total_ms/60000,1),"cause":e.cause,"depth":e.depth,
               "ash":ash_before,"bless":bl_before,"bought":bought,
               "offers":[(r["kind"],r["id"],r["cost"]) for r in offers],
               "prayers":e.stats.get("prayers"),"unlocked":sorted(e.unlocked),"life_recipes":sorted(getattr(e,"life_recipes",())),
               "recipes":sorted(e.recipes),"buildings":sorted(getattr(e,"buildings",())),"bound":sorted(e.bound_buildings)})
            e.anchor_action({"type":"begin_life"})
    return {"seed":seed,"lives":lives,"final_ash":e.ash,"final_bless":e.blessing,"converted":dict(e.converted)}

seed=int(sys.argv[1]); m=int(sys.argv[2])
t=time.time(); r=run(seed,m); r["secs"]=round(time.time()-t)
json.dump(r, open(f"/tmp/claude-0/sims/s{seed}_{m}.json","w"))
print(seed, r["secs"], r["final_ash"], r["final_bless"])
