"""q026 Controlled Cascade -- choose one seed and barrier for an exact propagation pattern."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,SEED,BARRIER,CASCADE,TARGET,CURSOR,BAD=13,0,9,3,14,10,11,8
LEVELS=[
 {"name":"One Barrier","seeds":[3,5],"barriers":[1,2],"target":1}, {"name":"Exact Spread","seeds":[6,9,12],"barriers":[1,4,8],"target":1},
 {"name":"Two Fronts","seeds":[7,14,28],"barriers":[3,5,9],"target":2}, {"name":"Cascade Shape","seeds":[15,30,45,60],"barriers":[3,12,17],"target":1},
 {"name":"Controlled Reaction","seeds":[31,62,93,124],"barriers":[7,25,49,97],"target":3}, {"name":"Controlled Cascade","seeds":[63,126,189,252],"barriers":[11,37,73,145],"target":2}]
def outcome(seed,barrier):return seed&~barrier
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=FIELD
  for i in range(8):x=8+(i%4)*12;y=14+(i//4)*17;bit=1<<i;f[y:y+10,x:x+10]=CASCADE if g.result&bit else BARRIER if g.barriers[g.bcursor]&bit else SEED if g.seeds[g.scursor]&bit else FIELD
  f[3:6,7+g.scursor*10:15+g.scursor*10]=CURSOR;f[49:53,7+g.bcursor*10:15+g.bcursor*10]=TARGET
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q026(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.seeds=self.barriers=[];self.target=self.scursor=self.bcursor=self.result=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q026",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.seeds=list(s["seeds"]);self.barriers=list(s["barriers"]);self.target=s["target"];self.scursor=self.bcursor=self.result=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.scursor=(self.scursor-1)%len(self.seeds)
  elif a==4:self.scursor=(self.scursor+1)%len(self.seeds)
  elif a==1:self.bcursor=(self.bcursor-1)%len(self.barriers)
  elif a==2:self.bcursor=(self.bcursor+1)%len(self.barriers)
  elif a==5:self.result=outcome(self.seeds[self.scursor],self.barriers[self.bcursor])
  elif a==6:
   if self.scursor==self.target and self.bcursor==self.target%len(self.barriers) and self.result:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
