"""q627 Canopy Sandbox -- preserve branch evidence through capacity-limited resets."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SHADE,LEFT,RIGHT,STORE,EVIDENCE,MAIN,BAD=7,10,11,6,2,4,9,13,15
LEVELS=[
 {"name":"One Branch","rules":(2,1),"cap":1,"plan":(1,4)},
 {"name":"Reset for Right","rules":(1,3),"cap":1,"plan":(1,3,2,4)},
 {"name":"Compare Together","rules":(2,3),"cap":2,"plan":(1,2,4)},
 {"name":"Evidence Survives","rules":(3,2),"cap":2,"plan":(1,2,3,1,2,4)},
 {"name":"Narrow Orchard","rules":(2,4),"cap":2,"plan":(1,2,3,2,1,4,5)},
 {"name":"Canopy Sandbox","rules":(4,3),"cap":3,"plan":(1,2,1,3,2,1,2,4,5,5)}]
def advance(s,a,x):
 sims,store,evidence,main,chosen=s;sims=list(sims);store=list(store)
 if a in (1,2):
  if len(store)>=x["cap"]:return None
  i=a-1;sims[i]=(sims[i]+x["rules"][i])%7;store.append((i,sims[i]));evidence|=1<<i
 elif a==3:sims=[0,0];store=[]
 elif a==4:
  if chosen is not None or not evidence:return None
  chosen=1 if evidence==2 or (evidence==3 and sims[1]>sims[0]) else 0;main=sims[chosen]
 elif a==5:
  if chosen is None:return None
  main=(main+x["rules"][chosen])%7
 return tuple(sims),tuple(store),evidence,main,chosen
def target(x):
 s=((0,0),(),0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ORCHARD;f[8:29,7:29]=SHADE;f[8:29,35:57]=SHADE
  f[25-g.sims[0]*2:27,10:26]=LEFT;f[25-g.sims[1]*2:27,38:54]=RIGHT
  for i,(side,val) in enumerate(g.store):f[34+i*6:38+i*6,10+side*29:24+side*29]=STORE+val%2
  if g.evidence&1:f[51:55,9:25]=EVIDENCE
  if g.evidence&2:f[51:55,39:55]=EVIDENCE
  f[56:59,8:12+g.main*6]=MAIN
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q627(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q627",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sims=(0,0);self.store=();self.evidence=self.main=0;self.chosen=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.sims,self.store,self.evidence,self.main,self.chosen),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.sims,self.store,self.evidence,self.main,self.chosen=s
  elif a==6:
   if (self.sims,self.store,self.evidence,self.main,self.chosen)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
