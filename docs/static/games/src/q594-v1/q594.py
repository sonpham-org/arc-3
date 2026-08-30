"""q594 Honeycomb Grammar -- relay-transformed grouped commands run on two clocks."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,NECTAR,GROUP,RELATION,RELAY,CLOCK,BAD=4,11,9,14,12,15,6,8
LEVELS=[
 {"name":"Local Clock","commands":[[1,3]],"shift":0,"cycle":2},{"name":"Outer Clock","commands":[[2,4],[1,3]],"shift":1,"cycle":3},
 {"name":"Grouped Relation","commands":[[4,2],[3,1],[1,4]],"shift":2,"cycle":3},{"name":"Relay Phase","commands":[[3,4],[1,2],[4,1],[2,3]],"shift":1,"cycle":4},
 {"name":"Nested Timing","commands":[[2,1],[4,3],[1,4],[3,2],[2,4]],"shift":3,"cycle":4},{"name":"Honeycomb Grammar","commands":[[4,1],[2,3],[3,4],[1,2],[4,2],[2,1]],"shift":2,"cycle":5}]
def enc(a,shift,outer):return((a-1+shift+outer)%4)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=HIVE;f[15:29,8:22]=NECTAR;f[15:29,42:56]=NECTAR;f[32:37,8:56]=RELAY
  for i in range(len(g.commands)):x=8+i*7;f[42:47,x:x+5]=CLOCK if i<g.progress else GROUP;f[49:53,x:x+5]=RELATION
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q594(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.commands=self.buffer=[];self.shift=self.cycle=self.local=self.outer=self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q594",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.commands=[list(x) for x in s["commands"]];self.shift=s["shift"];self.cycle=s["cycle"];self.buffer=[];self.local=self.outer=self.progress=0;self.failed=False
 def tick(self):
  self.local+=1
  if self.local==self.cycle:self.local=0;self.outer=(self.outer+1)%4
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4):self.buffer.append(enc(z,self.shift,self.outer));self.tick()
  elif z==5:
   if self.buffer!=self.commands[self.progress]:self.failed=True;self.lose()
   else:
    self.progress+=1;self.buffer=[];self.tick()
    if self.progress==len(self.commands):self.next_level()
  self.complete_action()
