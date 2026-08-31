"""q537 Canopy Lesson -- transfer a policy without deadlocking a narrow seed store."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SHADE,SEED,STORE,TRACE,CONTEXT,WASTE,BAD=4,7,11,6,2,9,13,10,15
LEVELS=[
 {"name":"One Stored Seed","cap":1,"plan":(1,2,3),"demo":(1,5,2,3)},
 {"name":"Ordered Pair","cap":2,"plan":(1,2,2,3,3),"demo":(1,5,2,2,3,3)},
 {"name":"Season Switch","cap":1,"plan":(1,4,2,3),"demo":(1,5,4,2,3)},
 {"name":"Clear Before Switch","cap":1,"plan":(1,2,3,4,2,3),"demo":(1,5,2,3,4,2,3)},
 {"name":"Capacity Ordering","cap":2,"plan":(1,2,2,3,4,3),"demo":(1,5,2,2,3,4,3)},
 {"name":"Canopy Lesson","cap":2,"plan":(1,4,2,2,3,4,3,2,3),"demo":(1,5,4,2,2,3,4,3,2,3)}]
def advance(s,a,x):
 context,store,glider,shade,seen,waste=s;store=list(store)
 if a==1:seen|=1<<context
 elif a==2:
  if len(store)>=x["cap"]:return None
  store.append(glider);glider=(glider+1)%4
 elif a==3:
  if not store:return None
  seed=store.pop(0);shade=(shade+seed+context+1)%7
 elif a==4:context^=1
 elif a==5:waste+=1
 return context,tuple(store),glider,shade,seen,waste
def target(x):
 s=(0,(),0,0,0,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ORCHARD;f[8:19,8:56]=SHADE
  for i,a in enumerate(g.cfg["demo"]):f[11:16,9+i*5:13+i*5]=(a+5)%16
  f[26:43,8:24]=SEED;f[26:43,40:56]=CONTEXT+g.context
  for i,v in enumerate(g.store):f[48:55,10+i*14:20+i*14]=STORE+v
  f[45:48,8:8+g.shade*6]=TRACE;f[56:59,8:8+g.cfg["cap"]*14]=STORE
  if g.waste:f[21:24,43:56]=WASTE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q537(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q537",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.context=0;self.store=();self.glider=self.shade=self.seen=self.waste=0
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.context,self.store,self.glider,self.shade,self.seen,self.waste),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.context,self.store,self.glider,self.shade,self.seen,self.waste=s
  elif a==6:
   if (self.context,self.store,self.glider,self.shade,self.seen,self.waste)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
