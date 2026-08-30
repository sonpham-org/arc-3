"""q243 Murmuration Pact -- identify a social convention despite one misleading response."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AVIARY,FLOCK,OFFER,RESPONSE,PARITY,PACT,BAD=7,14,9,12,10,15,6,8
RULES=[[1,0,1],[0,1,1],[1,1,0]]
LEVELS=[
 {"name":"Redundant Signal","rule":0,"probes":3,"lie":1},{"name":"Find the Mislead","rule":1,"probes":3,"lie":2},
 {"name":"Convention Parity","rule":2,"probes":4,"lie":0},{"name":"Reciprocal Flock","rule":1,"probes":5,"lie":3},
 {"name":"Exclude Unsafe Pact","rule":0,"probes":5,"lie":2},{"name":"Murmuration Pact","rule":2,"probes":6,"lie":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=AVIARY
  for i in range(3):x=9+i*17;f[16:30,x:x+11]=FLOCK;f[34:39,x:x+11]=RESPONSE if g.observed and g.observed[-1] else OFFER
  f[43:48,8:24]=PARITY if g.claim else AVIARY;f[49:53,34:56]=PACT if g.stage else AVIARY
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q243(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rule=self.probes=self.lie=self.claim=self.stage=0;self.offers=self.observed=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q243",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.rule=s["rule"];self.probes=s["probes"];self.lie=s["lie"];self.claim=self.stage=0;self.offers=[];self.observed=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3) and self.stage==0:
   true=RULES[self.rule][z-1];self.offers.append(z);self.observed.append(1-true if len(self.offers)-1==self.lie else true)
  elif z==4 and self.stage==0:self.claim=1-self.claim
  elif z==5 and self.stage==0:
   parity=sum(RULES[self.rule][a-1] for a in self.offers)%2
   if len(self.offers)>=self.probes and self.claim==parity:self.stage=1
   else:self.failed=True;self.lose()
  elif z in (1,2,3) and self.stage==1:
   if z==self.rule+1:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
