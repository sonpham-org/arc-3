"""q232 Tide Pact -- probe a hidden social convention before irreversible agreement."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,SHELL,OFFER,RESPONSE,PACT,CURRENT,BAD=2,11,9,14,10,6,15,8
RULES=[[0,1,0],[1,0,1],[0,1,1]]
LEVELS=[
 {"name":"Read the Group","rule":0,"probes":2},{"name":"Recency Current","rule":1,"probes":3},
 {"name":"Reciprocal Tide","rule":2,"probes":3},{"name":"Exclude Unsafe Pact","rule":1,"probes":4},
 {"name":"Irreversible Offer","rule":0,"probes":5},{"name":"Tide Pact","rule":2,"probes":6}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=BASIN
  for i in range(3):x=9+i*17;f[16:30,x:x+11]=SHELL;f[34:39,x:x+11]=RESPONSE if g.last_response==RULES[g.rule][i] and g.history else OFFER
  f[45:49,8:8+len(g.history)*7]=CURRENT;f[3:6,8:30]=PACT if g.stage else BASIN
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q232(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rule=self.probes=self.stage=self.last_response=0;self.history=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q232",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.rule=s["rule"];self.probes=s["probes"];self.stage=self.last_response=0;self.history=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3) and self.stage==0:self.history.append(z);self.last_response=RULES[self.rule][z-1]
  elif z==5 and self.stage==0:
   if len(self.history)<self.probes:self.failed=True;self.lose()
   else:self.stage=1
  elif z in (1,2,3) and self.stage==1:
   if z==self.rule+1:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
