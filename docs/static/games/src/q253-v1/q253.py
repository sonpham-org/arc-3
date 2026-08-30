"""q253 Impeller Pact -- infer a convention and stop once extra samples are wasteful."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TURBINE,BLADE,OFFER,RESPONSE,COST,CANDIDATE,BAD=2,11,9,14,10,15,6,8
RULES=[[1,0,1],[0,1,1],[1,1,0]]
LEVELS=[
 {"name":"Three Offers","rule":0},{"name":"Recency Pact","rule":1},{"name":"Reciprocal Wake","rule":2},
 {"name":"Stop Sampling","rule":1},{"name":"Costly Certainty","rule":0},{"name":"Impeller Pact","rule":2}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=TURBINE
  for i in range(3):x=9+i*17;f[16:30,x:x+11]=BLADE;f[34:39,x:x+11]=RESPONSE if g.responses and g.responses[-1] else OFFER
  f[43:47,8:8+g.cost*9]=COST;f[49:53,8+g.candidate*17:20+g.candidate*17]=CANDIDATE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q253(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rule=self.cost=self.candidate=0;self.responses=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q253",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):self.rule=LEVELS[self.level_index]["rule"];self.cost=self.candidate=0;self.responses=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):self.responses.append(RULES[self.rule][z-1]);self.cost+=1
  elif z==5:self.candidate=(self.candidate+1)%3
  elif z==6:
   if len(self.responses)==3 and self.candidate==self.rule:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
