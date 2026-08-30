"""q040 Mass Shadow -- balance invariant mass despite orientation-dependent silhouettes."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ROOM,OBJECT,SHADOW,LEFT,RIGHT,TARGET,CURSOR,BAD=12,1,9,3,10,15,14,11,8
LEVELS=[
 {"name":"Same Mass New Shadow","masses":[1,1],"target":[0,1]},
 {"name":"Three Projections","masses":[1,2,3],"target":[1,1,0]},
 {"name":"Equal Silhouettes","masses":[1,1,2,2],"target":[1,0,1,0]},
 {"name":"Hidden Weight","masses":[1,2,3,4],"target":[1,0,0,1]},
 {"name":"Platform Balance","masses":[1,2,2,3,4],"target":[1,1,0,1,0]},
 {"name":"Mass Shadow","masses":[1,2,3,4,5,3],"target":[1,0,1,0,1,0]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=ROOM;n=len(g.masses)
  for i,m in enumerate(g.masses):
   x=7+i*(50//n);w=3+((m+g.orient[i])%5);f[20:34,x:x+w]=OBJECT;f[35:39,x:x+9]=SHADOW;f[43:47,x:x+9]=RIGHT if g.sides[i] else LEFT;f[14:17,x:x+9]=CURSOR if i==g.cursor else ROOM
  f[50:54,8:56]=TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q040(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.masses=self.target=self.sides=self.orient=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q040",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.masses=list(s["masses"]);self.target=list(s["target"]);self.sides=[0]*len(self.masses);self.orient=[0]*len(self.masses);self.cursor=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.orient[self.cursor]=(self.orient[self.cursor]+1)%4
  elif z==3:self.cursor=(self.cursor-1)%len(self.masses)
  elif z==4:self.cursor=(self.cursor+1)%len(self.masses)
  elif z==5:self.sides[self.cursor]=1-self.sides[self.cursor]
  elif z==6:
   right=sum(m for m,s in zip(self.masses,self.sides) if s)
   if right*2==sum(self.masses):self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
