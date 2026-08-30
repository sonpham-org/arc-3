"""q188 Future Walls -- an early route becomes the obstacle pattern of a later maze."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,EARLY,WALL,FUTURE,GOAL,DONE,BAD=6,1,9,8,12,14,10,15
LEVELS=[
 {"name":"Path Becomes Wall","early":[1,4],"future":[2,3]}, {"name":"Remember the Route","early":[2,4,1],"future":[3,1,4]},
 {"name":"Deferred Obstacle","early":[4,1,3,2],"future":[1,3,4,2]}, {"name":"Future Maze","early":[1,3,2,4,1],"future":[4,2,1,3,2]},
 {"name":"Long Credit","early":[3,1,4,2,3,1],"future":[2,4,1,3,2,4]}, {"name":"Future Walls","early":[2,4,1,3,2,1,4],"future":[1,3,4,2,1,4,3]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FIELD
  seq=g.early if g.phase==0 else g.future
  for i,a in enumerate(seq):x=8+i*7;f[20:31,x:x+5]=WALL if g.phase else EARLY;f[39:48,x:x+5]=DONE if i<g.progress else GOAL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q188(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.early=self.future=[];self.phase=self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q188",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.early=list(s["early"]);self.future=list(s["future"]);self.phase=self.progress=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  seq=self.early if self.phase==0 else self.future
  if z==5 and self.phase==0 and self.progress==len(self.early):self.phase=1;self.progress=0
  elif z in (1,2,3,4):
   if self.progress>=len(seq) or z!=seq[self.progress]:self.failed=True;self.lose()
   else:
    self.progress+=1
    if self.phase==1 and self.progress==len(self.future):self.next_level()
  else:self.failed=True;self.lose()
  self.complete_action()
