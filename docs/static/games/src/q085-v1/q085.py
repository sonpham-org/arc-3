"""q085 Identity Trail -- footprints preserve identity after bodies become identical."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,TRAIL,BODY,TARGET,CURSOR,DONE,BAD=1,10,3,9,14,12,6,8
LEVELS=[
 {"name":"One Trail","trails":[0,1],"query":[0]}, {"name":"Crossing Tracks","trails":[1,0,2],"query":[2,0]},
 {"name":"Identical Bodies","trails":[2,0,1,2],"query":[1,2,0]}, {"name":"Long Footprints","trails":[1,3,0,2,1],"query":[3,1,2]},
 {"name":"Trail Assignment","trails":[3,0,2,1,3,2],"query":[0,3,2,1]}, {"name":"Identity Trail","trails":[2,0,3,1,2,3,0],"query":[3,0,2,1,3]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=FIELD
  for i,t in enumerate(g.trails):x=7+i*7;f[15+t*4:18+t*4,x:x+5]=TRAIL;f[34:41,x:x+5]=BODY;f[44:48,x:x+5]=CURSOR if i==g.cursor else FIELD
  for i,q in enumerate(g.query):f[3:6,7+i*9:14+i*9]=DONE if i<g.progress else TARGET+q%2
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q085(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.trails=self.query=[];self.progress=self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q085",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.trails=list(s["trails"]);self.query=list(s["query"]);self.progress=self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.trails)
  elif a==4:self.cursor=(self.cursor+1)%len(self.trails)
  elif a==6:
   if self.trails[self.cursor]==self.query[self.progress]:
    self.progress+=1
    if self.progress==len(self.query):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
