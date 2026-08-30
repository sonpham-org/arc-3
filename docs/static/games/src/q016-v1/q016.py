"""q016 Blind Guide -- an autonomous guide expresses hazard-safe directions through movement."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CORRIDOR,BODY,GUIDE,HAZARD,DONE,BAD=7,1,9,14,8,10,13
LEVELS=[
 {"name":"Follow Motion","route":[4,4]}, {"name":"Turn Signal","route":[1,4,2]},
 {"name":"Hazard Bend","route":[3,1,4,2]}, {"name":"Guide Memory","route":[4,1,3,2,4]},
 {"name":"Long Safe Path","route":[2,4,1,3,2,4]}, {"name":"Blind Guide","route":[1,4,2,3,1,4,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=CORRIDOR
  for i,a in enumerate(g.route):x=7+i*7;f[18:26,x:x+5]=GUIDE;f[19:23,x:x+a]=DONE if i<g.progress else GUIDE;f[38:46,x:x+5]=BODY if i>=g.progress else DONE
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q016(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q016",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):self.route=list(LEVELS[self.level_index]["route"]);self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=self.route[self.progress]:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.route):self.next_level()
  self.complete_action()
