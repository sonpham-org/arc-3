"""q067 Map Fragments -- rotate overlapping local maps into one global frame."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TABLE,FRAGMENT,LANDMARK,OVERLAP,TARGET,CURSOR,BAD=13,4,10,9,6,14,11,8
LEVELS=[
 {"name":"Register Pair","rotations":[1,0]}, {"name":"Shared Landmark","rotations":[3,1,0]},
 {"name":"Three Bearings","rotations":[2,3,1]}, {"name":"Rotated Overlap","rotations":[1,2,3,0]},
 {"name":"Fragment Mosaic","rotations":[3,1,2,1,0]}, {"name":"Map Fragments","rotations":[2,3,1,2,0,3]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=TABLE;n=len(g.rotations)
  for i,r in enumerate(g.current):
   x=7+i*(50//n);f[18:40,x:x+8]=FRAGMENT
   if r==0:f[20:25,x+1:x+6]=LANDMARK
   elif r==1:f[20:34,x+4:x+7]=LANDMARK
   elif r==2:f[33:38,x+2:x+7]=LANDMARK
   else:f[24:38,x+1:x+4]=LANDMARK
   f[13:16,x:x+8]=CURSOR if i==g.cursor else TABLE;f[43:47,x:x+g.rotations[i]+3]=TARGET
  f[50:53,9:55]=OVERLAP
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q067(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rotations=self.current=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q067",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):self.rotations=list(LEVELS[self.level_index]["rotations"]);self.current=[0]*len(self.rotations);self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==1:self.cursor=(self.cursor-1)%len(self.current)
  elif a==2:self.cursor=(self.cursor+1)%len(self.current)
  elif a==3:self.current[self.cursor]=(self.current[self.cursor]-1)%4
  elif a==4:self.current[self.cursor]=(self.current[self.cursor]+1)%4
  elif a==6:
   if self.current==self.rotations:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
