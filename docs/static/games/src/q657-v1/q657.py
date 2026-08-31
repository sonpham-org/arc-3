"""q657 Canopy Analogy -- preserve a relation through seasonal transforms and a narrow store."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SHADE,SEED,STORE,SEASON,TARGET,PROOF,BAD=2,7,11,6,4,9,13,10,15
LEVELS=[
 {"name":"Store and Transfer","cap":1,"plan":(1,2,4,5)},{"name":"Seasonal Transfer","cap":1,"plan":(1,2,3,4,5)},
 {"name":"Ordered Pair","cap":2,"plan":(1,2,1,2,4,5)},{"name":"Clear Before Season","cap":1,"plan":(1,2,4,3,1,2,4,5)},
 {"name":"Capacity Analogy","cap":2,"plan":(1,2,3,1,2,4,4,5)},{"name":"Canopy Analogy","cap":2,"plan":(1,2,1,2,3,4,1,2,4,5)}]
def advance(s,a,x):
 source,store,season,target_relation,proof=s;store=list(store)
 if a==1:source=(source+1)%4
 elif a==2:
  if len(store)>=x["cap"]:return None
  store.append(source)
 elif a==3:season=(season+1)%4
 elif a==4:
  if not store:return None
  target_relation=(store.pop(0)+season)%4
 elif a==5:
  if target_relation is None:return None
  proof=(source,tuple(store),season,target_relation)
 return source,tuple(store),season,target_relation,proof
def target(x):
 s=(0,(),0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ORCHARD
  for i in range(4):f[9+i*9:15+i*9,8:25]=SEED if i==g.source else SHADE
  for i in range(4):f[9+i*9:15+i*9,39:56]=TARGET if i==g.target_relation else SHADE+1
  for i,v in enumerate(g.store):f[48:54,9+i*14:19+i*14]=STORE+v
  f[55:58,8:8+g.season*11]=SEASON
  if g.proof:f[44:58,57:60]=PROOF
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q657(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q657",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=0;self.store=();self.season=0;self.target_relation=self.proof=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.source,self.store,self.season,self.target_relation,self.proof),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.source,self.store,self.season,self.target_relation,self.proof=s
  elif a==6:
   if (self.source,self.store,self.season,self.target_relation,self.proof)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
