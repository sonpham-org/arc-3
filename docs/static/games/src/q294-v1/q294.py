"""q294 Honeycomb Ledger -- conserve nectar while coordinating local and outer clocks."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,NECTAR,CELL,CURSOR,CLOCK,TARGET,BAD=6,3,14,9,15,10,12,8
LEVELS=[
 {"name":"Preserve Nectar","start":[2,0,1],"target":[1,1,1],"cycle":2,"outer":2,"phase":1},
 {"name":"Local Cycle","start":[3,0,1],"target":[1,2,1],"cycle":3,"outer":2,"phase":0},
 {"name":"Outer Ledger","start":[1,3,0],"target":[2,1,1],"cycle":3,"outer":3,"phase":2},
 {"name":"Coupled Clocks","start":[4,0,1],"target":[1,2,2],"cycle":4,"outer":3,"phase":1},
 {"name":"Global Bookkeeping","start":[2,3,1],"target":[3,1,2],"cycle":4,"outer":4,"phase":3},
 {"name":"Honeycomb Ledger","start":[5,1,1],"target":[2,3,2],"cycle":5,"outer":4,"phase":2}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=HIVE
  for i,v in enumerate(g.values):x=9+i*17;f[18:42,x:x+12]=CELL;f[37-v*4:39,x+3:x+9]=NECTAR;f[45:49,x:x+12]=CURSOR if i==g.cursor else HIVE
  f[3:6,8:8+g.outer_phase*10]=CLOCK
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q294(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=[];self.cursor=self.tick_count=self.cycle=self.outer_mod=self.outer_phase=self.target_phase=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q294",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.values=list(s["start"]);self.target=list(s["target"]);self.cycle=s["cycle"];self.outer_mod=s["outer"];self.target_phase=s["phase"];self.cursor=self.tick_count=self.outer_phase=0;self.failed=False
 def clock(self):
  self.tick_count+=1
  if self.tick_count==self.cycle:self.tick_count=0;self.outer_phase=(self.outer_phase+1)%self.outer_mod
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  nxt=(self.cursor+1)%3
  if z==1 and self.values[self.cursor]>0:self.values[self.cursor]-=1;self.values[nxt]+=1
  elif z==2 and self.values[nxt]>0:self.values[nxt]-=1;self.values[self.cursor]+=1
  elif z==3:self.cursor=nxt
  elif z not in (5,6):self.failed=True;self.lose()
  if z in (1,2,3,5):self.clock()
  elif z==6:
   if self.values==self.target and self.outer_phase==self.target_phase:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
