"""q109 Body-Centric Maze -- world commands must be converted after each maze rotation."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MAZE,BODY,LANDMARK,WORLD,BODYDIR,DONE,BAD=10,1,9,14,12,15,6,8
LEVELS=[
 {"name":"One Rotation","world":[1,4]}, {"name":"Track the Landmark","world":[2,4,1]},
 {"name":"Body Frame","world":[4,1,3,2]}, {"name":"Rotating Maze","world":[1,3,2,4,1]},
 {"name":"Stable Landmark","world":[3,1,4,2,3,1]}, {"name":"Body-Centric Maze","world":[2,4,1,3,2,1,4]}]
def body_action(world,rotation):return((world-1-rotation)%4)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=MAZE;f[21:38,23:40]=BODY;f[13:18,8+g.rotation*12:17+g.rotation*12]=LANDMARK
  for i,w in enumerate(g.world):x=8+i*7;f[43:49,x:x+5]=DONE if i<g.progress else WORLD
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q109(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.world=[];self.progress=self.rotation=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q109",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):self.world=list(LEVELS[self.level_index]["world"]);self.progress=self.rotation=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z!=body_action(self.world[self.progress],self.rotation):self.failed=True;self.lose()
  else:
   self.progress+=1;self.rotation=(self.rotation+1)%4
   if self.progress==len(self.world):self.next_level()
  self.complete_action()
