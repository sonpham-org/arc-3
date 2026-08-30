"""q149 Model Tokens -- eliminate incompatible world models before commitment."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TABLE,MODEL,ALIVE,CUT,TARGET,COMMIT,BAD=1,13,9,10,15,14,6,8
LEVELS=[
 {"name":"Eliminate One Model","n":3,"target":1,"cuts":[[0,2],[0],[2],[]]},
 {"name":"Two Observations","n":4,"target":2,"cuts":[[0,1],[3],[0,3],[1]]},
 {"name":"Competing Explanations","n":5,"target":3,"cuts":[[0,1],[2,4],[0,2],[1,4]]},
 {"name":"Observation Choice","n":6,"target":1,"cuts":[[0,2,4],[3,5],[0,3],[2,5]]},
 {"name":"Model Intersection","n":7,"target":5,"cuts":[[0,1],[2,3],[4,6],[0,2,4]]},
 {"name":"Model Tokens","n":8,"target":6,"cuts":[[0,1,2],[3,4],[5,7],[0,3,5]]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=TABLE
  for i in range(g.n):x=7+i*(50//g.n);f[20:34,x:x+6]=ALIVE if g.alive&(1<<i) else MODEL;f[38:43,x:x+6]=TARGET if i==g.target else TABLE
  f[3:6,8:8+g.used*8]=CUT
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q149(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.n=self.target=self.alive=self.used=0;self.masks=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q149",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.n=s["n"];self.target=s["target"];self.alive=(1<<self.n)-1;self.used=0;self.failed=False;self.masks=[self.alive-sum(1<<i for i in cut) for cut in s["cuts"]]
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4):self.alive&=self.masks[z-1];self.used+=1
  elif z==5:
   if self.alive==(1<<self.target):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
