"""q114 Noisy Example -- discard one visible action that caused no state change."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PANEL,EFFECT,NOISE,PLAYER,DONE,BAD=2,1,14,8,9,10,13
LEVELS=[
 {"name":"Accident","demo":[(1,1),(4,0),(2,1)]}, {"name":"Middle Slip","demo":[(3,1),(1,1),(2,0),(4,1)]},
 {"name":"Repeated Gesture","demo":[(1,1),(1,0),(1,1),(3,1)]}, {"name":"Long Example","demo":[(4,1),(2,1),(3,0),(1,1),(4,1)]},
 {"name":"Late Accident","demo":[(2,1),(3,1),(4,1),(1,1),(2,0),(4,1)]}, {"name":"Noisy Example","demo":[(1,1),(4,1),(2,0),(3,1),(1,1),(2,1),(4,1)]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:55,4:60]=PANEL
  for i,(a,e) in enumerate(g.demo):x=7+i*7;f[15:22,x:x+5]=EFFECT if e else NOISE;f[17:20,x:x+a]=PLAYER
  for i in range(len(g.policy)):f[38:45,8+i*7:13+i*7]=DONE if i<g.progress else PLAYER
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q114(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.demo=[];self.policy=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q114",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):self.demo=list(map(tuple,LEVELS[self.level_index]["demo"]));self.policy=[a for a,e in self.demo if e];self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=self.policy[self.progress]:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.policy):self.next_level()
  self.complete_action()
