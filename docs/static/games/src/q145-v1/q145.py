"""q145 Parallel Sandboxes -- compare interventions before applying one to an irreversible system."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,SANDBOX,MAIN,TESTED,TARGET,CURSOR,BAD=13,1,10,3,14,9,11,8
LEVELS=[
 {"name":"Two Tests","ops":[1,2],"target":1}, {"name":"Different Outcomes","ops":[2,3,1],"target":2},
 {"name":"Compare Policies","ops":[1,3,2],"target":0}, {"name":"Irreversible Main","ops":[3,1,4,2],"target":3},
 {"name":"Parallel Evidence","ops":[2,4,1,3],"target":1}, {"name":"Parallel Sandboxes","ops":[4,2,3,1,2],"target":2}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=LAB;f[13:27,7:27]=SANDBOX;f[13:27,37:57]=SANDBOX;f[35:49,20:44]=MAIN
  for i,o in enumerate(g.ops):f[3:6,7+i*9:14+i*9]=CURSOR if i==g.cursor else TARGET if i==g.target else LAB
  if 0 in g.tested:f[18:22,12:22]=TESTED
  if 1 in g.tested:f[18:22,42:52]=TESTED
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q145(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.ops=[];self.target=self.cursor=0;self.tested=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q145",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.ops=list(s["ops"]);self.target=s["target"];self.cursor=0;self.tested=set();self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.ops)
  elif a==4:self.cursor=(self.cursor+1)%len(self.ops)
  elif a in (1,2):self.tested.add(a-1)
  elif a==6:
   if self.cursor==self.target and self.tested=={0,1}:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
