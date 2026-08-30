"""q155 Mirror Roles -- transfer a learned symmetry from shapes to social roles."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,SHAPE,MIRROR,AGENT,ROLE,DONE,BAD=10,1,12,3,9,6,14,8
LEVELS=[
 {"name":"Mirror Pair","axis":0,"queries":[0,1]}, {"name":"Role Swap","axis":1,"queries":[1,2,3]},
 {"name":"Shape Lesson","axis":2,"queries":[0,3,1,2]}, {"name":"Agent Transfer","axis":3,"queries":[2,0,3,1,2]},
 {"name":"Mirrored Team","axis":1,"queries":[3,1,0,2,3,0]}, {"name":"Mirror Roles","axis":2,"queries":[1,3,0,2,1,0,3]}]
def role(x,axis):return ((axis-x)%4)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=HALL;f[12:31,29:34]=MIRROR
  for i in range(4):f[15+i*4:18+i*4,12:18]=SHAPE;f[15+(g.axis-i)%4*4:18+(g.axis-i)%4*4,45:51]=ROLE
  for i,q in enumerate(g.queries):x=7+i*8;f[38:45,x:x+6]=DONE if i<g.progress else AGENT;f[40:43,x:x+q+2]=ROLE
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q155(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.axis=0;self.queries=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q155",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.axis=s["axis"];self.queries=list(s["queries"]);self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=role(self.queries[self.progress],self.axis):self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.queries):self.next_level()
  self.complete_action()
