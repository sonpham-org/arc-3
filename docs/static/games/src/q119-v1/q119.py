"""q119 Analog Lesson -- transfer a demonstrated causal graph into moving blocks."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHANNEL,FLOW,BLOCK,EDGE,OBSERVED,RESULT,BAD=4,11,9,12,15,10,14,8
LEVELS=[
 {"name":"Flow to Block","flow":[2,1,4,3],"skin":[1,2,3,4],"demo":[2,4]},
 {"name":"Changed Bodies","flow":[3,1,4,2],"skin":[2,4,1,3],"demo":[1,3,4]},
 {"name":"Same Causal Graph","flow":[4,2,1,3],"skin":[3,1,4,2],"demo":[4,1,2,3]},
 {"name":"Analogical Policy","flow":[2,4,3,1],"skin":[4,2,1,3],"demo":[3,2,4,1,3]},
 {"name":"Surface Mismatch","flow":[3,4,2,1],"skin":[2,3,4,1],"demo":[2,4,1,3,2,1]},
 {"name":"Analog Lesson","flow":[4,1,3,2],"skin":[3,2,1,4],"demo":[1,4,2,3,1,2,4]}]
def transfer(a,flow,skin):return flow[skin.index(a)]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CHANNEL
  for i in range(4):x=8+i*13;f[15:22,x:x+8]=FLOW;f[28:37,x:x+8]=BLOCK;f[23:26,x+2:x+6]=EDGE
  for i in range(len(g.demo)):x=8+i*7;f[46:51,x:x+5]=OBSERVED if i<g.observed else RESULT
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q119(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.flow=self.skin=self.demo=self.result=[];self.observed=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q119",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.flow=list(s["flow"]);self.skin=list(s["skin"]);self.demo=list(s["demo"]);self.result=[];self.observed=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==5:self.observed=min(len(self.demo),self.observed+1)
  elif z in (1,2,3,4):
   if self.observed<len(self.demo):self.failed=True;self.lose()
   else:self.result.append(transfer(z,self.flow,self.skin))
  elif z==6:
   if self.result==self.demo:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
