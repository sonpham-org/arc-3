"""q070 Triangulation -- combine three relative-distance sensors to locate a hidden target."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,SENSOR,TARGET,CANDIDATE,REPORT,CURSOR,BAD=14,1,12,9,10,15,11,8
LEVELS=[
 {"name":"Two Baselines","size":4,"target":(2,1)}, {"name":"Third Sensor","size":5,"target":(3,2)},
 {"name":"Asymmetric Distances","size":5,"target":(1,3)}, {"name":"Interior Point","size":6,"target":(4,2)},
 {"name":"Moving Fix","size":6,"target":(2,4)}, {"name":"Triangulation","size":7,"target":(5,3)}]
def anchors(size):return [(0,0),(size-1,0),(0,size-1)]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:58,7:57]=FIELD;s=7
  for y in range(g.size):
   for x in range(g.size):f[10+y*s:15+y*s,9+x*s:14+x*s]=CANDIDATE if (x,y)==g.cursor else FIELD
  for i,(x,y) in enumerate(anchors(g.size)):f[10+y*s:16+y*s,9+x*s:15+x*s]=SENSOR;f[3:6,8+i*16:8+i*16+(g.reports[i] if g.probed else 1)*2]=REPORT
  if g.probed and g.cursor==g.target:x,y=g.target;f[10+y*s:15+y*s,9+x*s:14+x*s]=TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q070(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.size=0;self.target=self.cursor=(0,0);self.reports=(0,0,0);self.probed=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q070",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.size=s["size"];self.target=tuple(s["target"]);self.cursor=(0,0);self.reports=tuple(abs(self.target[0]-x)+abs(self.target[1]-y) for x,y in anchors(self.size));self.probed=self.failed=False
 def step(self):
  z=self.action.id.value;x,y=self.cursor
  if z==0:self.complete_action();return
  if z==1:y=max(0,y-1)
  elif z==2:y=min(self.size-1,y+1)
  elif z==3:x=max(0,x-1)
  elif z==4:x=min(self.size-1,x+1)
  elif z==5:self.probed=True
  elif z==6:
   if self.probed and self.cursor==self.target:self.next_level()
   else:self.failed=True;self.lose()
  if z in (1,2,3,4):self.cursor=(x,y)
  self.complete_action()
